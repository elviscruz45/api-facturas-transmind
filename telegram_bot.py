"""
Telegram Bot MVP - Invoice Extraction
Handles photo/PDF uploads with confirmation before processing.
"""
import asyncio
import io
import base64
from datetime import datetime
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from config import settings
from app.services.gemini_service import gemini_service
from app.services.supabase_service import supabase_service
from app.services.storage_service import storage_service
from app.schemas.invoice_schema import ProcessingResponse, InvoiceSchema
from app.utils.logger import setup_logger

logger = setup_logger("telegram_bot")

# Temporary storage for pending files (file_id -> file_info)
pending_files: Dict[str, Dict] = {}


def create_excel_from_invoice(invoice: InvoiceSchema) -> io.BytesIO:
    """Create Excel file from a single invoice"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Factura"
    
    # Header styling
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    # Invoice summary
    ws.cell(row=1, column=1, value="Campo").fill = header_fill
    ws.cell(row=1, column=1).font = header_font
    ws.cell(row=1, column=2, value="Valor").fill = header_fill
    ws.cell(row=1, column=2).font = header_font
    
    row = 2
    ws.cell(row=row, column=1, value="Nro. Factura")
    ws.cell(row=row, column=2, value=invoice.invoice_number or "")
    row += 1
    
    ws.cell(row=row, column=1, value="Fecha")
    ws.cell(row=row, column=2, value=invoice.invoice_date or "")
    row += 1
    
    ws.cell(row=row, column=1, value="Proveedor")
    ws.cell(row=row, column=2, value=invoice.supplier_name or "")
    row += 1
    
    ws.cell(row=row, column=1, value="RUC Proveedor")
    ws.cell(row=row, column=2, value=invoice.supplier_ruc or "")
    row += 1
    
    ws.cell(row=row, column=1, value="Cliente")
    ws.cell(row=row, column=2, value=invoice.customer_name or "")
    row += 1
    
    ws.cell(row=row, column=1, value="Subtotal")
    ws.cell(row=row, column=2, value=invoice.subtotal)
    row += 1
    
    ws.cell(row=row, column=1, value="IGV")
    ws.cell(row=row, column=2, value=invoice.tax)
    row += 1
    
    ws.cell(row=row, column=1, value="Total")
    ws.cell(row=row, column=2, value=invoice.total)
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 1
    
    ws.cell(row=row, column=1, value="Moneda")
    ws.cell(row=row, column=2, value=invoice.currency or "PEN")
    row += 1
    
    # Items section
    if invoice.items:
        row += 2
        ws.cell(row=row, column=1, value="Items").font = Font(bold=True, size=12)
        row += 1
        
        # Item headers
        item_headers = ["#", "Descripción", "Cantidad", "Precio Unit.", "Total"]
        for col, header in enumerate(item_headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
        row += 1
        
        # Items
        for idx, item in enumerate(invoice.items, 1):
            ws.cell(row=row, column=1, value=idx)
            ws.cell(row=row, column=2, value=item.description or "")
            ws.cell(row=row, column=3, value=item.quantity)
            ws.cell(row=row, column=4, value=item.unit_price)
            ws.cell(row=row, column=5, value=item.total_price)
            row += 1
    
    # Auto-adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    
    # Save to BytesIO
    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    
    return excel_file


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    chat_id = str(update.effective_chat.id)
    chat_title = update.effective_chat.title or update.effective_user.first_name or "Usuario"
    
    # Register company in Supabase if not exists
    if supabase_service.is_enabled():
        company = await supabase_service.get_company(chat_id)
        if not company:
            await supabase_service.save_company(
                chat_id=chat_id,
                name=chat_title,
                plan="free",
                limit_monthly=100,
                registered_by=update.effective_user.username or str(update.effective_user.id)
            )
            logger.log_info(
                "New company registered",
                chat_id=chat_id,
                name=chat_title
            )
    
    welcome_message = f"""
¡Bienvenido! 👋

Soy un bot de extracción de facturas. 

📸 **Envíame una foto o PDF de tu factura** y te enviaré un Excel con todos los datos extraídos.

📊 **Plan actual**: Gratuito (100 facturas/mes)

💡 **Instrucciones**:
1. Envía foto o PDF de la factura
2. Confirma el procesamiento
3. Recibe tu Excel con los datos

¡Empecemos!
"""
    
    await update.message.reply_text(welcome_message)
    
    logger.log_info(
        "Bot started",
        chat_id=chat_id,
        chat_title=chat_title,
        user=update.effective_user.username
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads"""
    try:
        chat_id = str(update.effective_chat.id)
        
        # Get largest photo
        photo = update.message.photo[-1]
        file_id = photo.file_id
        file_unique_id = photo.file_unique_id
        
        # Use shorter callback_data to avoid issues
        callback_key = f"{chat_id}_{update.message.message_id}"
        
        # Store pending file
        pending_files[callback_key] = {
            "type": "photo",
            "file_id": file_id,
            "file_unique_id": file_unique_id,
            "chat_id": chat_id,
            "message_id": update.message.message_id,
            "user": update.effective_user.username or str(update.effective_user.id)
        }
        
        # Create confirmation buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Sí", callback_data=f"yes_{callback_key}"),
                InlineKeyboardButton("❌ No", callback_data=f"no_{callback_key}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📸 Foto recibida.\n\n¿Procesar esta factura?",
            reply_markup=reply_markup
        )
        
        logger.log_info(
            "Photo received, awaiting confirmation",
            chat_id=chat_id,
            file_id=file_id
        )
        
    except Exception as e:
        logger.log_error(
            "Error handling photo",
            error=str(e),
            chat_id=str(update.effective_chat.id) if update.effective_chat else "unknown"
        )
        await update.message.reply_text(
            "❌ Error al recibir la foto. Por favor, intenta nuevamente."
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (PDFs)"""
    try:
        chat_id = str(update.effective_chat.id)
        document = update.message.document
        
        file_id = document.file_id
        file_unique_id = document.file_unique_id
        file_name = document.file_name
        mime_type = document.mime_type
        
        # Check if it's a PDF
        if mime_type != "application/pdf":
            await update.message.reply_text(
                "⚠️ Solo acepto archivos PDF o fotos.\n\nPor favor, envía una imagen o PDF de la factura."
            )
            return
        
        # Use shorter callback_data
        callback_key = f"{chat_id}_{update.message.message_id}"
        
        # Store pending file
        pending_files[callback_key] = {
            "type": "pdf",
            "file_id": file_id,
            "file_unique_id": file_unique_id,
            "file_name": file_name,
            "chat_id": chat_id,
            "message_id": update.message.message_id,
            "user": update.effective_user.username or str(update.effective_user.id)
        }
        
        # Create confirmation buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Sí", callback_data=f"yes_{callback_key}"),
                InlineKeyboardButton("❌ No", callback_data=f"no_{callback_key}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📄 PDF recibido: {file_name}\n\n¿Procesar esta factura?",
            reply_markup=reply_markup
        )
        
        logger.log_info(
            "PDF received, awaiting confirmation",
            chat_id=chat_id,
            file_id=file_id,
            file_name=file_name
        )
        
    except Exception as e:
        logger.log_error(
            "Error handling document",
            error=str(e),
            chat_id=str(update.effective_chat.id) if update.effective_chat else "unknown"
        )
        await update.message.reply_text(
            "❌ Error al recibir el documento. Por favor, intenta nuevamente."
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Parse callback: "yes_chatid_msgid" or "no_chatid_msgid"
    parts = callback_data.split("_", 1)
    if len(parts) != 2:
        await query.edit_message_text("⚠️ Solicitud inválida. Por favor, envía la factura nuevamente.")
        return
    
    action, callback_key = parts
    
    # Get pending file info
    file_info = pending_files.get(callback_key)
    if not file_info:
        await query.edit_message_text("⚠️ Archivo expirado. Por favor, envía la factura nuevamente.")
        return
    
    if action == "no":
        # Remove from pending
        del pending_files[callback_key]
        await query.edit_message_text("❌ Procesamiento cancelado.")
        logger.log_info("Processing cancelled", callback_key=callback_key)
        return
    
    if action == "yes":
        await query.edit_message_text("⏳ Procesando factura, por favor espera...")
        
        try:
            # Download file from Telegram
            file_id = file_info["file_id"]
            file = await context.bot.get_file(file_id)
            file_bytes = await file.download_as_bytearray()
            
            logger.log_info(
                "File downloaded from Telegram",
                file_id=file_id,
                size_bytes=len(file_bytes)
            )
            
            # Process based on file type
            if file_info["type"] == "photo":
                # Convert bytes to base64
                image_base64 = base64.b64encode(bytes(file_bytes)).decode('utf-8')
                
                # Process as image
                result = await gemini_service.extract_invoice_from_image(
                    image_base64=image_base64,
                    filename=f"telegram_photo_{file_id}.jpg",
                    sequence_id=1
                )
            else:
                # Process as PDF (for MVP, treat as image for now)
                # TODO: Implement proper PDF processing
                await query.edit_message_text(
                    "⚠️ Procesamiento de PDF aún no implementado en MVP.\n\n"
                    "Por favor, envía una captura de pantalla de la factura como foto."
                )
                del pending_files[callback_key]
                return
            
            # Check if extraction was successful
            if not result or not result.get("success"):
                error_msg = result.get("error", "Error desconocido") if result else "No se pudo procesar"
                await query.edit_message_text(
                    f"❌ No pude extraer datos de esta factura.\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Intenta con:\n"
                    f"• Una imagen más clara\n"
                    f"• Mejor iluminación\n"
                    f"• Asegúrate de que la factura sea visible"
                )
                del pending_files[callback_key]
                return
            
            # Convert dict to InvoiceSchema object
            invoice_data = result.get("invoice_data", {})
            invoice = InvoiceSchema(**invoice_data)
            
            logger.log_info(
                "Invoice extracted successfully",
                callback_key=callback_key,
                invoice_number=invoice.invoice_number,
                total=invoice.total
            )
            
            # Generate Excel
            excel_file = create_excel_from_invoice(invoice)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"factura_{timestamp}.xlsx"
            
            # Upload to Cloud Storage (optional, won't fail if it doesn't work)
            excel_blob_path = None
            if storage_service.client:
                try:
                    excel_metadata = storage_service.upload_excel(
                        excel_file,
                        excel_filename,
                        company_id=file_info["chat_id"]
                    )
                    if excel_metadata:
                        excel_blob_path = excel_metadata.get("blob_path")
                    excel_file.seek(0)  # Reset for sending
                except Exception as storage_error:
                    logger.log_warning(
                        "Failed to upload to Cloud Storage",
                        error=str(storage_error)
                    )
            
            # Save to Supabase
            record_id = None
            if supabase_service.is_enabled():
                try:
                    # Save processing record
                    record_id = await supabase_service.save_processing_record(
                        chat_id=file_info["chat_id"],
                        zip_blob_path=None,
                        excel_blob_path=excel_blob_path,
                        total_files=1,
                        success_files=1,
                        error_files=0,
                        telegram_file_id=file_id,
                        telegram_file_unique_id=file_info["file_unique_id"]
                    )
                    
                    # Save invoice
                    if record_id:
                        await supabase_service.save_invoices_batch(
                            invoices=[invoice],
                            chat_id=file_info["chat_id"],
                            record_id=record_id
                        )
                    
                    logger.log_info(
                        "Data saved to Supabase",
                        record_id=record_id,
                        chat_id=file_info["chat_id"]
                    )
                except Exception as db_error:
                    logger.log_error(
                        "Failed to save to Supabase",
                        error=str(db_error)
                    )
            
            # Send Excel to user
            caption = (
                f"✅ Factura procesada exitosamente\n\n"
                f"💰 Total: {invoice.currency or 'PEN'} {invoice.total or 0:.2f}\n"
                f"📊 IGV: {invoice.currency or 'PEN'} {invoice.tax or 0:.2f}\n"
                f"📄 Nro: {invoice.invoice_number or 'N/A'}"
            )
            
            await context.bot.send_document(
                chat_id=file_info["chat_id"],
                document=excel_file,
                filename=excel_filename,
                caption=caption
            )
            
            await query.edit_message_text("✅ ¡Listo! Excel enviado.")
            
            # Remove from pending
            del pending_files[callback_key]
            
            logger.log_info(
                "Processing completed successfully",
                callback_key=callback_key,
                chat_id=file_info["chat_id"]
            )
            
        except Exception as e:
            logger.log_error(
                "Error processing file",
                callback_key=callback_key,
                error=str(e)
            )
            
            await query.edit_message_text(
                f"❌ Error al procesar la factura.\n\n"
                f"Error: {str(e)}\n\n"
                f"Por favor, intenta nuevamente."
            )
            
            # Remove from pending
            if callback_key in pending_files:
                del pending_files[callback_key]


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ayuda command"""
    help_text = """
📖 **Ayuda - Bot de Facturas**

**Cómo usar:**
1. Envía una foto clara de tu factura
2. Espera la confirmación
3. Haz clic en "✅ Sí, procesar"
4. Recibe tu Excel con los datos

**Formatos aceptados:**
• Fotos (JPG, PNG)
• PDFs (próximamente)

**Consejos para mejores resultados:**
• Asegúrate de que la factura esté completa
• Buena iluminación
• Imagen clara y enfocada
• Evita sombras y reflejos

**Comandos:**
/start - Iniciar el bot
/ayuda - Ver esta ayuda

¿Necesitas soporte? Contacta al administrador.
"""
    
    await update.message.reply_text(help_text)


def main():
    """Start the bot"""
    if not settings.telegram_bot_token:
        logger.log_error("TELEGRAM_BOT_TOKEN not configured in .env")
        print("❌ Error: TELEGRAM_BOT_TOKEN no está configurado en el archivo .env")
        print("Por favor, obtén tu token de @BotFather y agrégalo al .env")
        return
    
    logger.log_info("Starting Telegram bot...")
    
    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ayuda", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    logger.log_info("Bot is running... Press Ctrl+C to stop.")
    print("🤖 Bot iniciado correctamente!")
    print("📱 Envía /start al bot para comenzar")
    print("⏹️  Presiona Ctrl+C para detener")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

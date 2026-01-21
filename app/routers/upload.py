from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from app.services.zip_handler import ZipHandler
from app.services.processing_orchestrator import orchestrator
from app.services.storage_service import storage_service
from app.schemas.invoice_schema import ProcessingResponse
from app.utils.logger import setup_logger
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from datetime import datetime

logger = setup_logger("upload_router")

router = APIRouter()

zip_handler = ZipHandler()

def create_excel_from_results(processing_response: ProcessingResponse, filename: str) -> io.BytesIO:
    """Convert processing results to Excel file"""
    wb = Workbook()
    
    # Sheet 1: Invoices Summary
    ws_summary = wb.active
    ws_summary.title = "Resumen Facturas"
    
    # Header styling
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    # Headers for summary
    headers = [
        "Nro. Factura", "Fecha", "Proveedor", "RUC Proveedor", 
        "Cliente", "Subtotal", "IGV", "Total", "Moneda",
        "Confianza", "Archivo Origen", "Secuencia"
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws_summary.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Data rows
    for row_idx, invoice in enumerate(processing_response.results, 2):
        ws_summary.cell(row=row_idx, column=1, value=invoice.invoice_number or "")
        ws_summary.cell(row=row_idx, column=2, value=invoice.invoice_date or "")
        ws_summary.cell(row=row_idx, column=3, value=invoice.supplier_name or "")
        ws_summary.cell(row=row_idx, column=4, value=invoice.supplier_ruc or "")
        ws_summary.cell(row=row_idx, column=5, value=invoice.customer_name or "")
        ws_summary.cell(row=row_idx, column=6, value=invoice.subtotal)
        ws_summary.cell(row=row_idx, column=7, value=invoice.tax)
        ws_summary.cell(row=row_idx, column=8, value=invoice.total)
        ws_summary.cell(row=row_idx, column=9, value=invoice.currency or "")
        ws_summary.cell(row=row_idx, column=10, value=invoice.confidence_score)
        ws_summary.cell(row=row_idx, column=11, value=invoice.source_file)
        ws_summary.cell(row=row_idx, column=12, value=invoice.sequence_id)
    
    # Auto-adjust column widths
    for col in range(1, len(headers) + 1):
        ws_summary.column_dimensions[ws_summary.cell(row=1, column=col).column_letter].width = 15
    
    # Sheet 2: Items Detail
    ws_items = wb.create_sheet("Detalle Items")
    
    item_headers = [
        "Nro. Factura", "Archivo Origen", "Item", "Descripción",
        "Cantidad", "Unidad", "Precio Unit.", "Total Item"
    ]
    
    for col, header in enumerate(item_headers, 1):
        cell = ws_items.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Items data
    item_row = 2
    for invoice in processing_response.results:
        if invoice.items:
            for item_idx, item in enumerate(invoice.items, 1):
                ws_items.cell(row=item_row, column=1, value=invoice.invoice_number or "")
                ws_items.cell(row=item_row, column=2, value=invoice.source_file)
                ws_items.cell(row=item_row, column=3, value=item_idx)
                ws_items.cell(row=item_row, column=4, value=item.description or "")
                ws_items.cell(row=item_row, column=5, value=item.quantity)
                ws_items.cell(row=item_row, column=6, value=item.unit or "")
                ws_items.cell(row=item_row, column=7, value=item.unit_price)
                ws_items.cell(row=item_row, column=8, value=item.total_price)
                item_row += 1
    
    # Auto-adjust column widths
    for col in range(1, len(item_headers) + 1):
        ws_items.column_dimensions[ws_items.cell(row=1, column=col).column_letter].width = 18
    
    # Sheet 3: Errors
    if processing_response.errors:
        ws_errors = wb.create_sheet("Errores")
        
        error_headers = ["Archivo", "Secuencia", "Tipo", "Error"]
        for col, header in enumerate(error_headers, 1):
            cell = ws_errors.cell(row=1, column=col, value=header)
            cell.fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        for row_idx, error in enumerate(processing_response.errors, 2):
            ws_errors.cell(row=row_idx, column=1, value=error.get("file", ""))
            ws_errors.cell(row=row_idx, column=2, value=error.get("sequence_id", ""))
            ws_errors.cell(row=row_idx, column=3, value=error.get("file_type", ""))
            ws_errors.cell(row=row_idx, column=4, value=error.get("error", ""))
        
        for col in range(1, len(error_headers) + 1):
            ws_errors.column_dimensions[ws_errors.cell(row=1, column=col).column_letter].width = 20
    
    # Save to BytesIO
    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    
    return excel_file

@router.post("/process-zip")
async def process_zip_file(file: UploadFile = File(...)):
    """
    Process a ZIP file from WhatsApp and extract invoice data
    
    - **file**: ZIP file containing WhatsApp exported media
    
    Returns structured invoice data extracted from images, PDFs, and text files.
    Files are processed in chronological order based on WhatsApp timestamps.
    """

    logger.log_info(
        "ZIP file upload started",
        filename=file.filename,
        content_type=file.content_type
    )

    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a ZIP file"
            )
        
        # Read file content
        file_content = await file.read()
        
        logger.log_info(
            "ZIP file read successfully",
            filename=file.filename,
            size_bytes=len(file_content)
        )
        
        # Upload ZIP to Cloud Storage (backup y audit trail)
        storage_metadata = storage_service.upload_zip(
            file_content, 
            file.filename,
            company_id=None  # TODO: extraer de headers o auth cuando implementes multi-tenancy
        )
        
        if storage_metadata:
            logger.log_info(
                "ZIP backed up to Cloud Storage",
                blob_path=storage_metadata["blob_path"],
                signed_url=storage_metadata["signed_url"]
            )
        else:
            # No falla si no se puede subir a Storage (degrada gracefully)
            logger.log_warning(
                "Failed to backup ZIP to Cloud Storage, continuing with processing",
                filename=file.filename
            )
        
        # Phase 1: Extract and validate ZIP
        success, extraction_result = zip_handler.extract_zip_files(file_content, file.filename)
        
        if not success:
            logger.log_error(
                "ZIP extraction failed",
                filename=file.filename,
                error=extraction_result.get("error")
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ZIP processing failed: {extraction_result.get('error')}"
            )
        
        extracted_files = extraction_result["extracted_files"]
        ignored_files = extraction_result["ignored_files"]
        temp_dir_obj = extraction_result.get("temp_dir_obj")
        
        if not extracted_files:
            # Cleanup temp directory if no files to process
            if temp_dir_obj:
                temp_dir_obj.cleanup()
            
            logger.log_warning(
                "No processable files found in ZIP",
                filename=file.filename,
                total_ignored=len(ignored_files)
            )
            
            return ProcessingResponse(
                results=[],
                errors=[{"error": "No processable files found in ZIP"}],
                total_processed=0,
                success_count=0
            )
        
        logger.log_info(
            "ZIP extraction completed",
            filename=file.filename,
            extracted_files=len(extracted_files),
            ignored_files=len(ignored_files)
        )
        
        # Phases 2-6: Process files through the pipeline
        try:
            processing_response = await orchestrator.process_extracted_files(extracted_files)
        finally:
            # Cleanup temp directory after processing
            if temp_dir_obj:
                temp_dir_obj.cleanup()
                logger.log_info("Temporary directory cleaned up", filename=file.filename)
        
        logger.log_info(
            "ZIP processing pipeline completed",
            filename=file.filename,
            total_processed=processing_response.total_processed,
            success_count=processing_response.success_count,
            error_count=len(processing_response.errors)
        )
        
        # Generate Excel file
        excel_file = create_excel_from_results(processing_response, file.filename)
        
        # Upload Excel to Cloud Storage
        excel_metadata = storage_service.upload_excel(
            excel_file,
            file.filename,
            company_id=None  # TODO: extraer de headers o auth
        )
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"facturas_{timestamp}.xlsx"
        
        # Prepare response headers
        response_headers = {
            "Content-Disposition": f"attachment; filename={excel_filename}",
            "X-Total-Files": str(len(extracted_files)),
            "X-Success-Files": str(processing_response.success_count),
            "X-Error-Files": str(len(processing_response.errors))
        }
        
        # Add Cloud Storage URLs to headers if upload succeeded
        if excel_metadata:
            response_headers["X-Storage-Excel-URL"] = excel_metadata["signed_url"]
            logger.log_info(
                "Excel saved to Cloud Storage",
                blob_path=excel_metadata["blob_path"],
                excel_url=excel_metadata["signed_url"]
            )
        
        if storage_metadata:
            response_headers["X-Storage-Zip-URL"] = storage_metadata["signed_url"]
        
        # Reset BytesIO position for streaming
        excel_file.seek(0)
        
        return StreamingResponse(
            excel_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=response_headers
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        logger.log_error(
            "Unexpected error during ZIP processing",
            filename=file.filename if file else "unknown",
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "invoice_extraction"}


@router.get("/info")
async def service_info():
    """Get service information"""
    from config import settings
    
    return {
        "service_name": "WhatsApp Invoice Extraction API",
        "supported_file_types": settings.allowed_extensions,
        "max_file_size_mb": settings.max_file_size_mb,
        "gemini_model": settings.gemini_model,
        "processing_phases": [
            "Phase 1: ZIP validation and extraction",
            "Phase 2: Chronological file sorting", 
            "Phase 3: File type classification",
            "Phase 4: Content processing by type",
            "Phase 5: Structured data extraction",
            "Phase 6: Pipeline orchestration"
        ]
    }


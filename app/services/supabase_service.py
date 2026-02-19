"""
Supabase Service for database operations.
Handles saving processing records, invoices, and company data.
"""
from supabase import create_client, Client
from config import settings
from app.utils.logger import setup_logger
from typing import List, Dict, Optional
from datetime import datetime
import uuid

logger = setup_logger("supabase_service")


class SupabaseService:
    """Service for interacting with Supabase database"""
    
    def __init__(self):
        """Initialize Supabase client with service role key for backend operations"""
        if not settings.supabase_url or not settings.supabase_secret_key:
            logger.log_warning(
                "Supabase credentials not configured",
                url=settings.supabase_url,
                has_key=bool(settings.supabase_secret_key)
            )
            self.client: Optional[Client] = None
            self.enabled = False
        else:
            try:
                # Use service_role key for backend operations (bypasses RLS)
                self.client: Client = create_client(
                    settings.supabase_url,
                    settings.supabase_secret_key
                )
                self.enabled = True
                logger.log_info("Supabase client initialized successfully")
            except Exception as e:
                logger.log_error(
                    "Failed to initialize Supabase client",
                    error=str(e)
                )
                self.client = None
                self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if Supabase integration is enabled"""
        return self.enabled and self.client is not None
    
    async def save_company(
        self,
        chat_id: str,
        name: str,
        plan: str = "free",
        limit_monthly: int = 100,
        registered_by: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Save or update company information
        
        Args:
            chat_id: Unique identifier (Telegram chat_id)
            name: Company name
            plan: Subscription plan (free/pro/enterprise)
            limit_monthly: Monthly invoice processing limit
            registered_by: Username or ID who registered the company
            
        Returns:
            Company record or None if failed
        """
        if not self.is_enabled():
            logger.log_error("🔴 Supabase is not enabled - cannot save company")
            return None
        
        try:
            data = {
                "chat_id": chat_id,
                "name": name,
                "plan": plan,
                "limit_monthly": limit_monthly,
                "usage_current_month": 0
            }
            
            if registered_by:
                # Note: 'registered_by' field doesn't exist in DB schema
                # Ignoring this field for now
                pass
            
            logger.log_info(
                "📤 About to insert/upsert company to Supabase",
                data=data
            )
            
            # Upsert: insert or update if exists
            result = self.client.table("companies").upsert(
                data,
                on_conflict="chat_id"
            ).execute()
            
            logger.log_info(
                "✅ Company upsert executed",
                has_data=bool(result.data),
                data_count=len(result.data) if result.data else 0
            )
            
            if not result.data:
                logger.log_error(
                    "❌ Upsert returned no data",
                    chat_id=chat_id
                )
                return None
            
            logger.log_info(
                "✅ Company saved to database",
                chat_id=chat_id,
                name=name,
                plan=plan,
                result=result.data[0]
            )
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.log_error(
                "❌ Exception in save_company",
                chat_id=chat_id,
                error=str(e),
                error_type=type(e).__name__
            )
            import traceback
            logger.log_error(
                "📍 Traceback from save_company",
                traceback=traceback.format_exc()
            )
            return None
    
    async def get_company(self, chat_id: str) -> Optional[Dict]:
        """
        Get company by chat_id
        
        Args:
            chat_id: Company identifier (Telegram chat_id)
            
        Returns:
            Company record or None if not found
        """
        if not self.is_enabled():
            logger.log_error("🔴 Supabase is not enabled - cannot get company")
            return None
        
        try:
            logger.log_info(
                "📥 Querying companies table",
                chat_id=chat_id
            )
            
            result = self.client.table("companies").select("*").eq(
                "chat_id", chat_id
            ).execute()
            
            logger.log_info(
                "📊 Query result",
                has_data=bool(result.data),
                data_count=len(result.data) if result.data else 0
            )
            
            if result.data and len(result.data) > 0:
                logger.log_info(
                    "✅ Company found",
                    chat_id=chat_id,
                    company=result.data[0]
                )
                return result.data[0]
            else:
                logger.log_info(
                    "❌ Company not found",
                    chat_id=chat_id
                )
                return None
            
        except Exception as e:
            logger.log_error(
                "❌ Exception in get_company",
                chat_id=chat_id,
                error=str(e),
                error_type=type(e).__name__
            )
            import traceback
            logger.log_error(
                "📍 Traceback from get_company",
                traceback=traceback.format_exc()
            )
            return None
    
    async def increment_company_usage(
        self,
        chat_id: str,
        invoices_count: int
    ) -> bool:
        """
        Increment company's monthly usage counter
        
        Args:
            chat_id: Company identifier (Telegram chat_id)
            invoices_count: Number of invoices to add to usage
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            # Manual increment (no RPC needed for simple increment)
            company = await self.get_company(chat_id)
            if company:
                new_usage = company.get("usage", 0) + invoices_count
                self.client.table("companies").update({
                    "usage": new_usage
                }).eq("chat_id", chat_id).execute()
                
                logger.log_info(
                    "Company usage incremented",
                    chat_id=chat_id,
                    count=invoices_count,
                    new_usage=new_usage
                )
                return True
            else:
                logger.log_warning(
                    "Company not found for usage increment",
                    chat_id=chat_id
                )
                return False
            
        except Exception as e:
            logger.log_error(
                "Failed to increment usage",
                chat_id=chat_id,
                error=str(e)
            )
            return False
    
    async def save_processing_record(
        self,
        chat_id: str,
        zip_blob_path: Optional[str],
        excel_blob_path: Optional[str],
        total_files: int,
        success_files: int,
        error_files: int,
        telegram_file_id: Optional[str] = None,
        telegram_file_unique_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Save processing record
        
        Args:
            chat_id: Company identifier (Telegram chat_id)
            zip_blob_path: Cloud Storage path to ZIP
            excel_blob_path: Cloud Storage path to Excel
            total_files: Total files processed
            success_files: Successfully extracted files
            error_files: Number of errors
            telegram_file_id: Telegram file ID
            telegram_file_unique_id: Telegram unique file ID
            
        Returns:
            Record ID (UUID) or None if failed
        """
        if not self.is_enabled():
            return None
        
        try:
            # Ensure company exists (create if needed, especially for 'anonymous')
            company = await self.get_company(chat_id)
            if not company:
                logger.log_info(
                    "Company not found, creating it",
                    chat_id=chat_id
                )
                await self.save_company(
                    chat_id=chat_id,
                    name="Anonymous User" if chat_id == "anonymous" else f"User {chat_id}",
                    plan="free",
                    limit_monthly=999999 if chat_id == "anonymous" else 100,
                    registered_by="system"
                )
            
            record_id = str(uuid.uuid4())
            
            # Build data dict
            data = {
                "id": record_id,
                "company_id": chat_id,
                "total_files": total_files,
                "success_files": success_files,
                "error_files": error_files,
                "deleted": False
            }
            
            # Add optional fields
            if zip_blob_path:
                data["zip_blob_path"] = zip_blob_path
            if excel_blob_path:
                data["excel_blob_path"] = excel_blob_path
            if telegram_file_id:
                data["telegram_file_id"] = telegram_file_id
            if telegram_file_unique_id:
                data["telegram_file_unique_id"] = telegram_file_unique_id
            
            result = self.client.table("processing_records").insert(data).execute()
            
            logger.log_info(
                "Processing record saved",
                record_id=record_id,
                chat_id=chat_id,
                total_files=total_files
            )
            
            return record_id
            
        except Exception as e:
            logger.log_error(
                "Failed to save processing record",
                chat_id=chat_id,
                error=str(e)
            )
            return None
    
    async def save_invoices_batch(
        self,
        invoices: List[Dict],
        chat_id: str,
        record_id: str
    ) -> bool:
        """
        Save batch of invoices to database
        
        Args:
            invoices: List of invoice dictionaries from ProcessingResponse
            chat_id: Company identifier (Telegram chat_id)
            record_id: Processing record UUID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        if not invoices:
            return True  # Nothing to save
        
        try:
            # Transform invoice data for database
            db_invoices = []
            
            for invoice in invoices:
                db_invoice = {
                    "company_id": chat_id,
                    "record_id": record_id,
                    "sequence_id": invoice.sequence_id if hasattr(invoice, 'sequence_id') else None,
                    "source_file": invoice.source_file if hasattr(invoice, 'source_file') else None,
                    "invoice_number": invoice.invoice_number if hasattr(invoice, 'invoice_number') else None,
                    "invoice_date": invoice.invoice_date if hasattr(invoice, 'invoice_date') else None,
                    "supplier_name": invoice.supplier_name if hasattr(invoice, 'supplier_name') else None,
                    "supplier_ruc": invoice.supplier_ruc if hasattr(invoice, 'supplier_ruc') else None,
                    "customer_name": invoice.customer_name if hasattr(invoice, 'customer_name') else None,
                    "customer_ruc": invoice.customer_ruc if hasattr(invoice, 'customer_ruc') else None,
                    "subtotal": float(invoice.subtotal) if hasattr(invoice, 'subtotal') and invoice.subtotal else None,
                    "igv": float(invoice.tax) if hasattr(invoice, 'tax') and invoice.tax else None,
                    "total": float(invoice.total) if hasattr(invoice, 'total') and invoice.total else None,
                    "currency": invoice.currency if hasattr(invoice, 'currency') else "PEN",
                    "confidence_score": invoice.confidence_score if hasattr(invoice, 'confidence_score') else None
                }
                
                db_invoices.append(db_invoice)
            
            # Batch insert invoices
            result = self.client.table("invoices").insert(db_invoices).execute()
            
            if not result.data:
                logger.log_error(
                    "No invoices were inserted",
                    chat_id=chat_id,
                    record_id=record_id
                )
                return False
            
            logger.log_info(
                "Invoices saved to database",
                count=len(db_invoices),
                chat_id=chat_id,
                record_id=record_id
            )
            
            # Save invoice items to separate table
            await self._save_invoice_items(invoices, result.data, chat_id)
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to save invoices batch",
                chat_id=chat_id,
                record_id=record_id,
                count=len(invoices),
                error=str(e)
            )
            return False
    
    async def _save_invoice_items(
        self,
        invoices: List[Dict],
        saved_invoices: List[Dict],
        chat_id: str
    ) -> bool:
        """
        Save invoice items to invoice_items table
        
        Args:
            invoices: Original invoice objects with items
            saved_invoices: Invoices returned from database (with IDs)
            chat_id: Company identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            all_items = []
            
            # Match invoices with their database IDs using sequence_id
            for i, invoice in enumerate(invoices):
                # Find corresponding saved invoice
                saved_invoice = None
                if i < len(saved_invoices):
                    saved_invoice = saved_invoices[i]
                
                if not saved_invoice or 'id' not in saved_invoice:
                    logger.log_warning(
                        "Could not find saved invoice ID for items",
                        invoice_number=invoice.invoice_number if hasattr(invoice, 'invoice_number') else None
                    )
                    continue
                
                invoice_id = saved_invoice['id']
                
                # Extract items from invoice
                if hasattr(invoice, 'items') and invoice.items:
                    for item_number, item in enumerate(invoice.items, 1):
                        item_data = {
                            "invoice_id": invoice_id,
                            "company_id": chat_id,
                            "item_number": item_number,
                            "description": item.description if hasattr(item, 'description') else None,
                            "quantity": float(item.quantity) if hasattr(item, 'quantity') and item.quantity else None,
                            "unit": item.unit if hasattr(item, 'unit') else None,
                            "unit_price": float(item.unit_price) if hasattr(item, 'unit_price') and item.unit_price else None,
                            "total_price": float(item.total_price) if hasattr(item, 'total_price') and item.total_price else None
                        }
                        all_items.append(item_data)
            
            # Batch insert items if any exist
            if all_items:
                self.client.table("invoice_items").insert(all_items).execute()
                
                logger.log_info(
                    "Invoice items saved to database",
                    count=len(all_items),
                    chat_id=chat_id
                )
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to save invoice items",
                chat_id=chat_id,
                error=str(e)
            )
            return False
    
    async def get_company_invoices(
        self,
        chat_id: str,
        limit: int = 100,
        offset: int = 0,
        include_deleted: bool = False
    ) -> List[Dict]:
        """
        Get invoices for a company (paginated)
        
        Args:
            chat_id: Company identifier (Telegram chat_id)
            limit: Maximum records to return
            offset: Number of records to skip
            include_deleted: Include soft-deleted invoices
            
        Returns:
            List of invoice records
        """
        if not self.is_enabled():
            return []
        
        try:
            query = self.client.table("invoices").select("*").eq(
                "company_id", chat_id
            )
            
            # Filter out deleted invoices unless explicitly requested
            if not include_deleted:
                query = query.is_("deleted_at", "null")
            
            result = query.order(
                "created_at", desc=True
            ).range(offset, offset + limit - 1).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.log_error(
                "Failed to get company invoices",
                chat_id=chat_id,
                error=str(e)
            )
            return []
    
    async def delete_processing_record(self, record_id: str) -> bool:
        """
        Delete processing record and associated invoices
        
        Args:
            record_id: Processing record UUID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            # Delete invoices first (foreign key constraint)
            self.client.table("invoices").delete().eq("record_id", record_id).execute()
            
            # Delete processing record
            self.client.table("processing_records").delete().eq("id", record_id).execute()
            
            logger.log_info(
                "Processing record deleted",
                record_id=record_id
            )
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to delete processing record",
                record_id=record_id,
                error=str(e)
            )
            return False
    
    async def get_invoices_with_items(
        self,
        chat_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        report_type: str = "custom"
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Get invoices and their items with date filtering for Excel export
        
        Args:
            chat_id: Company identifier (optional, None = all companies)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            report_type: 'daily', 'monthly', or 'custom'
            
        Returns:
            Tuple of (invoices_list, items_list)
        """
        if not self.is_enabled():
            return [], []
        
        try:
            # Build invoices query
            query = self.client.table("invoices").select("*")
            
            # Filter by company if provided
            if chat_id:
                query = query.eq("company_id", chat_id)
            
            # Filter by date range
            if start_date:
                query = query.gte("invoice_date", start_date)
            if end_date:
                query = query.lte("invoice_date", end_date)
            
            # Exclude deleted invoices
            query = query.eq("deleted", False)
            
            # Execute query
            invoices_result = query.order("invoice_date", desc=True).execute()
            invoices = invoices_result.data if invoices_result.data else []
            
            # Get invoice IDs for items query
            if not invoices:
                return [], []
            
            invoice_ids = [inv['id'] for inv in invoices]
            
            # Build items query
            items_query = self.client.table("invoice_items").select("*").in_(
                "invoice_id", invoice_ids
            )
            
            # Execute items query
            items_result = items_query.order("invoice_id").order("item_number").execute()
            items = items_result.data if items_result.data else []
            
            logger.log_info(
                "Retrieved invoices with items for export",
                invoices_count=len(invoices),
                items_count=len(items),
                chat_id=chat_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return invoices, items
            
        except Exception as e:
            logger.log_error(
                "Failed to get invoices with items",
                chat_id=chat_id,
                error=str(e)
            )
            return [], []
    
    async def save_single_invoice(
        self,
        invoice_data: Dict,
        phone_number: str,
        job_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Save a single invoice with its items to database
        
        Args:
            invoice_data: Invoice data dictionary from WhatsApp API
            phone_number: Phone number/company identifier
            job_id: Optional job ID for tracking
            
        Returns:
            Invoice ID if successful, None otherwise
        """
        if not self.is_enabled():
            logger.log_error("Supabase service is not enabled")
            return None
        
        try:
            logger.log_info(
                "🟢 SUPABASE SERVICE: save_single_invoice STARTED",
                phone_number=phone_number,
                invoice_number=invoice_data.get('invoice_number'),
                job_id=job_id,
                invoice_data_keys=list(invoice_data.keys())
            )
            
            # Ensure company exists
            logger.log_info("🔍 Checking if company exists...")
            company = await self.get_company(phone_number)
            if not company:
                logger.log_info(
                    "⚠️ Company not found, creating it NOW",
                    chat_id=phone_number,
                    customer_name=invoice_data.get('customer_name')
                )
                try:
                    created_company = await self.save_company(
                        chat_id=phone_number,
                        name=invoice_data.get('customer_name') or f"User {phone_number}",
                        plan="free",
                        limit_monthly=100,
                        registered_by="whatsapp_api"
                    )
                    
                    if not created_company:
                        logger.log_error(
                            "❌ save_company returned None - company creation failed",
                            phone_number=phone_number
                        )
                        raise Exception(f"Failed to create company for {phone_number}")
                    
                    logger.log_info(
                        "✅ Company created successfully",
                        created_company=created_company
                    )
                    
                    # Verify company exists now
                    verify_company = await self.get_company(phone_number)
                    if not verify_company:
                        logger.log_error(
                            "❌ Company still not found after creation",
                            phone_number=phone_number
                        )
                        raise Exception(f"Company verification failed for {phone_number}")
                    
                    logger.log_info("✅ Company verified", company=verify_company)
                    
                except Exception as e:
                    logger.log_error(
                        "❌ CRITICAL: Failed to create company - ABORTING invoice save",
                        error=str(e),
                        error_type=type(e).__name__,
                        phone_number=phone_number
                    )
                    import traceback
                    logger.log_error(
                        "📍 Traceback for company creation failure",
                        traceback=traceback.format_exc()
                    )
                    # Re-raise to stop invoice insertion
                    raise
            else:
                logger.log_info("✅ Company already exists", company_id=phone_number)
            
            # Safely convert numeric fields
            def safe_float(value, default=None):
                """Convert value to float, return default if conversion fails"""
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # Normalize RUC values ("0" or empty string -> None)
            def normalize_ruc(ruc_value):
                """Normalize RUC: convert '0', '', or invalid values to None"""
                if not ruc_value:
                    return None
                ruc_str = str(ruc_value).strip()
                if ruc_str == "0" or ruc_str == "" or len(ruc_str) < 8:
                    return None
                return ruc_str
            
            # Normalize and validate data
            supplier_ruc = normalize_ruc(invoice_data.get('supplier_ruc'))
            customer_ruc = normalize_ruc(invoice_data.get('customer_ruc'))
            
            logger.log_info(
                "🔧 DATA VALIDATION AND NORMALIZATION",
                original_supplier_ruc=invoice_data.get('supplier_ruc'),
                normalized_supplier_ruc=supplier_ruc,
                supplier_ruc_type=type(invoice_data.get('supplier_ruc')).__name__,
                original_customer_ruc=invoice_data.get('customer_ruc'),
                normalized_customer_ruc=customer_ruc,
                customer_ruc_type=type(invoice_data.get('customer_ruc')).__name__,
                subtotal=invoice_data.get('subtotal'),
                subtotal_type=type(invoice_data.get('subtotal')).__name__,
                igv=invoice_data.get('igv'),
                igv_type=type(invoice_data.get('igv')).__name__,
                total=invoice_data.get('total'),
                total_type=type(invoice_data.get('total')).__name__
            )
            
            # Prepare invoice data for database (Table 1: invoices)
            db_invoice = {
                "job_id": job_id,
                "company_id": phone_number,
                "record_id": None,  # NULL for single file processing
                "invoice_number": invoice_data.get('invoice_number'),
                "invoice_date": invoice_data.get('invoice_date'),
                "supplier_name": invoice_data.get('supplier_name'),
                "supplier_ruc": supplier_ruc,  # Normalized
                "customer_name": invoice_data.get('customer_name'),
                "customer_ruc": customer_ruc,  # Normalized
                "subtotal": safe_float(invoice_data.get('subtotal')),
                "tax": safe_float(invoice_data.get('igv')),
                "total": safe_float(invoice_data.get('total')),
                "currency": invoice_data.get('currency', 'PEN'),
                "confidence_score": safe_float(invoice_data.get('confidence_score'), 0.0),
                "source_file": invoice_data.get('source_file') or f"whatsapp_{phone_number}",
                "source_url": invoice_data.get('source_url'),
                "sequence_id": 1,  # Always 1 for single file processing
                "mime_type": invoice_data.get('mime_type'),
                "processing_status": 'success',
                "error_message": None
            }
            
            logger.log_info(
                "🔍 ABOUT TO INSERT TO 'invoices' TABLE",
                invoice_number=db_invoice['invoice_number'],
                supplier_ruc=db_invoice['supplier_ruc'],
                customer_ruc=db_invoice['customer_ruc'],
                total=db_invoice['total'],
                phone_number=phone_number
            )
            
            # Log complete db_invoice object for debugging
            import json
            logger.log_info(
                "📋 COMPLETE DB_INVOICE OBJECT",
                db_invoice=json.dumps(db_invoice, indent=2, default=str)
            )
            
            # Insert invoice to Table 1: invoices
            try:
                logger.log_info("⏳ Executing Supabase insert...")
                result = self.client.table("invoices").insert(db_invoice).execute()
                logger.log_info("✅ Supabase insert executed")
            except Exception as e:
                logger.log_error(
                    "Error inserting to invoices table",
                    error=str(e),
                    error_type=type(e).__name__,
                    db_invoice_keys=list(db_invoice.keys()),
                    invoice_number=db_invoice['invoice_number'],
                    supplier_ruc=db_invoice['supplier_ruc'],
                    customer_ruc=db_invoice['customer_ruc']
                )
                import traceback
                logger.log_error(
                    "Traceback for invoice insert error",
                    traceback=traceback.format_exc()
                )
                raise
            
            logger.log_info(
                "🔍 Checking result from Supabase...",
                has_data=bool(result.data),
                data_length=len(result.data) if result.data else 0
            )
            
            if not result.data or len(result.data) == 0:
                logger.log_error(
                    "❌ Failed to insert invoice - no data returned from Supabase",
                    phone_number=phone_number,
                    result_dict=result.__dict__ if hasattr(result, '__dict__') else str(result)
                )
                return None
            
            invoice_id = result.data[0]['id']
            
            logger.log_info(
                "✅ INVOICE SAVED TO 'invoices' TABLE",
                invoice_id=invoice_id,
                invoice_number=invoice_data.get('invoice_number'),
                supplier_name=invoice_data.get('supplier_name'),
                total=invoice_data.get('total')
            )
            
            # Save invoice items to Table 2: invoice_items
            items = invoice_data.get('items', [])
            if items and len(items) > 0:
                db_items = []
                for item_number, item in enumerate(items, 1):
                    # Map Spanish field names from WhatsApp to English database fields
                    db_item = {
                        "invoice_id": invoice_id,
                        "company_id": phone_number,
                        "item_number": item_number,
                        "description": item.get('descripcion'),
                        "quantity": safe_float(item.get('cantidad')),
                        "unit": item.get('unidad', 'UND'),
                        "unit_price": safe_float(item.get('precioUnitario')),
                        "total_price": safe_float(item.get('total'))
                    }
                    db_items.append(db_item)
                
                # Log items data before inserting
                logger.log_info(
                    "🔍 PREPARING TO INSERT INVOICE ITEMS",
                    invoice_id=invoice_id,
                    items_count=len(db_items)
                )
                
                import json
                logger.log_info(
                    "📋 ITEMS TO INSERT",
                    items=json.dumps(db_items, indent=2, default=str)
                )
                
                # Batch insert items to Table 2
                try:
                    logger.log_info("⏳ Executing Supabase insert for items...")
                    self.client.table("invoice_items").insert(db_items).execute()
                    logger.log_info(
                        "✅ INVOICE ITEMS SAVED to 'invoice_items' table",
                        invoice_id=invoice_id,
                        items_count=len(db_items)
                    )
                except Exception as e:
                    logger.log_error(
                        "Error inserting invoice items, but invoice was saved",
                        error=str(e),
                        error_type=type(e).__name__,
                        invoice_id=invoice_id,
                        items_count=len(db_items)
                    )
                    import traceback
                    logger.log_error(
                        "Traceback for items insert error",
                        traceback=traceback.format_exc()
                    )
                    # Don't fail the whole operation if items fail
            else:
                logger.log_info(
                    "No items to save for this invoice (empty items array)",
                    invoice_id=invoice_id
                )
            
            logger.log_info(
                "🎉 SUPABASE SERVICE: save_single_invoice COMPLETED SUCCESSFULLY",
                invoice_id=invoice_id,
                phone_number=phone_number,
                job_id=job_id,
                items_count=len(items) if items else 0
            )
            
            return invoice_id
            
        except Exception as e:
            logger.log_error(
                "❌ EXCEPTION IN save_single_invoice",
                phone_number=phone_number,
                error=str(e),
                error_type=type(e).__name__,
                invoice_number=invoice_data.get('invoice_number')
            )
            import traceback
            logger.log_error(
                "📍 FULL TRACEBACK FROM save_single_invoice",
                traceback=traceback.format_exc()
            )
            return None


# Global instance
supabase_service = SupabaseService()

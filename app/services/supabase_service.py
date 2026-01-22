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
            return None
        
        try:
            data = {
                "chat_id": chat_id,
                "name": name,
                "plan": plan,
                "limit_monthly": limit_monthly,
                "usage": 0,
                "active": True
            }
            
            if registered_by:
                data["registered_by"] = registered_by
            
            # Upsert: insert or update if exists
            result = self.client.table("companies").upsert(
                data,
                on_conflict="chat_id"
            ).execute()
            
            logger.log_info(
                "Company saved to database",
                chat_id=chat_id,
                name=name,
                plan=plan
            )
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.log_error(
                "Failed to save company",
                chat_id=chat_id,
                error=str(e)
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
            return None
        
        try:
            result = self.client.table("companies").select("*").eq(
                "chat_id", chat_id
            ).execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.log_error(
                "Failed to get company",
                chat_id=chat_id,
                error=str(e)
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


# Global instance
supabase_service = SupabaseService()

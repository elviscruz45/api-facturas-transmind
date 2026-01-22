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
        company_id: str,
        name: str,
        plan: str = "free",
        limit_monthly: int = 100
    ) -> Optional[Dict]:
        """
        Save or update company information
        
        Args:
            company_id: Unique identifier (e.g., chat_id from Telegram)
            name: Company name
            plan: Subscription plan (free/pro/enterprise)
            limit_monthly: Monthly invoice processing limit
            
        Returns:
            Company record or None if failed
        """
        if not self.is_enabled():
            return None
        
        try:
            data = {
                "company_id": company_id,
                "name": name,
                "plan": plan,
                "limit_monthly": limit_monthly,
                "usage_current_month": 0,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Upsert: insert or update if exists
            result = self.client.table("companies").upsert(
                data,
                on_conflict="company_id"
            ).execute()
            
            logger.log_info(
                "Company saved to database",
                company_id=company_id,
                name=name,
                plan=plan
            )
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.log_error(
                "Failed to save company",
                company_id=company_id,
                error=str(e)
            )
            return None
    
    async def get_company(self, company_id: str) -> Optional[Dict]:
        """
        Get company by ID
        
        Args:
            company_id: Company identifier
            
        Returns:
            Company record or None if not found
        """
        if not self.is_enabled():
            return None
        
        try:
            result = self.client.table("companies").select("*").eq(
                "company_id", company_id
            ).execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.log_error(
                "Failed to get company",
                company_id=company_id,
                error=str(e)
            )
            return None
    
    async def increment_company_usage(
        self,
        company_id: str,
        invoices_count: int
    ) -> bool:
        """
        Increment company's monthly usage counter
        
        Args:
            company_id: Company identifier
            invoices_count: Number of invoices to add to usage
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            # Atomic increment using PostgreSQL function
            result = self.client.rpc(
                "increment_usage",
                {
                    "p_company_id": company_id,
                    "p_count": invoices_count
                }
            ).execute()
            
            logger.log_info(
                "Company usage incremented",
                company_id=company_id,
                count=invoices_count
            )
            
            return True
            
        except Exception as e:
            # Fallback to manual increment if RPC not available
            logger.log_warning(
                "RPC increment failed, using fallback",
                company_id=company_id,
                error=str(e)
            )
            
            try:
                company = await self.get_company(company_id)
                if company:
                    new_usage = company.get("usage_current_month", 0) + invoices_count
                    self.client.table("companies").update({
                        "usage_current_month": new_usage
                    }).eq("company_id", company_id).execute()
                    return True
            except Exception as fallback_error:
                logger.log_error(
                    "Failed to increment usage (fallback)",
                    company_id=company_id,
                    error=str(fallback_error)
                )
            
            return False
    
    async def save_processing_record(
        self,
        company_id: Optional[str],
        zip_filename: str,
        zip_blob_path: Optional[str],
        excel_blob_path: Optional[str],
        total_invoices: int,
        success_count: int,
        error_count: int
    ) -> Optional[str]:
        """
        Save processing record
        
        Args:
            company_id: Company identifier (None for anonymous)
            zip_filename: Original ZIP filename
            zip_blob_path: Cloud Storage path to ZIP
            excel_blob_path: Cloud Storage path to Excel
            total_invoices: Total invoices processed
            success_count: Successfully extracted invoices
            error_count: Number of errors
            
        Returns:
            Record ID (UUID) or None if failed
        """
        if not self.is_enabled():
            return None
        
        try:
            record_id = str(uuid.uuid4())
            
            data = {
                "id": record_id,
                "company_id": company_id,
                "zip_filename": zip_filename,
                "zip_blob_path": zip_blob_path,
                "excel_blob_path": excel_blob_path,
                "total_invoices": total_invoices,
                "success_count": success_count,
                "error_count": error_count,
                "processed_at": datetime.utcnow().isoformat()
            }
            
            result = self.client.table("processing_records").insert(data).execute()
            
            logger.log_info(
                "Processing record saved",
                record_id=record_id,
                company_id=company_id,
                total_invoices=total_invoices
            )
            
            return record_id
            
        except Exception as e:
            logger.log_error(
                "Failed to save processing record",
                company_id=company_id,
                error=str(e)
            )
            return None
    
    async def save_invoices_batch(
        self,
        invoices: List[Dict],
        company_id: Optional[str],
        record_id: str
    ) -> bool:
        """
        Save batch of invoices to database
        
        Args:
            invoices: List of invoice dictionaries from ProcessingResponse
            company_id: Company identifier
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
                # Handle items as JSONB array
                items_json = []
                if hasattr(invoice, 'items') and invoice.items:
                    for item in invoice.items:
                        items_json.append({
                            "description": item.description if hasattr(item, 'description') else None,
                            "quantity": item.quantity if hasattr(item, 'quantity') else None,
                            "unit": item.unit if hasattr(item, 'unit') else None,
                            "unit_price": float(item.unit_price) if hasattr(item, 'unit_price') and item.unit_price else None,
                            "total_price": float(item.total_price) if hasattr(item, 'total_price') and item.total_price else None
                        })
                
                db_invoice = {
                    "company_id": company_id,
                    "record_id": record_id,
                    "invoice_number": invoice.invoice_number if hasattr(invoice, 'invoice_number') else None,
                    "invoice_date": invoice.invoice_date if hasattr(invoice, 'invoice_date') else None,
                    "supplier_name": invoice.supplier_name if hasattr(invoice, 'supplier_name') else None,
                    "supplier_ruc": invoice.supplier_ruc if hasattr(invoice, 'supplier_ruc') else None,
                    "customer_name": invoice.customer_name if hasattr(invoice, 'customer_name') else None,
                    "customer_ruc": invoice.customer_ruc if hasattr(invoice, 'customer_ruc') else None,
                    "subtotal": float(invoice.subtotal) if hasattr(invoice, 'subtotal') and invoice.subtotal else None,
                    "tax": float(invoice.tax) if hasattr(invoice, 'tax') and invoice.tax else None,
                    "total": float(invoice.total) if hasattr(invoice, 'total') and invoice.total else None,
                    "currency": invoice.currency if hasattr(invoice, 'currency') else "PEN",
                    "items": items_json,
                    "confidence_score": invoice.confidence_score if hasattr(invoice, 'confidence_score') else None,
                    "source_file": invoice.source_file if hasattr(invoice, 'source_file') else None,
                    "sequence_id": invoice.sequence_id if hasattr(invoice, 'sequence_id') else None,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                db_invoices.append(db_invoice)
            
            # Batch insert
            result = self.client.table("invoices").insert(db_invoices).execute()
            
            logger.log_info(
                "Invoices saved to database",
                count=len(db_invoices),
                company_id=company_id,
                record_id=record_id
            )
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to save invoices batch",
                company_id=company_id,
                record_id=record_id,
                count=len(invoices),
                error=str(e)
            )
            return False
    
    async def get_company_invoices(
        self,
        company_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get invoices for a company (paginated)
        
        Args:
            company_id: Company identifier
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of invoice records
        """
        if not self.is_enabled():
            return []
        
        try:
            result = self.client.table("invoices").select("*").eq(
                "company_id", company_id
            ).order(
                "created_at", desc=True
            ).range(offset, offset + limit - 1).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.log_error(
                "Failed to get company invoices",
                company_id=company_id,
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

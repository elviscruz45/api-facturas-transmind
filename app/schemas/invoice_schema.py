from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import re

class InvoiceItemSchema(BaseModel):
    """Schema for individual line items in an invoice"""
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    unit: Optional[str] = None  # e.g., "unidad", "kg", "metro", etc.

class InvoiceSchema(BaseModel):
    """Unified JSON schema for invoice extraction - Phase 5"""
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None  # ISO format date string
    supplier_name: Optional[str] = None
    supplier_ruc: Optional[str] = None
    customer_name: Optional[str] = None
    items: Optional[List[InvoiceItemSchema]] = None  # List of line items
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    confidence_score: float = 0.0
    source_file: str
    sequence_id: int
    
    @validator('supplier_ruc')
    def validate_ruc(cls, v):
        """Validate RUC format (basic validation)"""
        if v and not re.match(r'^\d{11}$', v.replace('-', '').replace('.', '')):
            # Don't raise error, just note it's invalid format
            pass
        return v
    
    @validator('invoice_date')
    def validate_date(cls, v):
        """Validate date format"""
        if v:
            try:
                # Try to parse the date to validate format
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                # Don't raise error, keep original value
                pass
        return v
    
    @validator('confidence_score')
    def validate_confidence(cls, v):
        """Ensure confidence score is between 0 and 1"""
        return max(0.0, min(1.0, v))

class ProcessingResponse(BaseModel):
    """Response model for the complete processing pipeline"""
    results: List[InvoiceSchema]
    errors: List[dict]
    total_processed: int
    success_count: int

class WhatsAppInvoiceItem(BaseModel):
    """Item model for WhatsApp invoice data (Spanish field names)"""
    descripcion: Optional[str] = None
    cantidad: Optional[float] = None
    precioUnitario: Optional[float] = None
    total: Optional[float] = None
    unidad: Optional[str] = None

class SaveInvoiceRequest(BaseModel):
    """Request model for saving invoice data from WhatsApp API"""
    # Main invoice fields (English/snake_case from WhatsApp)
    supplier_ruc: Optional[str] = None
    supplier_name: Optional[str] = None
    customer_ruc: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_number: Optional[str] = None
    subtotal: Optional[float] = None
    igv: Optional[float] = None  # IGV/Tax
    total: Optional[float] = None
    currency: Optional[str] = "PEN"
    
    # Items (Spanish field names)
    items: Optional[List[WhatsAppInvoiceItem]] = None
    
    # Metadata
    confidence_score: Optional[float] = 0.0
    phoneNumber: str  # Required field
    source_file: Optional[str] = None
    source_url: Optional[str] = None
    mime_type: Optional[str] = None
    job_id: Optional[str] = None
    createdAt: Optional[str] = None

class SaveInvoiceResponse(BaseModel):
    """Response model for saved invoice"""
    id: int
    success: bool = True
    message: str = "Invoice saved successfully"
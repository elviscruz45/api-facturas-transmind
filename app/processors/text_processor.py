import chardet
from typing import Optional, Dict
from config import settings
from app.utils.logger import setup_logger

logger = setup_logger("text_processor")

class TextProcessor:
    """Phase 4: Process text files for invoice extraction"""
    
    def __init__(self):
        self.encoding_fallback_sequence = settings.encoding_fallback_sequence
    
    def extract_text_content(self, file_path: str) -> Optional[str]:
        """Extract and normalize text content from file"""
        
        for encoding in self.encoding_fallback_sequence:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                
                # Normalize content
                normalized_content = self.normalize_text(content)
                
                logger.log_file_processing(
                    filename=file_path,
                    sequence_id=0,
                    file_type="text",
                    status="content_extracted",
                    encoding=encoding,
                    content_length=len(normalized_content)
                )
                
                return normalized_content
                
            except UnicodeDecodeError:
                logger.log_warning(
                    "Encoding failed, trying next",
                    filename=file_path,
                    encoding=encoding
                )
                continue
            except Exception as e:
                logger.log_error(
                    "Text extraction failed",
                    filename=file_path,
                    encoding=encoding,
                    error=str(e)
                )
                break
        
        return None
    
    def normalize_text(self, content: str) -> str:
        """Normalize text content"""
        if not content:
            return ""
        
        # Remove excessive whitespace
        normalized = ' '.join(content.split())
        
        # Remove non-printable characters but keep basic formatting
        normalized = ''.join(char if char.isprintable() or char in '\n\r\t' else ' ' for char in normalized)
        
        # Collapse multiple spaces
        while '  ' in normalized:
            normalized = normalized.replace('  ', ' ')
        
        return normalized.strip()
    
    def is_potential_invoice_text(self, content: str) -> bool:
        """Check if text content might contain invoice information"""
        if not content:
            return False
        
        content_lower = content.lower()
        
        # Common invoice keywords in Spanish/English
        invoice_keywords = [
            'factura', 'invoice', 'ruc', 'total', 'subtotal', 'igv', 'tax',
            'fecha', 'date', 'cliente', 'customer', 'proveedor', 'supplier',
            'numero', 'number', 'boleta', 'receipt', 'comprobante'
        ]
        
        # Check if any invoice keywords are present
        keyword_found = any(keyword in content_lower for keyword in invoice_keywords)
        
        # Check for numeric patterns (amounts, RUC, etc.)
        import re
        numeric_patterns = bool(re.search(r'\d{2,}', content))
        
        is_potential = keyword_found and numeric_patterns
        
        return is_potential
    
    def process_text_file(self, file_path: str) -> Dict:
        """Main method to process text file"""
        try:
            # Extract content
            content = self.extract_text_content(file_path)
            
            if not content:
                return {
                    "success": False,
                    "error": "Failed to extract text content",
                    "content": None
                }
            
            # Check if it's potentially an invoice
            is_potential_invoice = self.is_potential_invoice_text(content)
            
            return {
                "success": True,
                "content": content,
                "is_potential_invoice": is_potential_invoice,
                "content_length": len(content)
            }
            
        except Exception as e:
            logger.log_error(
                "Text file processing failed",
                filename=file_path,
                error=str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "content": None
            }
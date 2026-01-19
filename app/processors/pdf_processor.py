import PyPDF2
import pdfplumber
from PIL import Image
import io
from typing import Optional, Dict, List
from app.utils.logger import setup_logger

logger = setup_logger("pdf_processor")

class PDFProcessor:
    """Phase 4: Process PDF files - detect text vs scanned and extract accordingly"""
    
    def __init__(self):
        self.min_chars_per_page = 50  # Minimum characters to consider text-based PDF
        self.max_pages_to_process = 10  # Limit pages for processing
    
    def is_text_based_pdf(self, file_path: str) -> tuple[bool, Dict]:
        """Detect if PDF contains text or is scanned (image-based)"""
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                total_chars = 0
                pages_with_text = 0
                
                # Check first few pages
                pages_to_check = min(self.max_pages_to_process, total_pages)
                
                for i in range(pages_to_check):
                    page = pdf.pages[i]
                    page_text = page.extract_text() or ""
                    page_chars = len(page_text.strip())
                    
                    total_chars += page_chars
                    if page_chars >= self.min_chars_per_page:
                        pages_with_text += 1
                
                # Calculate ratios
                avg_chars_per_page = total_chars / pages_to_check if pages_to_check > 0 else 0
                text_page_ratio = pages_with_text / pages_to_check if pages_to_check > 0 else 0
                
                # PDF is considered text-based if:
                # - Average characters per page > threshold
                # - At least 50% of pages have significant text
                is_text_based = (avg_chars_per_page >= self.min_chars_per_page and 
                                text_page_ratio >= 0.5)
                
                analysis_result = {
                    "total_pages": total_pages,
                    "pages_checked": pages_to_check,
                    "total_characters": total_chars,
                    "avg_chars_per_page": avg_chars_per_page,
                    "pages_with_text": pages_with_text,
                    "text_page_ratio": text_page_ratio,
                    "is_text_based": is_text_based
                }
                
                logger.log_file_processing(
                    filename=file_path,
                    sequence_id=0,
                    file_type="pdf",
                    status="analyzed",
                    **analysis_result
                )
                
                return is_text_based, analysis_result
                
        except Exception as e:
            logger.log_error(
                "PDF analysis failed",
                filename=file_path,
                error=str(e)
            )
            return False, {"error": str(e)}
    
    def extract_text_from_pdf(self, file_path: str) -> Optional[str]:
        """Extract text directly from text-based PDF"""
        try:
            extracted_text = []
            
            with pdfplumber.open(file_path) as pdf:
                pages_to_process = min(self.max_pages_to_process, len(pdf.pages))
                
                for i in range(pages_to_process):
                    page = pdf.pages[i]
                    page_text = page.extract_text()
                    
                    if page_text:
                        extracted_text.append(page_text.strip())
            
            # Join all text
            full_text = "\n\n".join(extracted_text)
            
            # Normalize text
            normalized_text = self.normalize_pdf_text(full_text)
            
            logger.log_file_processing(
                filename=file_path,
                sequence_id=0,
                file_type="pdf",
                status="text_extracted",
                pages_processed=pages_to_process,
                text_length=len(normalized_text)
            )
            
            return normalized_text
            
        except Exception as e:
            logger.log_error(
                "PDF text extraction failed",
                filename=file_path,
                error=str(e)
            )
            return None
    
    def normalize_pdf_text(self, text: str) -> str:
        """Normalize extracted PDF text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        normalized = ' '.join(text.split())
        
        # Remove non-printable characters but keep basic formatting
        normalized = ''.join(char if char.isprintable() or char in '\n\r\t' else ' ' for char in normalized)
        
        # Collapse multiple spaces
        while '  ' in normalized:
            normalized = normalized.replace('  ', ' ')
        
        return normalized.strip()
    
    def process_pdf_file(self, file_path: str) -> Dict:
        """Main method to process PDF file"""
        try:
            # First, analyze if PDF is text-based or scanned
            is_text_based, analysis = self.is_text_based_pdf(file_path)
            
            if is_text_based:
                # Extract text directly
                extracted_text = self.extract_text_from_pdf(file_path)
                
                if extracted_text:
                    return {
                        "success": True,
                        "processing_type": "text_extraction",
                        "content": extracted_text,
                        "analysis": analysis,
                        "requires_ocr": False
                    }
                else:
                    # Text extraction failed, treat as scanned
                    is_text_based = False
            
            if not is_text_based:
                # For MVP, we'll skip image conversion and just return an error
                # This can be implemented later with PyMuPDF
                return {
                    "success": False,
                    "error": "Scanned PDF processing not implemented in MVP",
                    "analysis": analysis,
                    "requires_ocr": True
                }
            
        except Exception as e:
            logger.log_error(
                "PDF processing failed",
                filename=file_path,
                error=str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "requires_ocr": False
            }
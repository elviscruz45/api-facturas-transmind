import zipfile
import tempfile
import os
import io
from pathlib import Path
from typing import List, Dict, Tuple
import magic
from config import settings
from app.utils.logger import setup_logger

logger = setup_logger("zip_handler")

class ZipHandler:
    """Phase 1: ZIP file ingesión and validation"""
    
    def __init__(self):
        self.max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        self.allowed_extensions = settings.allowed_extensions
        self.irrelevant_patterns = [
            'sticker', 'thumbnail', '.gif', '.webp', 
            '.mp3', '.opus', '.m4a', '.aac'
        ]
    
    def validate_zip_file(self, file_content: bytes, filename: str) -> Tuple[bool, str]:
        """Validate ZIP file size, type and structure"""
        
        # Check file size
        if len(file_content) > self.max_size_bytes:
            return False, f"File size ({len(file_content)} bytes) exceeds maximum allowed ({self.max_size_bytes} bytes)"
        
        # Check if it's a valid ZIP file
        try:
            # Try to read ZIP structure
            with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zip_ref:
                # Test ZIP integrity
                bad_file = zip_ref.testzip()
                if bad_file:
                    return False, f"Corrupted ZIP file: {bad_file}"
                
                # Check if ZIP has any files
                file_list = zip_ref.namelist()
                if not file_list:
                    return False, "ZIP file is empty"
                
                logger.log_info(
                    "ZIP file validation successful",
                    filename=filename,
                    total_files=len(file_list),
                    size_bytes=len(file_content)
                )
                
                return True, "Valid ZIP file"
        
        except zipfile.BadZipFile:
            return False, "Invalid ZIP file format"
        except Exception as e:
            return False, f"Error validating ZIP file: {str(e)}"
    
    def is_relevant_file(self, filename: str) -> bool:
        """Check if file is relevant for processing (not sticker, thumbnail, etc.)"""
        filename_lower = filename.lower()
        
        # Check for irrelevant patterns
        for pattern in self.irrelevant_patterns:
            if pattern in filename_lower:
                return False
        
        # Check for allowed extensions
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            return False
        
        # Additional WhatsApp-specific filters
        if filename_lower.startswith('.'):  # Hidden files
            return False
        
        if 'whatsapp audio' in filename_lower and file_ext in ['.opus', '.m4a']:
            # Skip short audio files (typically < 5 seconds)
            return False
        
        return True

    def extract_zip_files(self, file_content: bytes, filename: str) -> Tuple[bool, Dict]:
        """Extract ZIP files to temporary directory with validation"""
        
        # Validate ZIP first
        is_valid, message = self.validate_zip_file(file_content, filename)
        if not is_valid:
            return False, {"error": message}

        extracted_files = []
        ignored_files = []
        temp_dir_obj = None

        try:
            # Create temporary directory for extraction (don't use 'with' - cleanup later)
            temp_dir_obj = tempfile.TemporaryDirectory(prefix="invoice_zip_")
            temp_dir = temp_dir_obj.name
            
            with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zip_ref:
                file_list = zip_ref.namelist()
                
                for zip_file in file_list:
                    # Skip directories
                    if zip_file.endswith('/'):
                        continue
                    
                    # Check if file is relevant
                    if not self.is_relevant_file(zip_file):
                        ignored_files.append({
                            "filename": zip_file,
                            "reason": "irrelevant file type or pattern"
                        })
                        continue
                    
                    try:
                        # Extract file
                        extracted_path = zip_ref.extract(zip_file, temp_dir)
                        
                        # Get file info
                        file_stat = os.stat(extracted_path)
                        
                        # Verify MIME type
                        mime_type = magic.from_file(extracted_path, mime=True)
                        
                        extracted_files.append({
                            "original_name": zip_file,
                            "extracted_path": extracted_path,
                            "size_bytes": file_stat.st_size,
                            "mime_type": mime_type,
                            "modified_time": file_stat.st_mtime
                        })
                        
                        logger.log_file_processing(
                            filename=zip_file,
                            sequence_id=len(extracted_files),
                            file_type="extracted",
                            status="extracted_successfully",
                            mime_type=mime_type,
                            size_bytes=file_stat.st_size
                        )
                    
                    except Exception as e:
                        ignored_files.append({
                            "filename": zip_file,
                            "reason": f"extraction error: {str(e)}"
                        })
            
            logger.log_info(
                "ZIP extraction completed",
                total_extracted=len(extracted_files),
                total_ignored=len(ignored_files),
                temp_dir=temp_dir
            )
            
            return True, {
                "extracted_files": extracted_files,
                "ignored_files": ignored_files,
                "temp_dir": temp_dir,
                "temp_dir_obj": temp_dir_obj,  # Return for cleanup later
                "total_extracted": len(extracted_files),
                "total_ignored": len(ignored_files)
            }
        
        except Exception as e:
            # Cleanup temp dir if error occurs
            if temp_dir_obj:
                temp_dir_obj.cleanup()
            
            logger.log_error(
                "ZIP extraction failed",
                filename=filename,
                error=str(e)
            )
            return False, {"error": f"ZIP extraction failed: {str(e)}"}
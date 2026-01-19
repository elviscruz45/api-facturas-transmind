import magic
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple
from app.models.file_index import FileIndex, FileRecord
from app.utils.logger import setup_logger

logger = setup_logger("file_classifier")

class FileClassifier:
    """Phase 3: Classify files by content type with metadata extraction"""
    
    def __init__(self):
        # File type mappings
        self.type_mappings = {
            '.txt': 'text',
            '.jpg': 'image', 
            '.jpeg': 'image',
            '.png': 'image',
            '.pdf': 'pdf'
        }
        
        # MIME type validation
        self.expected_mime_types = {
            'text': ['text/plain', 'text/utf-8'],
            'image': ['image/jpeg', 'image/png', 'image/jpg'],
            'pdf': ['application/pdf']
        }
    
    def generate_file_hash(self, file_path: str) -> str:
        """Generate SHA-256 hash for deduplication"""
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                return hashlib.sha256(file_content).hexdigest()
        except Exception as e:
            logger.log_error(
                "Failed to generate file hash",
                file_path=file_path,
                error=str(e)
            )
            return ""
    
    def detect_mime_type(self, file_path: str) -> str:
        """Detect MIME type using python-magic"""
        try:
            mime_type = magic.from_file(file_path, mime=True)
            logger.log_file_processing(
                filename=Path(file_path).name,
                sequence_id=0,
                file_type="mime_detection",
                status="detected",
                mime_type=mime_type
            )
            return mime_type
        except Exception as e:
            logger.log_error(
                "MIME type detection failed",
                file_path=file_path,
                error=str(e)
            )
            return "application/octet-stream"  # Default binary type
    
    def classify_file_type(self, filename: str, mime_type: str) -> str:
        """Classify file type based on extension and MIME type"""
        
        # Get file extension
        file_ext = Path(filename).suffix.lower()
        
        # Primary classification by extension
        file_type = self.type_mappings.get(file_ext, 'other')
        
        # Validate with MIME type
        if file_type != 'other':
            expected_mimes = self.expected_mime_types.get(file_type, [])
            if expected_mimes and mime_type not in expected_mimes:
                logger.log_warning(
                    "MIME type mismatch",
                    filename=filename,
                    file_extension=file_ext,
                    expected_file_type=file_type,
                    actual_mime_type=mime_type,
                    expected_mime_types=expected_mimes
                )
                # Don't change classification, just log the mismatch
        
        return file_type
    
    def classify_files(self, file_indices: List[FileIndex]) -> Dict[str, List[FileRecord]]:
        """Classify all files and organize by type"""
        
        classified_files = {
            'text': [],
            'image': [],
            'pdf': [],
            'other': []
        }
        
        duplicate_hashes = set()
        
        for file_index in file_indices:
            try:
                # Detect MIME type
                mime_type = self.detect_mime_type(file_index.file_path)
                
                # Classify file type
                file_type = self.classify_file_type(file_index.filename, mime_type)
                
                # Generate hash for deduplication
                file_hash = self.generate_file_hash(file_index.file_path)
                
                # Check for duplicates
                if file_hash in duplicate_hashes:
                    logger.log_warning(
                        "Duplicate file detected",
                        filename=file_index.filename,
                        sequence_id=file_index.sequence_id,
                        hash=file_hash,
                        status="skipped_duplicate"
                    )
                    continue
                
                duplicate_hashes.add(file_hash)
                
                # Create FileRecord
                file_record = FileRecord(
                    sequence_id=file_index.sequence_id,
                    filename=file_index.filename,
                    file_type=file_type,
                    mime_type=mime_type,
                    hash=file_hash,
                    file_path=file_index.file_path,
                    file_size=file_index.file_size
                )
                
                # Add to appropriate category
                classified_files[file_type].append(file_record)
                
                logger.log_file_processing(
                    filename=file_index.filename,
                    sequence_id=file_index.sequence_id,
                    file_type=file_type,
                    status="classified",
                    mime_type=mime_type,
                    hash=file_hash[:8] + "...",  # Truncated hash for logging
                    file_size=file_index.file_size
                )
                
            except Exception as e:
                logger.log_error(
                    "File classification failed",
                    filename=file_index.filename,
                    sequence_id=file_index.sequence_id,
                    error=str(e)
                )
                
                # Create record for failed classification
                file_record = FileRecord(
                    sequence_id=file_index.sequence_id,
                    filename=file_index.filename,
                    file_type='other',
                    mime_type='application/octet-stream',
                    hash='',
                    file_path=file_index.file_path,
                    file_size=file_index.file_size
                )
                
                classified_files['other'].append(file_record)
        
        # Log classification summary
        total_files = sum(len(files) for files in classified_files.values())
        logger.log_info(
            "File classification completed",
            total_files=total_files,
            text_files=len(classified_files['text']),
            image_files=len(classified_files['image']),
            pdf_files=len(classified_files['pdf']),
            other_files=len(classified_files['other'])
        )
        
        return classified_files
    
    def get_processable_files(self, classified_files: Dict[str, List[FileRecord]]) -> List[FileRecord]:
        """Get all files that can be processed for invoice extraction"""
        
        processable_files = []
        
        # Text, image, and PDF files are processable
        for file_type in ['text', 'image', 'pdf']:
            processable_files.extend(classified_files[file_type])

        # Sort by sequence_id to maintain chronological order
        processable_files.sort(key=lambda x: x.sequence_id)
        
        logger.log_info(
            "Processable files identified",
            total_processable=len(processable_files),
            other_files_skipped=len(classified_files['other'])
        )
        
        return processable_files
    
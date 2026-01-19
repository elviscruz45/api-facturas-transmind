import re
import os
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from pathlib import Path
from app.models.file_index import FileIndex
from app.utils.logger import setup_logger

logger = setup_logger("file_sorter")

class FileSorter:
    """Phase 2: Determine chronological order of files using WhatsApp timestamps"""
    
    def __init__(self):
        # WhatsApp filename patterns
        self.whatsapp_patterns = [
            r'IMG-(\d{8})-WA(\d{4})',     # IMG-YYYYMMDD-WA####.jpg
            r'VID-(\d{8})-WA(\d{4})',     # VID-YYYYMMDD-WA####.mp4
            r'AUD-(\d{8})-WA(\d{4})',     # AUD-YYYYMMDD-WA####.opus
            r'DOC-(\d{8})-WA(\d{4})',     # DOC-YYYYMMDD-WA####.pdf
            r'PTT-(\d{8})-WA(\d{4})',     # PTT-YYYYMMDD-WA####.opus (voice notes)
        ]
    
    def parse_whatsapp_timestamp(self, filename: str) -> Optional[datetime]:
        """Extract timestamp from WhatsApp filename pattern"""
        
        for pattern in self.whatsapp_patterns:
            match = re.search(pattern, filename)
            if match:
                date_str = match.group(1)  # YYYYMMDD
                sequence = match.group(2)  # WA####
                
                try:
                    # Parse date part
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    
                    # Create datetime with sequence as microseconds for sub-second ordering
                    sequence_num = int(sequence)
                    microseconds = min(sequence_num * 1000, 999999)  # Max microseconds is 999999
                    
                    parsed_date = datetime(year, month, day, 0, 0, 0, microseconds)
                    
                    logger.log_file_processing(
                        filename=filename,
                        sequence_id=0,  # Will be assigned later
                        file_type="timestamp_parsed",
                        status="whatsapp_timestamp_found",
                        parsed_timestamp=parsed_date.isoformat(),
                        pattern_matched=pattern
                    )
                    
                    return parsed_date
                
                except (ValueError, IndexError) as e:
                    logger.log_warning(
                        "Invalid date in WhatsApp filename",
                        filename=filename,
                        date_str=date_str,
                        error=str(e)
                    )
                    continue
        
        return None
    
    def get_filesystem_timestamp(self, file_path: str) -> Optional[datetime]:
        """Get file modification/creation timestamp as fallback"""
        try:
            stat = os.stat(file_path)
            
            # Use modification time, fallback to creation time
            timestamp = stat.st_mtime
            if hasattr(stat, 'st_birthtime'):  # macOS
                timestamp = min(stat.st_mtime, stat.st_birthtime)
            elif hasattr(stat, 'st_ctime'):   # Windows creation time
                timestamp = min(stat.st_mtime, stat.st_ctime)
            
            return datetime.fromtimestamp(timestamp)
        
        except OSError as e:
            logger.log_error(
                "Failed to get filesystem timestamp",
                file_path=file_path,
                error=str(e)
            )
            return None
    
    def sort_files_chronologically(self, extracted_files: List[Dict]) -> List[FileIndex]:
        """Sort files chronologically and assign sequence IDs"""
        
        file_indices = []
        
        for idx, file_info in enumerate(extracted_files):
            filename = file_info["original_name"]
            file_path = file_info["extracted_path"]
            
            # Try to parse WhatsApp timestamp first
            whatsapp_timestamp = self.parse_whatsapp_timestamp(filename)
            
            # Get filesystem timestamp as fallback
            fs_timestamp = self.get_filesystem_timestamp(file_path)
            
            # Determine which timestamp to use
            if whatsapp_timestamp:
                final_timestamp = whatsapp_timestamp
                timestamp_source = "whatsapp_filename"
            elif fs_timestamp:
                final_timestamp = fs_timestamp
                timestamp_source = "filesystem"
            else:
                # Use current time as last resort
                final_timestamp = datetime.now()
                timestamp_source = "current_time"
                
                logger.log_warning(
                    "No timestamp found, using current time",
                    filename=filename,
                    file_path=file_path
                )
            
            file_index = FileIndex(
                sequence_id=0,  # Will be assigned after sorting
                filename=filename,
                original_timestamp=whatsapp_timestamp,
                parsed_timestamp=final_timestamp,
                file_path=file_path,
                file_size=file_info.get("size_bytes", 0)
            )
            
            file_indices.append((final_timestamp, file_index, timestamp_source))
        
        # Sort by timestamp
        file_indices.sort(key=lambda x: x[0])
        
        # Assign sequence IDs maintaining chronological order
        sorted_file_indices = []
        for idx, (timestamp, file_index, source) in enumerate(file_indices, 1):
            file_index.sequence_id = idx
            sorted_file_indices.append(file_index)
            
            logger.log_file_processing(
                filename=file_index.filename,
                sequence_id=file_index.sequence_id,
                file_type="chronological_sort",
                status="sequence_assigned",
                timestamp_source=source,
                final_timestamp=timestamp.isoformat()
            )
        
        logger.log_info(
            "Files sorted chronologically",
            total_files=len(sorted_file_indices),
            first_file=sorted_file_indices[0].filename if sorted_file_indices else None,
            last_file=sorted_file_indices[-1].filename if sorted_file_indices else None
        )
        
        return sorted_file_indices
    
    def validate_chronological_order(self, file_indices: List[FileIndex]) -> bool:
        """Validate that files are properly ordered chronologically"""
        
        for i in range(1, len(file_indices)):
            current_file = file_indices[i]
            previous_file = file_indices[i-1]
            
            # Check sequence ID order
            if current_file.sequence_id <= previous_file.sequence_id:
                logger.log_error(
                    "Sequence ID order violation",
                    current_file=current_file.filename,
                    current_seq=current_file.sequence_id,
                    previous_file=previous_file.filename,
                    previous_seq=previous_file.sequence_id
                )
                return False
            
            # Check timestamp order
            if (current_file.parsed_timestamp and previous_file.parsed_timestamp and 
                current_file.parsed_timestamp < previous_file.parsed_timestamp):
                logger.log_warning(
                    "Timestamp order inconsistency",
                    current_file=current_file.filename,
                    current_timestamp=current_file.parsed_timestamp.isoformat(),
                    previous_file=previous_file.filename,
                    previous_timestamp=previous_file.parsed_timestamp.isoformat()
                )
        
        return True
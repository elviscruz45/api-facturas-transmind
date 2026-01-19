from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import hashlib

class FileIndex(BaseModel):
    """Model for tracking files with chronological order from WhatsApp"""
    sequence_id: int
    filename: str
    original_timestamp: Optional[datetime] = None
    parsed_timestamp: Optional[datetime] = None
    file_path: str
    file_size: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class FileRecord(BaseModel):
    """Model for classified files with metadata - Phase 3"""
    sequence_id: int
    filename: str
    file_type: str  # 'text', 'image', 'pdf', 'other'
    mime_type: str
    hash: str
    file_path: str
    file_size: int
    
    @classmethod
    def create_hash(cls, file_content: bytes) -> str:
        """Generate SHA-256 hash for deduplication"""
        return hashlib.sha256(file_content).hexdigest()
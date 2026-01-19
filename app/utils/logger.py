import logging
import json
from datetime import datetime
from typing import Any, Dict

class StructuredLogger:
    """Structured logger for the invoice processing pipeline"""
    
    def __init__(self, name: str = "invoice_processor"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create console handler with structured format
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _log_structured(self, level: str, message: str, **kwargs):
        """Log structured data"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        
        if level.lower() == "error":
            self.logger.error(json.dumps(log_data))
        elif level.lower() == "warning":
            self.logger.warning(json.dumps(log_data))
        elif level.lower() == "debug":
            self.logger.debug(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))
    
    def log_file_processing(self, filename: str, sequence_id: int, 
                           file_type: str, status: str, **kwargs):
        """Log file processing events"""
        self._log_structured(
            "info",
            f"File processing: {status}",
            filename=filename,
            sequence_id=sequence_id,
            file_type=file_type,
            status=status,
            **kwargs
        )
    
    def log_extraction_result(self, filename: str, sequence_id: int,
                             confidence_score: float, success: bool, **kwargs):
        """Log invoice extraction results"""
        self._log_structured(
            "info",
            f"Invoice extraction: {'success' if success else 'failed'}",
            filename=filename,
            sequence_id=sequence_id,
            confidence_score=confidence_score,
            success=success,
            **kwargs
        )
    
    def log_error(self, message: str, **kwargs):
        """Log errors"""
        self._log_structured("error", message, **kwargs)
    
    def log_warning(self, message: str, **kwargs):
        """Log warnings"""
        self._log_structured("warning", message, **kwargs)
    
    def log_info(self, message: str, **kwargs):
        """Log info"""
        self._log_structured("info", message, **kwargs)

def setup_logger(name: str = "invoice_processor") -> StructuredLogger:
    """Setup and return a structured logger instance"""
    return StructuredLogger(name)



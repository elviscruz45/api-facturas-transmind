from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # API Configuration
    app_name: str = "WhatsApp Invoice Extraction API"
    debug: bool = False
    
    # File Processing
    max_file_size_mb: int = 300
    allowed_extensions: List[str] = [".txt", ".jpg", ".png", ".jpeg", ".pdf"]
    temp_dir: str = "/tmp/invoice_processing"
    
    # Vertex AI Configuration
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_location: str = "us-central1"
    gemini_concurrency_limit: int = 5
    gemini_timeout_seconds: int = 30
    
    # Processing Configuration
    max_files_per_batch: int = 100
    encoding_fallback_sequence: List[str] = ["utf-8", "latin-1", "cp1252"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()


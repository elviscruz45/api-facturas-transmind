from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # API Configuration
    app_name: str = "WhatsApp Invoice Extraction API"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # File Processing
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "300"))
    allowed_extensions: List[str] = [".txt", ".jpg", ".png", ".jpeg", ".pdf"]
    temp_dir: str = "/tmp/invoice_processing"
    
    # Vertex AI Configuration (Optimizado para Free Tier - 15 RPM)
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    gemini_location: str = os.getenv("GEMINI_LOCATION", "us-east4")
    gemini_concurrency_limit: int = int(os.getenv("GEMINI_CONCURRENCY_LIMIT", "1"))  # Secuencial para evitar rate limits
    gemini_timeout_seconds: int = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "180"))  # 3 minutos para permitir reintentos
    
    
    # Cloud Storage Configuration
    storage_bucket_name: str = os.getenv("STORAGE_BUCKET_NAME", "facturacion-484614-invoices")
    storage_upload_folder: str = "uploads"
    storage_result_folder: str = "results"
    storage_retention_days: int = 90
    
    
    # Processing Configuration
    max_files_per_batch: int = 100
    encoding_fallback_sequence: List[str] = ["utf-8", "latin-1", "cp1252"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()


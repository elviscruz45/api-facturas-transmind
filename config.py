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
    
    # Vertex AI Configuration
    # Modelo: gemini-2.5-flash-lite es GA (estable) y el más barato con soporte multimodal
    # Pricing: $0.10/M tokens input imagen, $0.40/M tokens output
    # Con Batch API: 50% descuento ($0.05 input / $0.20 output)
    # Rate limits por tier:
    #   Free Tier   → ~15 RPM  (GEMINI_CONCURRENCY_LIMIT=1, TIMEOUT=180)
    #   Tier 1 Paid → ~1000 RPM (GEMINI_CONCURRENCY_LIMIT=10, TIMEOUT=60)
    #   Tier 2+     → ~2000 RPM (GEMINI_CONCURRENCY_LIMIT=20, TIMEOUT=30)
    # Para subir de Free a Tier 1: activar billing en Google AI Studio (sin costo adicional)
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    gemini_location: str = os.getenv("GEMINI_LOCATION", "us-east4")
    gemini_concurrency_limit: int = int(os.getenv("GEMINI_CONCURRENCY_LIMIT", "1"))  # Free Tier=1, Paid Tier 1=10, Tier 2+=20
    gemini_timeout_seconds: int = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "180"))    # Free=180s, Paid=60s, Tier2=30s
    
    
    # Cloud Storage Configuration
    storage_bucket_name: str = os.getenv("STORAGE_BUCKET_NAME", "facturacion-484614-invoices")
    storage_upload_folder: str = "uploads"
    storage_result_folder: str = "results"
    storage_retention_days: int = 90
    
    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_publishable_key: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    
    # Telegram Bot Configuration
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # OCR Configuration
    # Threshold de confianza: si OCR >= valor, se salta Gemini (ahorra 18-20s por factura)
    # 0.65 = solo necesita invoice_number + ruc + total para confiar en OCR
    ocr_confidence_threshold: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.65"))
    # true = usar Cloud Vision para imágenes/PDFs escaneados (requiere google-cloud-vision)
    ocr_use_cloud_vision: bool = os.getenv("OCR_USE_CLOUD_VISION", "true").lower() == "true"

    # Processing Configuration
    max_files_per_batch: int = 100
    encoding_fallback_sequence: List[str] = ["utf-8", "latin-1", "cp1252"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra variables in .env that aren't defined in Settings

settings = Settings()


"""
Cloud Storage service for managing uploaded ZIPs and processed files
"""
from google.cloud import storage
from google.oauth2 import service_account
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import io
from config import settings
from app.utils.logger import setup_logger

logger = setup_logger("storage_service")

class StorageService:
    """Manage file uploads and downloads to/from Cloud Storage"""
    
    def __init__(self):
        self.project_id = settings.google_cloud_project
        self.bucket_name = os.getenv("STORAGE_BUCKET_NAME", f"{self.project_id}-invoices")
        self.client = None
        self.bucket = None
        self.can_sign_urls = False  # Flag para saber si podemos generar signed URLs
        
    def initialize(self) -> bool:
        """Initialize Cloud Storage client and bucket"""
        try:
            # Check if service account credentials are configured
            service_account_path = settings.google_application_credentials
            
            if service_account_path and os.path.exists(service_account_path):
                # Use service account credentials (enables signed URLs)
                logger.log_info(
                    "Loading service account credentials",
                    credentials_path=service_account_path
                )
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_path
                )
                self.client = storage.Client(
                    project=self.project_id,
                    credentials=credentials
                )
                self.can_sign_urls = True
                logger.log_info("✅ Service account credentials loaded - signed URLs enabled")
            else:
                # Use Application Default Credentials (may not support signed URLs)
                logger.log_info(
                    "Using Application Default Credentials",
                    service_account_path=service_account_path or "not_configured"
                )
                self.client = storage.Client(project=self.project_id)
                
                # Detectar si podemos generar signed URLs
                try:
                    creds = self.client._credentials
                    if hasattr(creds, 'sign_bytes') or isinstance(creds, service_account.Credentials):
                        self.can_sign_urls = True
                        logger.log_info("✅ Credentials support signing - signed URLs available")
                    else:
                        self.can_sign_urls = False
                        logger.log_warning(
                            "⚠️ Credentials do not support signing - signed URLs disabled",
                            credentials_type=type(creds).__name__,
                            suggestion="Configure GOOGLE_APPLICATION_CREDENTIALS to enable signed URLs"
                        )
                except Exception as e:
                    self.can_sign_urls = False
                    logger.log_warning(
                        "⚠️ Could not detect credential signing capability",
                        error=str(e)
                    )
            
            # Get or create bucket
            try:
                self.bucket = self.client.get_bucket(self.bucket_name)
                logger.log_info(
                    "Cloud Storage bucket found",
                    bucket_name=self.bucket_name,
                    can_sign_urls=self.can_sign_urls
                )
            except Exception:
                # Bucket doesn't exist, create it
                self.bucket = self.client.create_bucket(
                    self.bucket_name,
                    location="us-east4"
                )
                
                # Set lifecycle policy to delete files after 90 days
                self.bucket.lifecycle_rules = [{
                    "action": {"type": "Delete"},
                    "condition": {"age": 90}
                }]
                self.bucket.patch()
                
                logger.log_info(
                    "Cloud Storage bucket created",
                    bucket_name=self.bucket_name,
                    location="us-east4",
                    can_sign_urls=self.can_sign_urls
                )
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to initialize Cloud Storage",
                error=str(e),
                error_type=type(e).__name__
            )
            import traceback
            logger.log_error(
                "Initialization traceback",
                traceback=traceback.format_exc()
            )
            return False
    
    def _generate_url_with_fallback(self, blob, days: int = 7) -> str:
        """Generate signed URL with fallback to public URL if signing fails"""
        if not self.can_sign_urls:
            # Si sabemos que no podemos firmar, devolver public URL directamente
            return blob.public_url if blob.public_url else f"gs://{self.bucket_name}/{blob.name}"
        
        try:
            # Intentar generar signed URL
            return blob.generate_signed_url(
                expiration=timedelta(days=days),
                method="GET"
            )
        except Exception as e:
            logger.log_warning(
                "Failed to generate signed URL, using fallback",
                error=str(e)[:100],  # Truncar error para logs
                blob_name=blob.name
            )
            return blob.public_url if blob.public_url else f"gs://{self.bucket_name}/{blob.name}"
    
    def upload_zip(self, file_content: bytes, original_filename: str, 
                   company_id: Optional[str] = None) -> Optional[Dict]:
        """
        Upload ZIP file to Cloud Storage
        
        Args:
            file_content: ZIP file bytes
            original_filename: Original filename
            company_id: Optional company identifier for multi-tenancy
            
        Returns:
            Dict with upload metadata or None if failed
        """
        if not self.bucket:
            if not self.initialize():
                return None
        
        try:
            # Generate unique path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_prefix = f"{company_id}/" if company_id else "uploads/"
            
            # Path structure: uploads/{company_id}/{year}/{month}/{timestamp}_{filename}
            year_month = datetime.now().strftime("%Y/%m")
            blob_path = f"{company_prefix}{year_month}/{timestamp}_{original_filename}"
            
            # Create blob and upload
            blob = self.bucket.blob(blob_path)
            
            # Set metadata
            blob.metadata = {
                "original_filename": original_filename,
                "upload_timestamp": timestamp,
                "company_id": company_id or "unknown",
                "content_type": "application/zip"
            }
            
            # Upload file
            blob.upload_from_string(
                file_content,
                content_type="application/zip"
            )
            
            # Generate URL (signed if possible, public otherwise)
            signed_url = self._generate_url_with_fallback(blob, days=7)
            
            logger.log_info(
                "ZIP uploaded to Cloud Storage",
                blob_path=blob_path,
                size_bytes=len(file_content),
                company_id=company_id
            )
            
            return {
                "blob_path": blob_path,
                "public_url": blob.public_url,
                "signed_url": signed_url,
                "size_bytes": len(file_content),
                "upload_timestamp": timestamp,
                "company_id": company_id
            }
            
        except Exception as e:
            logger.log_error(
                "Failed to upload ZIP to Cloud Storage",
                filename=original_filename,
                error=str(e)
            )
            return None
    
    def upload_excel(self, excel_bytes: io.BytesIO, original_zip_filename: str,
                     company_id: Optional[str] = None) -> Optional[Dict]:
        """
        Upload processed Excel file to Cloud Storage
        
        Args:
            excel_bytes: Excel file as BytesIO
            original_zip_filename: Original ZIP filename (for reference)
            company_id: Optional company identifier
            
        Returns:
            Dict with upload metadata or None if failed
        """
        if not self.bucket:
            if not self.initialize():
                return None
        
        try:
            # Generate unique path for Excel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_prefix = f"{company_id}/" if company_id else "results/"
            year_month = datetime.now().strftime("%Y/%m")
            
            excel_filename = f"facturas_{timestamp}.xlsx"
            blob_path = f"{company_prefix}{year_month}/{excel_filename}"
            
            # Create blob and upload
            blob = self.bucket.blob(blob_path)
            
            # Set metadata
            blob.metadata = {
                "original_zip": original_zip_filename,
                "processed_timestamp": timestamp,
                "company_id": company_id or "unknown",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
            
            # Upload Excel
            excel_bytes.seek(0)
            blob.upload_from_file(
                excel_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Generate URL (signed if possible, public otherwise)
            signed_url = self._generate_url_with_fallback(blob, days=30)
            
            logger.log_info(
                "Excel uploaded to Cloud Storage",
                blob_path=blob_path,
                original_zip=original_zip_filename,
                company_id=company_id
            )
            
            return {
                "blob_path": blob_path,
                "signed_url": signed_url,
                "excel_filename": excel_filename,
                "processed_timestamp": timestamp,
                "company_id": company_id
            }
            
        except Exception as e:
            logger.log_error(
                "Failed to upload Excel to Cloud Storage",
                error=str(e)
            )
            return None
    
    def upload_report_excel(self, excel_bytes: io.BytesIO, filename: str,
                           phone_number: Optional[str] = None,
                           metadata: Optional[Dict] = None) -> Optional[Dict]:
        """
        Upload Excel report to Cloud Storage with automatic URL generation fallback
        
        Args:
            excel_bytes: Excel file as BytesIO
            filename: Report filename
            phone_number: Optional phone number/company ID
            metadata: Optional metadata dict to attach to blob
            
        Returns:
            Dict with upload metadata including file_url, or None if failed
        """
        if not self.bucket:
            if not self.initialize():
                logger.log_error("Cannot upload report - storage not initialized")
                return None
        
        try:
            import uuid
            
            # Generate unique path for report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_prefix = f"reports/{phone_number}/" if phone_number else "reports/all/"
            year_month = datetime.now().strftime("%Y/%m")
            report_uuid = str(uuid.uuid4())[:8]
            blob_path = f"{company_prefix}{year_month}/{timestamp}_{report_uuid}_{filename}"
            
            # Create blob
            blob = self.bucket.blob(blob_path)
            
            # Set metadata
            blob.metadata = metadata or {}
            blob.metadata.update({
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "generated_at": timestamp,
                "filename": filename
            })
            
            # Upload Excel
            excel_bytes.seek(0)
            blob.upload_from_file(
                excel_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            logger.log_info(
                "Report uploaded to Cloud Storage",
                blob_path=blob_path,
                phone_number=phone_number or "all"
            )
            
            # Generate URL with automatic fallback
            file_url = self._generate_url_with_fallback(blob, days=7)
            
            # Determine URL type based on what we got
            url_type = "unknown"
            expires_in = "unknown"
            access = "unknown"
            
            if file_url:
                if "X-Goog-Signature" in file_url:
                    url_type = "signed_url"
                    expires_in = "7 days"
                    access = "temporary"
                elif file_url.startswith("gs://"):
                    url_type = "gs_uri"
                    expires_in = "N/A"
                    access = "requires_auth"
                else:
                    url_type = "public_url"
                    expires_in = "permanent"
                    access = "public"
            
            logger.log_info(
                "Report URL generated",
                url_type=url_type,
                can_sign_urls=self.can_sign_urls,
                blob_path=blob_path
            )
            
            return {
                "blob_path": blob_path,
                "file_url": file_url,
                "filename": filename,
                "url_type": url_type,
                "expires_in": expires_in,
                "access": access,
                "generated_at": timestamp
            }
            
        except Exception as e:
            logger.log_error(
                "Failed to upload report to Cloud Storage",
                filename=filename,
                error=str(e),
                error_type=type(e).__name__
            )
            import traceback
            logger.log_error(
                "Upload traceback",
                traceback=traceback.format_exc()
            )
            return None
    
    def list_company_files(self, company_id: str, 
                          file_type: str = "uploads",
                          limit: int = 100) -> List[Dict]:
        """
        List files for a specific company
        
        Args:
            company_id: Company identifier
            file_type: 'uploads' or 'results'
            limit: Maximum number of files to return
            
        Returns:
            List of file metadata dicts
        """
        if not self.bucket:
            if not self.initialize():
                return []
        
        try:
            prefix = f"{company_id}/"
            blobs = self.bucket.list_blobs(prefix=prefix, max_results=limit)
            
            files = []
            for blob in blobs:
                # Filter by file type if needed
                if file_type == "uploads" and not blob.name.endswith(".zip"):
                    continue
                if file_type == "results" and not blob.name.endswith(".xlsx"):
                    continue
                
                files.append({
                    "filename": blob.name.split("/")[-1],
                    "blob_path": blob.name,
                    "size_bytes": blob.size,
                    "created_at": blob.time_created.isoformat() if blob.time_created else None,
                    "metadata": blob.metadata or {}
                })
            
            return files
            
        except Exception as e:
            logger.log_error(
                "Failed to list company files",
                company_id=company_id,
                error=str(e)
            )
            return []
    
    def download_file(self, blob_path: str) -> Optional[bytes]:
        """
        Download file from Cloud Storage
        
        Args:
            blob_path: Path to blob in bucket
            
        Returns:
            File bytes or None if failed
        """
        if not self.bucket:
            if not self.initialize():
                return None
        
        try:
            blob = self.bucket.blob(blob_path)
            content = blob.download_as_bytes()
            
            logger.log_info(
                "File downloaded from Cloud Storage",
                blob_path=blob_path,
                size_bytes=len(content)
            )
            
            return content
            
        except Exception as e:
            logger.log_error(
                "Failed to download file from Cloud Storage",
                blob_path=blob_path,
                error=str(e)
            )
            return None
    
    def delete_file(self, blob_path: str) -> bool:
        """
        Delete file from Cloud Storage
        
        Args:
            blob_path: Path to blob in bucket
            
        Returns:
            True if deleted successfully
        """
        if not self.bucket:
            if not self.initialize():
                return False
        
        try:
            blob = self.bucket.blob(blob_path)
            blob.delete()
            
            logger.log_info(
                "File deleted from Cloud Storage",
                blob_path=blob_path
            )
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to delete file from Cloud Storage",
                blob_path=blob_path,
                error=str(e)
            )
            return False


# Global service instance
storage_service = StorageService()

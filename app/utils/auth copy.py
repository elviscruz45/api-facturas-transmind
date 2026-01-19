from google.cloud import aiplatform
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2.service_account import Credentials
import os
from config import settings
from app.utils.logger import setup_logger

logger = setup_logger("vertex_ai_auth")

class VertexAIAuth:
    """Handle Vertex AI authentication and client initialization"""
    def __init__(self):
        self.project_id = settings.google_cloud_project
        self.location = settings.gemini_location
        self.credentials = None
        self._client_initialized = False
    
    def initialize_credentials(self) -> bool:
        """Initialize Google Cloud credentials using ADC or service account"""
        try:
            
            print("111111 google auth")

            # Try explicit service account file first (avoids blocking on metadata server)
            sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or settings.google_application_credentials
            
            if sa_path and os.path.exists(sa_path):
                print(f"Loading credentials from file: {sa_path}")
                self.credentials = Credentials.from_service_account_file(sa_path)
                
                # Get project from file or settings
                if not self.project_id:
                    # Try to read project from service account file
                    import json
                    with open(sa_path, 'r') as f:
                        sa_data = json.load(f)
                        self.project_id = sa_data.get('project_id', settings.google_cloud_project)
                
                logger.log_info(
                    "Vertex AI credentials initialized from service account file",
                    project_id=self.project_id,
                    location=self.location,
                    auth_method="service_account_file"
                )
                print("222222 google auth (from file)")
                return True
            
            print("No service account file found, trying ADC...")
            # Fallback: Try Application Default Credentials
            credentials, project = default()
            print("222222 google auth (from ADC)")

            # If project not found in credentials, use from settings
            if not project and self.project_id:
                project = self.project_id
            elif project and not self.project_id:
                self.project_id = project
            print("33333 google auth")

            self.credentials = credentials
            print("44444 google auth")

            logger.log_info(
                "Vertex AI credentials initialized successfully",
                project_id=self.project_id,
                location=self.location,
                auth_method="ADC"
            )
            
            return True
            
        except DefaultCredentialsError as e:
            logger.log_error(
                "Failed to initialize Vertex AI credentials",
                error=str(e),
                project_id=self.project_id
            )
            return False
        except Exception as e:
            logger.log_error(
                "Unexpected error initializing credentials",
                error=str(e),
                project_id=self.project_id
            )
            return False
    
    def initialize_vertex_ai(self) -> bool:
        """Initialize Vertex AI platform"""
        print("111111 vertex ai")

        if not self.initialize_credentials():
            return False
        
        print("22222 vertex ai")

        
        try:
            aiplatform.init(
                project=self.project_id,
                location=self.location,
                credentials=self.credentials
            )
            
            self._client_initialized = True
            
            logger.log_info(
                "Vertex AI platform initialized successfully",
                project_id=self.project_id,
                location=self.location
            )
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to initialize Vertex AI platform",
                error=str(e),
                project_id=self.project_id,
                location=self.location
            )
            return False
    
    def is_initialized(self) -> bool:
        """Check if Vertex AI is properly initialized"""
        return self._client_initialized
    
    def get_project_id(self) -> str:
        """Get the current project ID"""
        return self.project_id

# Global auth instance
vertex_auth = VertexAIAuth()


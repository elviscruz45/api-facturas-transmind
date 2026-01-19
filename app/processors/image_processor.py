import base64
from PIL import Image
from typing import Optional, Dict
from app.utils.logger import setup_logger

logger = setup_logger("image_processor")

class ImageProcessor:
    """Phase 4: Process image files for invoice extraction using Gemini"""
    
    def __init__(self):
        # Supported image formats
        self.supported_formats = ['JPEG', 'PNG', 'JPG']
        self.max_image_size = (2048, 2048)  # Max size for Gemini
    
    def validate_image(self, file_path: str) -> tuple[bool, str]:
        """Validate image file format and size"""
        try:
            with Image.open(file_path) as img:
                # Check format
                if img.format not in self.supported_formats:
                    return False, f"Unsupported image format: {img.format}"
                
                # Check if image is too large
                width, height = img.size
                if width > self.max_image_size[0] or height > self.max_image_size[1]:
                    logger.log_warning(
                        "Image size exceeds maximum",
                        filename=file_path,
                        size=f"{width}x{height}",
                        max_size=f"{self.max_image_size[0]}x{self.max_image_size[1]}"
                    )
                    # We'll resize it rather than reject it
                
                return True, "Valid image"
                
        except Exception as e:
            return False, f"Image validation failed: {str(e)}"
    
    def resize_image_if_needed(self, file_path: str) -> Optional[str]:
        """Resize image if it exceeds maximum size"""
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                
                if width <= self.max_image_size[0] and height <= self.max_image_size[1]:
                    return file_path  # No resizing needed
                
                # Calculate new size maintaining aspect ratio
                ratio = min(self.max_image_size[0] / width, self.max_image_size[1] / height)
                new_size = (int(width * ratio), int(height * ratio))
                
                # Resize image
                resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save resized image (overwrite original in temp directory)
                resized_img.save(file_path, img.format, quality=95)
                
                logger.log_file_processing(
                    filename=file_path,
                    sequence_id=0,
                    file_type="image",
                    status="resized",
                    original_size=f"{width}x{height}",
                    new_size=f"{new_size[0]}x{new_size[1]}"
                )
                
                return file_path
                
        except Exception as e:
            logger.log_error(
                "Image resizing failed",
                filename=file_path,
                error=str(e)
            )
            return None
    
    def convert_image_to_base64(self, file_path: str) -> Optional[str]:
        """Convert image to base64 for Gemini API"""
        try:
            with open(file_path, 'rb') as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            return encoded_image
            
        except Exception as e:
            logger.log_error(
                "Image base64 encoding failed",
                filename=file_path,
                error=str(e)
            )
            return None
    
    def prepare_image_for_gemini(self, file_path: str) -> Dict:
        """Prepare image for Gemini processing"""
        try:
            # Validate image
            is_valid, message = self.validate_image(file_path)
            if not is_valid:
                return {
                    "success": False,
                    "error": message,
                    "image_data": None
                }
            
            # Resize if needed
            processed_path = self.resize_image_if_needed(file_path)
            if not processed_path:
                return {
                    "success": False,
                    "error": "Image processing failed",
                    "image_data": None
                }
            
            # Convert to base64
            base64_image = self.convert_image_to_base64(processed_path)
            if not base64_image:
                return {
                    "success": False,
                    "error": "Image encoding failed",
                    "image_data": None
                }
            
            # Get image info
            with Image.open(processed_path) as img:
                image_info = {
                    "format": img.format,
                    "size": img.size,
                    "mode": img.mode
                }
            
            return {
                "success": True,
                "image_data": base64_image,
                "image_info": image_info,
                "processed_path": processed_path
            }
            
        except Exception as e:
            logger.log_error(
                "Image preparation for Gemini failed",
                filename=file_path,
                error=str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "image_data": None
            }
import json
import asyncio
from typing import Dict, Optional
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import aiplatform
from config import settings
from app.utils.auth import vertex_auth
from app.schemas.invoice_schema import InvoiceSchema
from app.utils.logger import setup_logger

logger = setup_logger("gemini_service")

class GeminiService:
    """Vertex AI Gemini service for invoice extraction from images and PDFs"""
    
    def __init__(self):
        self.model_name = settings.gemini_model
        self.timeout_seconds = settings.gemini_timeout_seconds
        self.model = None
        self.semaphore = asyncio.Semaphore(settings.gemini_concurrency_limit)
        
        # Invoice extraction prompt template
        self.invoice_prompt = """
Analyze this image and extract invoice/receipt information. Return ONLY a JSON object with these exact fields (use null for missing values):

{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD format or null",
  "supplier_name": "string or null", 
  "supplier_ruc": "11-digit RUC number or null",
  "customer_name": "string or null",
  "subtotal": "numeric value or null",
  "tax": "numeric tax amount or null",
  "total": "numeric total amount or null",
  "currency": "PEN/USD/EUR etc or null",
  "confidence_score": "0.0 to 1.0 based on data quality"
}

Rules:
- Extract only visible information
- For dates, use YYYY-MM-DD format 
- For numbers, use numeric values without currency symbols
- Set confidence_score based on text clarity and completeness
- If no invoice data is found, set confidence_score to 0.0
- Return ONLY the JSON, no additional text
"""
    
    def initialize_model(self) -> bool:
        """Initialize the Gemini model"""
        try:
            if not vertex_auth.initialize_vertex_ai():
                return False
            
            self.model = GenerativeModel(self.model_name)
            
            logger.log_info(
                "Gemini model initialized successfully",
                model_name=self.model_name,
                project_id=vertex_auth.get_project_id()
            )
            
            return True
            
        except Exception as e:
            logger.log_error(
                "Failed to initialize Gemini model",
                model_name=self.model_name,
                error=str(e)
            )
            return False
    
    def prepare_image_part(self, image_base64: str, mime_type: str) -> Part:
        """Prepare image part for Gemini"""
        import base64
        image_data = base64.b64decode(image_base64)
        return Part.from_data(image_data, mime_type=mime_type)
    
    async def extract_invoice_from_image(self, image_base64: str, filename: str, 
                                       sequence_id: int) -> Dict:
        """Extract invoice data from image using Gemini"""
        
        async with self.semaphore:  # Control concurrency
            try:
                if not self.model:
                    if not self.initialize_model():
                        return self._create_error_response(
                            "Gemini model not initialized", filename, sequence_id
                        )
                
                # Prepare image part
                image_part = self.prepare_image_part(image_base64, "image/jpeg")
                
                # Generate content
                logger.log_file_processing(
                    filename=filename,
                    sequence_id=sequence_id,
                    file_type="image",
                    status="sending_to_gemini"
                )
                
                response = await asyncio.wait_for(
                    self._call_gemini_async(image_part, self.invoice_prompt),
                    timeout=self.timeout_seconds
                )
                
                # Parse response
                return self._parse_gemini_response(response, filename, sequence_id)
                
            except asyncio.TimeoutError:
                logger.log_error(
                    "Gemini API timeout",
                    filename=filename,
                    sequence_id=sequence_id,
                    timeout_seconds=self.timeout_seconds
                )
                return self._create_error_response(
                    "API timeout", filename, sequence_id
                )
            
            except Exception as e:
                logger.log_error(
                    "Gemini image processing failed",
                    filename=filename,
                    sequence_id=sequence_id,
                    error=str(e)
                )
                return self._create_error_response(
                    str(e), filename, sequence_id
                )
    
    async def extract_invoice_from_text(self, text_content: str, filename: str,
                                      sequence_id: int) -> Dict:
        """Extract invoice data from text content"""
        
        async with self.semaphore:
            try:
                if not self.model:
                    if not self.initialize_model():
                        return self._create_error_response(
                            "Gemini model not initialized", filename, sequence_id
                        )
                
                # Create text-specific prompt
                text_prompt = f"""\nAnalyze this text and extract invoice information. Return ONLY a JSON object with the same structure as requested for images.\n\nText content:\n{text_content}\n\n{self.invoice_prompt}"""
                
                logger.log_file_processing(
                    filename=filename,
                    sequence_id=sequence_id,
                    file_type="text",
                    status="sending_to_gemini",
                    content_length=len(text_content)
                )
                
                response = await asyncio.wait_for(
                    self._call_gemini_text_async(text_prompt),
                    timeout=self.timeout_seconds
                )
                
                return self._parse_gemini_response(response, filename, sequence_id)
                
            except Exception as e:
                logger.log_error(
                    "Gemini text processing failed",
                    filename=filename,
                    sequence_id=sequence_id,
                    error=str(e)
                )
                return self._create_error_response(
                    str(e), filename, sequence_id
                )
    
    async def _call_gemini_async(self, image_part: Part, prompt: str) -> str:
        """Make async call to Gemini with image"""
        def _sync_call():
            response = self.model.generate_content([image_part, prompt])
            return response.text
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_call)
    
    async def _call_gemini_text_async(self, prompt: str) -> str:
        """Make async call to Gemini with text only"""
        def _sync_call():
            response = self.model.generate_content(prompt)
            return response.text
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_call)
    
    def _parse_gemini_response(self, response_text: str, filename: str, 
                              sequence_id: int) -> Dict:
        """Parse Gemini JSON response into InvoiceSchema"""
        try:
            # Clean response text
            cleaned_response = response_text.strip()
            
            # Remove any markdown code blocks
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # Parse JSON
            invoice_data = json.loads(cleaned_response)
            
            # Add metadata
            invoice_data["source_file"] = filename
            invoice_data["sequence_id"] = sequence_id
            
            # Validate using Pydantic schema
            invoice_schema = InvoiceSchema(**invoice_data)
            
            logger.log_extraction_result(
                filename=filename,
                sequence_id=sequence_id,
                confidence_score=invoice_schema.confidence_score,
                success=True,
                invoice_number=invoice_schema.invoice_number,
                total=invoice_schema.total
            )
            
            return {
                "success": True,
                "invoice_data": invoice_schema.dict(),
                "raw_response": response_text
            }
            
        except json.JSONDecodeError as e:
            logger.log_error(
                "Invalid JSON response from Gemini",
                filename=filename,
                sequence_id=sequence_id,
                response=response_text[:200] + "..." if len(response_text) > 200 else response_text,
                json_error=str(e)
            )
            return self._create_fallback_response(response_text, filename, sequence_id)
            
        except Exception as e:
            logger.log_error(
                "Response parsing failed",
                filename=filename,
                sequence_id=sequence_id,
                error=str(e)
            )
            return self._create_fallback_response(response_text, filename, sequence_id)
    
    def _create_error_response(self, error_msg: str, filename: str, 
                              sequence_id: int) -> Dict:
        """Create error response with 0 confidence"""
        error_invoice = InvoiceSchema(
            confidence_score=0.0,
            source_file=filename,
            sequence_id=sequence_id
        )
        
        return {
            "success": False,
            "invoice_data": error_invoice.dict(),
            "error": error_msg,
            "raw_response": None
        }
    
    def _create_fallback_response(self, raw_response: str, filename: str,
                                 sequence_id: int) -> Dict:
        """Create fallback response when JSON parsing fails"""
        fallback_invoice = InvoiceSchema(
            confidence_score=0.0,
            source_file=filename,
            sequence_id=sequence_id
        )
        
        return {
            "success": False,
            "invoice_data": fallback_invoice.dict(),
            "raw_response": raw_response,
            "error": "Failed to parse structured response"
        }

# Global service instance
gemini_service = GeminiService()
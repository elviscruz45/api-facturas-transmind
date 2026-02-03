import json
import asyncio
from typing import Dict, Optional
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from google.cloud import aiplatform
from google.api_core import retry, exceptions
from config import settings
from app.utils.auth import vertex_auth
from app.schemas.invoice_schema import InvoiceSchema
from app.utils.logger import setup_logger
import time

logger = setup_logger("gemini_service")

class GeminiService:
    """Vertex AI Gemini service for invoice extraction from images and PDFs"""
    
    def __init__(self):
        self.model_name = settings.gemini_model
        self.timeout_seconds = settings.gemini_timeout_seconds
        self.model = None
        self.semaphore = asyncio.Semaphore(settings.gemini_concurrency_limit)
        
        # Configuración para forzar respuestas JSON limpias (sin markdown)
        self.generation_config = GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1  # Baja temperatura para respuestas más deterministas
        )
        
        # Invoice extraction prompt template
        self.invoice_prompt = """
Analyze this image and extract invoice/receipt information. Return ONLY a JSON object with these exact fields (use null for missing values):

{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD format or null",
  "supplier_name": "string or null", 
  "supplier_ruc": "11-digit RUC number or null",
  "customer_name": "string or null",
  "items": [
    {
      "description": "item description or null",
      "quantity": "numeric quantity or null",
      "unit_price": "numeric unit price or null",
      "total_price": "numeric total price or null",
      "unit": "measurement unit (unidad/kg/metro/etc) or null"
    }
  ],
  "subtotal": "numeric value or null",
  "tax": "numeric tax amount or null",
  "total": "numeric total amount or null",
  "currency": "PEN/USD/EUR etc or null",
  "confidence_score": "0.0 to 1.0 based on data quality"
}

Rules:
- Extract ALL visible line items/products from the invoice detail
- For each item, extract description, quantity, unit price, total price and unit of measurement
- If no items are visible, use empty array [] for "items"
- For dates, use YYYY-MM-DD format 
- For numbers, use numeric values without currency symbols
- Set confidence_score based on text clarity and completeness
- If no invoice data is found, set confidence_score to 0.0
- Return ONLY the JSON, no additional text or markdown
"""
    
    def initialize_model(self) -> bool:
        """Initialize the Gemini model"""
        try:
            print("se esta inizando vertex ai")
            if not vertex_auth.initialize_vertex_ai():
                return False
            print("bbbbb se esta inizando vertex ai")

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
            print ("semafoorooooo")
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
                
                # Delay conservador para 15 RPM (6s = ~10 requests/min con margen de seguridad)
                await asyncio.sleep(6)
                
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
    
    async def extract_invoice_from_pdf(self, pdf_base64: str, filename: str,
                                      sequence_id: int) -> Dict:
        """Extract invoice data from PDF using Gemini"""
        
        async with self.semaphore:
            try:
                if not self.model:
                    if not self.initialize_model():
                        return self._create_error_response(
                            "Gemini model not initialized", filename, sequence_id
                        )
                
                # Prepare PDF part
                pdf_part = self.prepare_image_part(pdf_base64, "application/pdf")
                
                logger.log_file_processing(
                    filename=filename,
                    sequence_id=sequence_id,
                    file_type="pdf",
                    status="sending_to_gemini"
                )
                
                # Generate content from PDF
                response = await asyncio.wait_for(
                    self._call_gemini_async(pdf_part, self.invoice_prompt),
                    timeout=self.timeout_seconds
                )
                
                # Delay conservador para 15 RPM (6s = ~10 requests/min con margen de seguridad)
                await asyncio.sleep(6)
                
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
                    "Gemini PDF processing failed",
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
                
                # Delay conservador para 15 RPM (6s = ~10 requests/min con margen de seguridad)
                await asyncio.sleep(6)
                
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
        """Make async call to Gemini with image and automatic retries for rate limits"""
        max_retries = 5  # Más reintentos para manejar rate limits de 15 RPM
        base_delay = 3  # Backoff exponencial (3s, 6s, 12s, 24s, 48s)
        
        for attempt in range(max_retries):
            try:
                def _sync_call():
                    response = self.model.generate_content(
                        [image_part, prompt],
                        generation_config=self.generation_config
                    )
                    return response.text
                
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, _sync_call)
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a 429 error (rate limit)
                if "429" in error_str or "Resource exhausted" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        delay = base_delay * (2 ** attempt)
                        logger.log_warning(
                            f"Rate limit hit (429), retrying in {delay}s",
                            attempt=attempt + 1,
                            max_retries=max_retries
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.log_error(
                            "Max retries reached for rate limit",
                            attempts=max_retries
                        )
                        raise Exception("Rate limit exceeded after retries. Please reduce concurrency or try again later.")
                else:
                    # Not a rate limit error, raise immediately
                    raise
        
        raise Exception("Failed after all retry attempts")
    
    async def _call_gemini_text_async(self, prompt: str) -> str:
        """Make async call to Gemini with text only and automatic retries"""
        max_retries = 5  # Más reintentos para manejar rate limits de 15 RPM
        base_delay = 3  # Backoff exponencial (3s, 6s, 12s, 24s, 48s)
        
        for attempt in range(max_retries):
            try:
                def _sync_call():
                    response = self.model.generate_content(
                        prompt,
                        generation_config=self.generation_config
                    )
                    return response.text
                
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, _sync_call)
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a 429 error (rate limit)
                if "429" in error_str or "Resource exhausted" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        delay = base_delay * (2 ** attempt)
                        logger.log_warning(
                            f"Rate limit hit (429), retrying in {delay}s",
                            attempt=attempt + 1,
                            max_retries=max_retries
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.log_error(
                            "Max retries reached for rate limit",
                            attempts=max_retries
                        )
                        raise Exception("Rate limit exceeded after retries. Please reduce concurrency or try again later.")
                else:
                    # Not a rate limit error, raise immediately
                    raise
        
        raise Exception("Failed after all retry attempts")
    
    def _parse_gemini_response(self, response_text: str, filename: str, 
                              sequence_id: int) -> Dict:
        """Parse Gemini JSON response into InvoiceSchema
        
        Ahora mucho más seguro porque generation_config con response_mime_type='application/json'
        garantiza que Gemini devuelva JSON limpio sin markdown.
        """
        try:
            # Ya no necesitamos limpiar markdown - Gemini garantiza JSON puro
            invoice_data = json.loads(response_text.strip())
            
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
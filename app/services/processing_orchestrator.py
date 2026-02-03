import asyncio
from typing import List, Dict
from app.models.file_index import FileRecord
from app.processors.file_sorter import FileSorter
from app.processors.file_classifier import FileClassifier
from app.processors.text_processor import TextProcessor
from app.processors.image_processor import ImageProcessor
from app.processors.pdf_processor import PDFProcessor
from app.services.gemini_service import gemini_service
from app.schemas.invoice_schema import InvoiceSchema, ProcessingResponse
from app.utils.logger import setup_logger

logger = setup_logger("processing_orchestrator")

class ProcessingOrchestrator:
    """Phase 6: Orchestrate the complete invoice extraction pipeline"""
    
    def __init__(self):
        self.file_sorter = FileSorter()
        self.file_classifier = FileClassifier()
        self.text_processor = TextProcessor()
        self.image_processor = ImageProcessor()
        self.pdf_processor = PDFProcessor()
    
    async def process_extracted_files(self, extracted_files: List[Dict]) -> ProcessingResponse:
        """Main orchestration method to process all files"""
        
        logger.log_info(
            "Starting invoice processing pipeline",
            total_files=len(extracted_files)
        )
        
        try:
            # Phase 2: Sort files chronologically
            sorted_file_indices = self.file_sorter.sort_files_chronologically(extracted_files)
            
            # Validate chronological order
            if not self.file_sorter.validate_chronological_order(sorted_file_indices):
                logger.log_warning("Chronological order validation failed")
            
            # Phase 3: Classify files by type
            classified_files = self.file_classifier.classify_files(sorted_file_indices)
            
            # Get processable files
            processable_files = self.file_classifier.get_processable_files(classified_files)
            
            # Phase 4: Process files by type sequentially to maintain order
            results = []
            errors = []
            
            for file_record in processable_files:
                try:
                    result = await self.process_single_file(file_record)
                    
                    if result["success"]:
                        results.append(result["invoice_data"])
                        logger.log_file_processing(
                            filename=file_record.filename,
                            sequence_id=file_record.sequence_id,
                            file_type=file_record.file_type,
                            status="processing_completed",
                            success=True
                        )
                    else:
                        errors.append({
                            "file": file_record.filename,
                            "sequence_id": file_record.sequence_id,
                            "file_type": file_record.file_type,
                            "error": result.get("error", "Unknown error")
                        })
                        
                        logger.log_file_processing(
                            filename=file_record.filename,
                            sequence_id=file_record.sequence_id,
                            file_type=file_record.file_type,
                            status="processing_failed",
                            success=False,
                            error=result.get("error")
                        )
                
                except Exception as e:
                    error_info = {
                        "file": file_record.filename,
                        "sequence_id": file_record.sequence_id,
                        "file_type": file_record.file_type,
                        "error": str(e)
                    }
                    errors.append(error_info)
                    
                    logger.log_error(
                        "Single file processing failed",
                        filename=file_record.filename,
                        sequence_id=file_record.sequence_id,
                        error=str(e)
                    )
            
            # Create response
            response = ProcessingResponse(
                results=results,
                errors=errors,
                total_processed=len(processable_files),
                success_count=len(results)
            )
            
            logger.log_info(
                "Invoice processing pipeline completed",
                total_files=len(extracted_files),
                processable_files=len(processable_files),
                successful_extractions=len(results),
                errors=len(errors),
                success_rate=f"{(len(results)/len(processable_files)*100):.1f}%" if processable_files else "0%"
            )
            
            return response
            
        except Exception as e:
            logger.log_error(
                "Processing pipeline failed",
                error=str(e),
                total_files=len(extracted_files)
            )
            
            # Return error response
            return ProcessingResponse(
                results=[],
                errors=[{"error": f"Pipeline failed: {str(e)}"}],
                total_processed=0,
                success_count=0
            )
    
    async def process_single_file(self, file_record: FileRecord) -> Dict:
        """Process a single file based on its type"""
        
        logger.log_file_processing(
            filename=file_record.filename,
            sequence_id=file_record.sequence_id,
            file_type=file_record.file_type,
            status="processing_started"
        )
        
        try:
            if file_record.file_type == "text":
                return await self.process_text_file(file_record)
            
            elif file_record.file_type == "image":
                return await self.process_image_file(file_record)
            
            elif file_record.file_type == "pdf":
                return await self.process_pdf_file(file_record)
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_record.file_type}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_text_file(self, file_record: FileRecord) -> Dict:
        """Process text file"""
        try:
            # Extract text content
            result = self.text_processor.process_text_file(file_record.file_path)
            
            if not result["success"]:
                return result
            
            text_content = result["content"]
            
            # Check if it's potentially an invoice
            if not result.get("is_potential_invoice", False):
                # Create low-confidence response
                low_conf_invoice = InvoiceSchema(
                    confidence_score=0.1,
                    source_file=file_record.filename,
                    sequence_id=file_record.sequence_id
                )
                
                return {
                    "success": True,
                    "invoice_data": low_conf_invoice.dict(),
                    "note": "Text does not appear to contain invoice data"
                }
            
            # Send to Gemini for structured extraction
            gemini_result = await gemini_service.extract_invoice_from_text(
                text_content, file_record.filename, file_record.sequence_id
            )
            
            return gemini_result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Text processing failed: {str(e)}"
            }
    
    async def process_image_file(self, file_record: FileRecord) -> Dict:
        """Process image file"""
        try:
            # Prepare image for Gemini
            prep_result = self.image_processor.prepare_image_for_gemini(file_record.file_path)
            
            if not prep_result["success"]:
                return prep_result
            
            
            # Send to Gemini
            gemini_result = await gemini_service.extract_invoice_from_image(
                prep_result["image_data"],
                file_record.filename,
                file_record.sequence_id
            )
            
            return gemini_result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Image processing failed: {str(e)}"
            }
    
    async def process_pdf_file(self, file_record: FileRecord) -> Dict:
        """Process PDF file"""
        try:
            # Process PDF (detect text vs scanned)
            pdf_result = self.pdf_processor.process_pdf_file(file_record.file_path)
            
            if not pdf_result["success"]:
                return pdf_result
            
            if pdf_result["processing_type"] == "text_extraction":
                # Text-based PDF - send text to Gemini
                text_content = pdf_result["content"]
                gemini_result = await gemini_service.extract_invoice_from_text(
                    text_content, file_record.filename, file_record.sequence_id
                )
                return gemini_result
            
            else:
                return {
                    "success": False,
                    "error": "Scanned PDF processing not available in MVP"
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF processing failed: {str(e)}"
            }

# Global orchestrator instance
orchestrator = ProcessingOrchestrator()


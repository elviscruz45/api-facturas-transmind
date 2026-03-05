import asyncio
import time
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
        pipeline_start = time.time()
        logger.log_info(
            "🚀 Starting invoice processing pipeline",
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
            
            # Procesar archivos en paralelo (el semáforo de Gemini controla la concurrencia real)
            tasks = [self.process_single_file(f) for f in processable_files]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            for file_record, result in zip(processable_files, raw_results):
                try:
                    if isinstance(result, Exception):
                        raise result

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
            
            pipeline_elapsed = time.time() - pipeline_start

            logger.log_info(
                "✅ Invoice processing pipeline completed",
                total_files=len(extracted_files),
                processable_files=len(processable_files),
                successful_extractions=len(results),
                errors=len(errors),
                success_rate=f"{(len(results)/len(processable_files)*100):.1f}%" if processable_files else "0%",
                total_elapsed_s=round(pipeline_elapsed, 2)
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
        file_start = time.time()
        logger.log_file_processing(
            filename=file_record.filename,
            sequence_id=file_record.sequence_id,
            file_type=file_record.file_type,
            status="processing_started"
        )

        try:
            if file_record.file_type == "text":
                result = await self.process_text_file(file_record)
            elif file_record.file_type == "image":
                result = await self.process_image_file(file_record)
            elif file_record.file_type == "pdf":
                result = await self.process_pdf_file(file_record)
            else:
                return {"success": False, "error": f"Unsupported file type: {file_record.file_type}"}

            elapsed = round(time.time() - file_start, 2)
            engine = result.get("extraction_method", "gemini")
            confidence = result.get("invoice_data", {}).get("confidence_score", 0.0) if result.get("success") else 0.0
            icon = "⚡" if "ocr" in engine else "🤖"
            logger.log_info(
                f"{icon} [{engine.upper()}] {file_record.filename} → {elapsed}s | confidence={confidence}",
                filename=file_record.filename,
                sequence_id=file_record.sequence_id,
                engine=engine,
                elapsed_s=elapsed,
                confidence=confidence,
                success=result.get("success")
            )
            return result

        except Exception as e:
            elapsed = round(time.time() - file_start, 2)
            logger.log_error(
                f"❌ File processing crashed after {elapsed}s",
                filename=file_record.filename,
                elapsed_s=elapsed,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    async def process_text_file(self, file_record: FileRecord) -> Dict:
        """Process text file — Gemini directo."""
        try:
            result = self.text_processor.process_text_file(file_record.file_path)
            if not result["success"]:
                return result

            text_content = result["content"]

            if not result.get("is_potential_invoice", False):
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

            t0 = time.time()
            logger.log_info("🤖 [GEMINI] processing text file", filename=file_record.filename)
            gemini_result = await gemini_service.extract_invoice_from_text(
                text_content, file_record.filename, file_record.sequence_id
            )
            gemini_result["extraction_method"] = "gemini_text"
            logger.log_info(
                f"🤖 [GEMINI] text done in {round(time.time()-t0, 1)}s",
                filename=file_record.filename
            )
            return gemini_result

        except Exception as e:
            return {"success": False, "error": f"Text processing failed: {str(e)}"}
    
    async def process_image_file(self, file_record: FileRecord) -> Dict:
        """
        Process image — Gemini Vision directo.
        OCR no aplica para imágenes de WhatsApp: compresión JPEG, ángulos,
        sombras → confidence bajo → igual cae al fallback, sumando latencia.
        OCR-first sí aplica para PDFs digitales SUNAT (texto puro estructurado).
        """
        try:
            prep_result = self.image_processor.prepare_image_for_gemini(file_record.file_path)
            if not prep_result["success"]:
                return prep_result

            image_data = prep_result["image_data"]

            t0 = time.time()
            logger.log_info(
                "🤖 [GEMINI VISION] processing image",
                filename=file_record.filename
            )
            gemini_result = await gemini_service.extract_invoice_from_image(
                image_data, file_record.filename, file_record.sequence_id
            )
            gemini_result["extraction_method"] = "gemini_vision"
            logger.log_info(
                f"🤖 [GEMINI VISION] done in {round(time.time()-t0, 1)}s",
                filename=file_record.filename
            )
            return gemini_result

        except Exception as e:
            return {"success": False, "error": f"Image processing failed: {str(e)}"}
    
    async def process_pdf_file(self, file_record: FileRecord) -> Dict:
        """Process PDF — Gemini directo."""
        try:
            pdf_result = self.pdf_processor.process_pdf_file(file_record.file_path)
            if not pdf_result["success"]:
                return pdf_result

            t0 = time.time()
            logger.log_info("🤖 [GEMINI PDF] processing PDF", filename=file_record.filename)

            # Usar base64 del PDF si está disponible, sino texto extraído
            if pdf_result.get("pdf_base64"):
                gemini_result = await gemini_service.extract_invoice_from_pdf(
                    pdf_result["pdf_base64"], file_record.filename, file_record.sequence_id
                )
            else:
                text_content = pdf_result.get("content", "")
                gemini_result = await gemini_service.extract_invoice_from_text(
                    text_content, file_record.filename, file_record.sequence_id
                )

            gemini_result["extraction_method"] = "gemini_pdf"
            logger.log_info(
                f"🤖 [GEMINI PDF] done in {round(time.time()-t0, 1)}s",
                filename=file_record.filename
            )
            return gemini_result

        except Exception as e:
            return {"success": False, "error": f"PDF processing failed: {str(e)}"}

# Global orchestrator instance
orchestrator = ProcessingOrchestrator()


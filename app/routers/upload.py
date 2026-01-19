from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.services.zip_handler import ZipHandler
from app.services.processing_orchestrator import orchestrator
from app.schemas.invoice_schema import ProcessingResponse
from app.utils.logger import setup_logger

logger = setup_logger("upload_router")

router = APIRouter()

zip_handler = ZipHandler()

@router.post("/process-zip", response_model=ProcessingResponse)
async def process_zip_file(file: UploadFile = File(...)):
    """
    Process a ZIP file from WhatsApp and extract invoice data
    
    - **file**: ZIP file containing WhatsApp exported media
    
    Returns structured invoice data extracted from images, PDFs, and text files.
    Files are processed in chronological order based on WhatsApp timestamps.
    """

    logger.log_info(
        "ZIP file upload started",
        filename=file.filename,
        content_type=file.content_type
    )

    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a ZIP file"
            )
        
        # Read file content
        file_content = await file.read()
        
        logger.log_info(
            "ZIP file read successfully",
            filename=file.filename,
            size_bytes=len(file_content)
        )
        
        # Phase 1: Extract and validate ZIP
        success, extraction_result = zip_handler.extract_zip_files(file_content, file.filename)
        
        if not success:
            logger.log_error(
                "ZIP extraction failed",
                filename=file.filename,
                error=extraction_result.get("error")
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ZIP processing failed: {extraction_result.get('error')}"
            )
        
        extracted_files = extraction_result["extracted_files"]
        ignored_files = extraction_result["ignored_files"]
        temp_dir_obj = extraction_result.get("temp_dir_obj")
        
        if not extracted_files:
            # Cleanup temp directory if no files to process
            if temp_dir_obj:
                temp_dir_obj.cleanup()
            
            logger.log_warning(
                "No processable files found in ZIP",
                filename=file.filename,
                total_ignored=len(ignored_files)
            )
            
            return ProcessingResponse(
                results=[],
                errors=[{"error": "No processable files found in ZIP"}],
                total_processed=0,
                success_count=0
            )
        
        logger.log_info(
            "ZIP extraction completed",
            filename=file.filename,
            extracted_files=len(extracted_files),
            ignored_files=len(ignored_files)
        )
        
        # Phases 2-6: Process files through the pipeline
        try:
            processing_response = await orchestrator.process_extracted_files(extracted_files)
        finally:
            # Cleanup temp directory after processing
            if temp_dir_obj:
                temp_dir_obj.cleanup()
                logger.log_info("Temporary directory cleaned up", filename=file.filename)
        
        logger.log_info(
            "ZIP processing pipeline completed",
            filename=file.filename,
            total_processed=processing_response.total_processed,
            success_count=processing_response.success_count,
            error_count=len(processing_response.errors)
        )
        
        return processing_response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        logger.log_error(
            "Unexpected error during ZIP processing",
            filename=file.filename if file else "unknown",
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "invoice_extraction"}


@router.get("/info")
async def service_info():
    """Get service information"""
    from config import settings
    
    return {
        "service_name": "WhatsApp Invoice Extraction API",
        "supported_file_types": settings.allowed_extensions,
        "max_file_size_mb": settings.max_file_size_mb,
        "gemini_model": settings.gemini_model,
        "processing_phases": [
            "Phase 1: ZIP validation and extraction",
            "Phase 2: Chronological file sorting", 
            "Phase 3: File type classification",
            "Phase 4: Content processing by type",
            "Phase 5: Structured data extraction",
            "Phase 6: Pipeline orchestration"
        ]
    }


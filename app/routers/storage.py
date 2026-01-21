"""
Additional endpoints for managing stored files
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from app.services.storage_service import storage_service
from app.utils.logger import setup_logger
from typing import Optional

logger = setup_logger("storage_router")

router = APIRouter(prefix="/storage", tags=["storage"])

@router.get("/files")
async def list_files(
    company_id: Optional[str] = Query(None, description="Company ID to filter files"),
    file_type: str = Query("uploads", description="File type: 'uploads' or 'results'"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of files to return")
):
    """
    List uploaded ZIPs or processed Excel files
    
    - **company_id**: Filter by company (optional)
    - **file_type**: 'uploads' for ZIPs, 'results' for Excel files
    - **limit**: Maximum results (1-1000)
    """
    try:
        if company_id:
            files = storage_service.list_company_files(
                company_id=company_id,
                file_type=file_type,
                limit=limit
            )
        else:
            # List all files if no company_id provided
            logger.log_warning(
                "Listing all files without company_id filter",
                file_type=file_type
            )
            files = []
        
        return {
            "files": files,
            "total": len(files),
            "company_id": company_id,
            "file_type": file_type
        }
        
    except Exception as e:
        logger.log_error(
            "Failed to list files",
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get("/download/{blob_path:path}")
async def download_file(blob_path: str):
    """
    Download a file from Cloud Storage by blob path
    
    - **blob_path**: Full path to blob (e.g., 'company123/2026/01/20260121_143025_facturas.zip')
    """
    try:
        file_content = storage_service.download_file(blob_path)
        
        if not file_content:
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {blob_path}"
            )
        
        # Determine content type from filename
        if blob_path.endswith('.zip'):
            media_type = "application/zip"
            filename = blob_path.split('/')[-1]
        elif blob_path.endswith('.xlsx'):
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = blob_path.split('/')[-1]
        else:
            media_type = "application/octet-stream"
            filename = blob_path.split('/')[-1]
        
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error(
            "Failed to download file",
            blob_path=blob_path,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )


@router.delete("/delete/{blob_path:path}")
async def delete_file(blob_path: str):
    """
    Delete a file from Cloud Storage
    
    - **blob_path**: Full path to blob
    
    ⚠️ Warning: This operation is permanent and cannot be undone
    """
    try:
        success = storage_service.delete_file(blob_path)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"File not found or could not be deleted: {blob_path}"
            )
        
        return {
            "status": "success",
            "message": f"File deleted: {blob_path}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error(
            "Failed to delete file",
            blob_path=blob_path,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import upload, storage
from app.utils.logger import setup_logger

# Initialize logger
logger = setup_logger()

app = FastAPI(
    title="WhatsApp Invoice Extraction API",
    description="Extract structured invoice data from WhatsApp ZIP files using Gemini 2.5 Flash-Lite",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router, prefix="/api/v1", tags=["upload"])
app.include_router(storage.router, prefix="/api/v1", tags=["storage"])

@app.get("/")
async def root():
    return {"message": "WhatsApp Invoice Extraction API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def run_dev():
    """Function to run the development server via Poetry script"""
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)

if __name__ == "__main__":
    run_dev()


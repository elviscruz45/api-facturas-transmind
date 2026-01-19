# WhatsApp Invoice Extraction API

FastAPI-based MVP system for extracting structured invoice data from WhatsApp ZIP exports using Google's Gemini 2.5 Flash-Lite Preview via Vertex AI.

## Features

- **Phase 1**: ZIP validation and secure file extraction
- **Phase 2**: Chronological ordering using WhatsApp timestamps
- **Phase 3**: File classification (text, images, PDFs)
- **Phase 4**: Type-specific processing with AI extraction
- **Phase 5**: Unified JSON schema for invoice data
- **Phase 6**: Sequential orchestration maintaining order

## Quick Setup with Poetry

### 1. Install Poetry (if not already installed)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Install Dependencies

```bash
cd api-facturas
poetry install
```

### 3. Google Cloud Setup

```bash
# Set up Application Default Credentials
gcloud auth application-default login

# Or use service account (recommended for production)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

### 4. Environment Configuration

```bash
cp .env.template .env
# Edit .env with your Google Cloud project details
```

### 5. Run the API

```bash
# Using Poetry script
poetry run start

# Or activate virtual environment and run manually
poetry shell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Testing with Insomnia

### 1. Health Check

```
GET http://localhost:8000/health
```

### 2. Service Info

```
GET http://localhost:8000/api/v1/info
```

### 3. Process ZIP File

```
POST http://localhost:8000/api/v1/process-zip
Content-Type: multipart/form-data

Body:
- file: [Select ZIP file from WhatsApp export]
```

## Expected Response Format

```json
{
  "results": [
    {
      "invoice_number": "INV-001",
      "invoice_date": "2024-01-15",
      "supplier_name": "Empresa ABC S.A.",
      "supplier_ruc": "20123456789",
      "total": 118.0,
      "currency": "PEN",
      "confidence_score": 0.95,
      "source_file": "IMG-20240115-WA0001.jpg",
      "sequence_id": 1
    }
  ],
  "errors": [],
  "total_processed": 5,
  "success_count": 1
}
```

## Project Structure

```
api-facturas/
├── pyproject.toml        # Poetry dependencies and scripts
├── app/
│   ├── routers/          # API endpoints
│   ├── services/         # Business logic
│   ├── processors/       # File processing by type
│   ├── models/          # Data models
│   ├── schemas/         # Pydantic schemas
│   └── utils/           # Utilities (auth, logging)
├── main.py              # FastAPI application
├── config.py            # Configuration settings
└── README.md            # This file
```

## Supported File Types

- **Text**: .txt files
- **Images**: .jpg, .jpeg, .png
- **Documents**: .pdf (text-based only in MVP)

## Development Commands

```bash
# Install dependencies
poetry install

# Add new dependency
poetry add package_name

# Add development dependency
poetry add --group dev package_name

# Run tests (when available)
poetry run pytest

# Format code
poetry run black .

# Sort imports
poetry run isort .

# Lint code
poetry run flake8
```

## Configuration Options

Edit `config.py` or use environment variables:

- `MAX_FILE_SIZE_MB`: Maximum ZIP file size (default: 50MB)
- `GEMINI_CONCURRENCY_LIMIT`: Concurrent AI requests (default: 5)
- `ALLOWED_EXTENSIONS`: Supported file types
- `GEMINI_MODEL`: AI model name (default: gemini-2.5-flash-lite-preview)

## Troubleshooting

### Common Issues

1. **Poetry not found**: Ensure Poetry is properly installed and in your PATH
2. **Authentication Error**: Ensure Google Cloud credentials are properly configured
3. **Large Files**: Check file size limits and processing timeouts
4. **Poor Extraction**: Verify image quality and text clarity

### Logs

The application provides structured logging for debugging:

- File processing events
- Extraction results with confidence scores
- Error details with context

## Next Steps (Future Implementation)

- Asynchronous job processing for large files
- Scanned PDF support with OCR
- Caching for duplicate detection
- Multi-tenant support
- Advanced monitoring and metrics
- Docker containerization
- CI/CD pipeline
# api-facturas-transmind

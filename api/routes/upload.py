"""
api/routes/upload.py
POST /api/upload — accepts multipart documents + optional transaction CSV.
Stores raw bytes in a temp cache keyed by case_id.
"""

import csv
import io
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.models import UploadResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory staging cache: {case_id: {"documents": [...], "transactions": [...]}}
# In production, replace with Redis or S3 presigned uploads.
_upload_cache: dict[str, dict] = {}

ALLOWED_DOC_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
ALLOWED_CSV_TYPES = {"text/csv", "text/plain", "application/csv", "application/octet-stream"}


def _parse_csv(content: bytes) -> list[dict]:
    """Parse CSV bytes into a list of row dicts."""
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    aadhaar: Optional[UploadFile] = File(None),
    pan: Optional[UploadFile] = File(None),
    salary_slip: Optional[UploadFile] = File(None),
    bank_statement: Optional[UploadFile] = File(None),
    transactions_csv: Optional[UploadFile] = File(None),
    case_id: Optional[str] = Form(None),
):
    """
    Accept KYC documents and transaction CSV.
    Returns a case_id that can be passed to /analyze.
    """
    cid = case_id or str(uuid.uuid4())
    documents: list[dict] = []
    uploaded_names: list[str] = []

    file_map = {
        "aadhaar": aadhaar,
        "pan": pan,
        "salary_slip": salary_slip,
        "bank_statement": bank_statement,
    }

    for doc_type, upload in file_map.items():
        if upload is None:
            continue
        content_type = upload.content_type or ""
        if content_type not in ALLOWED_DOC_TYPES and not upload.filename.endswith(".pdf"):
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type for {doc_type}: {content_type}",
            )
        content = await upload.read()
        if len(content) > 10 * 1024 * 1024:  # 10 MB limit
            raise HTTPException(status_code=413, detail=f"{doc_type} exceeds 10 MB limit.")
        documents.append({
            "doc_type": doc_type,
            "filename": upload.filename,
            "content": content,
        })
        uploaded_names.append(upload.filename)
        logger.info("Uploaded: %s (%d bytes)", upload.filename, len(content))

    # Parse transactions CSV
    transactions: list[dict] = []
    if transactions_csv:
        csv_content = await transactions_csv.read()
        transactions = _parse_csv(csv_content)
        uploaded_names.append(transactions_csv.filename)
        logger.info("Uploaded transaction CSV: %d rows", len(transactions))

    _upload_cache[cid] = {
        "documents": documents,
        "transactions": transactions,
    }

    return UploadResponse(
        case_id=cid,
        uploaded_files=uploaded_names,
        message=f"Uploaded {len(documents)} document(s) and {len(transactions)} transaction rows.",
    )


def get_upload_cache(case_id: str) -> dict:
    """Retrieve staged upload data for a given case_id."""
    return _upload_cache.get(case_id, {})


def clear_upload_cache(case_id: str) -> None:
    """Remove staged upload data after analysis completes."""
    _upload_cache.pop(case_id, None)

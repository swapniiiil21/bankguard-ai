"""
tools/ocr_tools.py
Tesseract OCR (primary) + AWS Textract (fallback) wrappers.
Returns structured JSON from document images / PDFs.
"""

import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import boto3
import pytesseract
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


# ---------------------------------------------------------------------------
# Tesseract helpers
# ---------------------------------------------------------------------------

def _preprocess_image(image: Image.Image) -> Image.Image:
    """Convert to greyscale and upscale small images for better OCR accuracy."""
    img = image.convert("L")  # greyscale
    w, h = img.size
    if w < 1000:
        scale = 1000 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def tesseract_extract(image_bytes: bytes) -> str:
    """Run Tesseract OCR on raw image bytes and return raw text."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        processed = _preprocess_image(image)
        config = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(processed, config=config)
        return text.strip()
    except Exception as exc:
        logger.error("Tesseract OCR failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# AWS Textract helpers
# ---------------------------------------------------------------------------

def _get_textract_client():
    """Build and return an AWS Textract client."""
    return boto3.client(
        "textract",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY or None,
    )


def textract_extract(image_bytes: bytes) -> str:
    """Use AWS Textract to extract text from an image (fallback path)."""
    try:
        client = _get_textract_client()
        response = client.detect_document_text(Document={"Bytes": image_bytes})
        lines = [
            block["Text"]
            for block in response.get("Blocks", [])
            if block["BlockType"] == "LINE"
        ]
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("Textract extraction failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Field parsing
# ---------------------------------------------------------------------------

def _parse_fields(raw_text: str, doc_type: str) -> dict[str, Any]:
    """
    Use regex heuristics to extract structured fields from OCR text.
    Falls back to empty strings for missing fields.
    """
    text = raw_text.upper()

    # Name — look for "Name:" pattern
    name_match = re.search(r"NAME[:\s]+([A-Z\s]{3,40})", text)
    name = name_match.group(1).strip().title() if name_match else ""

    # DOB
    dob_match = re.search(
        r"(?:DOB|DATE OF BIRTH|D\.O\.B)[:\s]+(\d{2}[/\-]\d{2}[/\-]\d{4})", text
    )
    dob = dob_match.group(1) if dob_match else ""

    # ID number (Aadhaar: 12 digits; PAN: 10 alphanums)
    aadhaar_match = re.search(r"\b(\d{4}\s\d{4}\s\d{4})\b", raw_text)
    pan_match = re.search(r"\b([A-Z]{5}\d{4}[A-Z])\b", raw_text)
    id_number = (
        aadhaar_match.group(1).replace(" ", "")
        if aadhaar_match
        else (pan_match.group(1) if pan_match else "")
    )

    # Employer
    employer_match = re.search(r"(?:EMPLOYER|COMPANY|ORGANIZATION)[:\s]+([A-Z\s&\.]{3,50})", text)
    employer = employer_match.group(1).strip().title() if employer_match else ""

    # Income
    income_match = re.search(
        r"(?:SALARY|INCOME|GROSS|NET PAY)[:\s₹,]*(\d[\d,]*)", raw_text, re.IGNORECASE
    )
    income_raw = income_match.group(1).replace(",", "") if income_match else "0"
    try:
        income = float(income_raw)
    except ValueError:
        income = 0.0

    # Address
    address_match = re.search(r"(?:ADDRESS|ADDR)[:\s]+(.{10,80})", text)
    address = address_match.group(1).strip().title() if address_match else ""

    return {
        "doc_type": doc_type,
        "name": name,
        "dob": dob,
        "id_number": id_number,
        "employer": employer,
        "income": income,
        "address": address,
        "raw_text": raw_text,
    }


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def extract_document(image_bytes: bytes, doc_type: str = "unknown") -> dict[str, Any]:
    """
    Primary entry point.
    1. Try Tesseract — if it yields ≥50 chars of text, use it.
    2. Otherwise fall back to AWS Textract.
    Returns structured dict with extracted fields.
    """
    raw_text = tesseract_extract(image_bytes)
    source = "tesseract"

    if len(raw_text) < 50:
        logger.info("Tesseract output too short (%d chars). Trying Textract…", len(raw_text))
        raw_text = textract_extract(image_bytes)
        source = "textract"

    if not raw_text:
        logger.warning("Both OCR engines returned empty text for doc_type=%s", doc_type)
        raw_text = ""

    result = _parse_fields(raw_text, doc_type)
    result["ocr_source"] = source
    return result


def extract_from_file(file_path: str | Path, doc_type: str = "unknown") -> dict[str, Any]:
    """Convenience wrapper that reads a file and calls extract_document."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")
    image_bytes = path.read_bytes()
    return extract_document(image_bytes, doc_type)

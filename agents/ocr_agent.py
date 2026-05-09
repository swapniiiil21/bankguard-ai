"""
agents/ocr_agent.py
OCRAgent — extracts structured data from uploaded KYC/loan documents.
"""

import logging
from typing import Any

from tools.ocr_tools import extract_document

logger = logging.getLogger(__name__)


class OCRAgent:
    """
    Processes raw document bytes for each uploaded file.
    Supports: Aadhaar, PAN, salary slip, bank statement.
    Primary engine: Tesseract. Fallback: AWS Textract.
    """

    name = "OCRAgent"

    # Map user-provided doc_type labels to canonical types
    DOC_TYPE_ALIASES: dict[str, str] = {
        "aadhaar": "aadhaar",
        "aadhar": "aadhaar",
        "pan": "pan",
        "pan_card": "pan",
        "salary": "salary_slip",
        "salary_slip": "salary_slip",
        "payslip": "salary_slip",
        "bank": "bank_statement",
        "bank_statement": "bank_statement",
        "statement": "bank_statement",
    }

    def run(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Process a list of document dicts.

        Args:
            documents: List of {doc_type: str, content: bytes} dicts.

        Returns:
            List of structured OCR result dicts.
        """
        results: list[dict[str, Any]] = []

        for doc in documents:
            doc_type = self.DOC_TYPE_ALIASES.get(
                doc.get("doc_type", "unknown").lower(), "unknown"
            )
            content: bytes = doc.get("content", b"")

            if not content:
                logger.warning("Empty content for doc_type=%s, skipping.", doc_type)
                results.append({"doc_type": doc_type, "error": "empty_content"})
                continue

            logger.info("Running OCR on doc_type=%s (%d bytes)", doc_type, len(content))
            try:
                extracted = extract_document(content, doc_type=doc_type)
                extracted["filename"] = doc.get("filename", "")
                results.append(extracted)
            except Exception as exc:
                logger.error("OCR failed for doc_type=%s: %s", doc_type, exc)
                results.append({"doc_type": doc_type, "error": str(exc)})

        return results

    def run_single(self, content: bytes, doc_type: str = "unknown") -> dict[str, Any]:
        """Convenience method for a single document."""
        return self.run([{"content": content, "doc_type": doc_type}])[0]

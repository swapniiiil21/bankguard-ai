"""
agents/kyc_agent.py
KYCVerificationAgent — detects document tampering, font inconsistency,
ID/DOB format issues, and semantic anomalies using Groq Llama 3.
"""

import logging
import re
from typing import Any

from tools.llm import call_llm

logger = logging.getLogger(__name__)

# ── Valid format regexes ───────────────────────────────────────────────────
AADHAAR_RE = re.compile(r"^\d{12}$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
DOB_RE = re.compile(r"^\d{2}[/\-]\d{2}[/\-]\d{4}$")


class KYCVerificationAgent:
    """
    Performs multi-layered KYC verification on OCR-extracted document data.
    Returns a structured result with kyc_status, confidence, and flags.
    """

    name = "KYCVerificationAgent"

    # ── Rule-based checks ──────────────────────────────────────────────────

    def _check_id_format(self, doc: dict[str, Any]) -> list[str]:
        flags: list[str] = []
        id_number = doc.get("id_number", "").replace(" ", "")
        doc_type = doc.get("doc_type", "")

        if doc_type == "aadhaar":
            if not AADHAAR_RE.match(id_number):
                flags.append(f"Invalid Aadhaar format: '{id_number}'")
        elif doc_type == "pan":
            if not PAN_RE.match(id_number.upper()):
                flags.append(f"Invalid PAN format: '{id_number}'")

        dob = doc.get("dob", "")
        if dob and not DOB_RE.match(dob):
            flags.append(f"Invalid DOB format: '{dob}'")

        return flags

    def _check_cross_document_consistency(
        self, docs: list[dict[str, Any]]
    ) -> list[str]:
        """Check name and DOB consistency across multiple documents."""
        flags: list[str] = []
        names = [
            d.get("name", "").strip().lower()
            for d in docs
            if d.get("name", "").strip()
        ]
        dobs = [
            d.get("dob", "").strip()
            for d in docs
            if d.get("dob", "").strip()
        ]

        unique_names = set(names)
        if len(unique_names) > 1:
            flags.append(f"Name mismatch across documents: {unique_names}")

        unique_dobs = set(dobs)
        if len(unique_dobs) > 1:
            flags.append(f"DOB mismatch across documents: {unique_dobs}")

        return flags

    # ── LLM-based analysis ─────────────────────────────────────────────────

    def _llm_tamper_analysis(self, docs: list[dict[str, Any]]) -> dict[str, Any]:
        """Send OCR text snippets to Groq LLM for tampering signal analysis."""
        doc_summaries = []
        for doc in docs:
            doc_summaries.append(
                f"Document Type: {doc.get('doc_type', 'unknown')}\n"
                f"Name: {doc.get('name', '')}\n"
                f"DOB: {doc.get('dob', '')}\n"
                f"ID Number: {doc.get('id_number', '')}\n"
                f"Employer: {doc.get('employer', '')}\n"
                f"Raw Text Snippet: {doc.get('raw_text', '')[:500]}\n"
            )

        prompt = f"""You are a KYC fraud detection expert at a bank.
Analyse the following OCR-extracted document data and identify any signs of:
1. Font inconsistency or unusual character spacing that may indicate editing
2. Mismatched or implausible dates
3. Suspicious patterns in ID numbers
4. Any other tampering signals

Documents:
{'---'.join(doc_summaries)}

Respond STRICTLY in this JSON format (no markdown, no explanation):
{{
  "tampering_suspected": true/false,
  "confidence": 0-100,
  "signals": ["signal1", "signal2"],
  "reasoning": "brief explanation"
}}"""

        raw = call_llm(prompt)
        try:
            import json
            # Strip markdown fences if present
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean)
        except Exception:
            logger.warning("KYC LLM response not valid JSON: %s", raw[:200])
            return {
                "tampering_suspected": False,
                "confidence": 50,
                "signals": [],
                "reasoning": raw[:300],
            }

    # ── Main run ───────────────────────────────────────────────────────────

    def run(self, raw_documents: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Perform full KYC verification on a list of OCR-extracted documents.

        Returns:
            {
              kyc_status: "clear" | "suspicious" | "failed",
              confidence: float (0-100),
              flags: list[str],
              llm_analysis: dict,
            }
        """
        if not raw_documents:
            return {
                "kyc_status": "failed",
                "confidence": 0.0,
                "flags": ["No documents provided"],
                "llm_analysis": {},
            }

        all_flags: list[str] = []

        # Rule-based checks per document
        for doc in raw_documents:
            all_flags.extend(self._check_id_format(doc))

        # Cross-document consistency
        all_flags.extend(self._check_cross_document_consistency(raw_documents))

        # LLM tamper analysis
        llm_result = self._llm_tamper_analysis(raw_documents)
        if llm_result.get("tampering_suspected"):
            all_flags.extend(llm_result.get("signals", []))

        # Determine status
        flag_count = len(all_flags)
        llm_confidence = llm_result.get("confidence", 50)

        if flag_count == 0 and not llm_result.get("tampering_suspected"):
            kyc_status = "clear"
            confidence = min(95.0, 100 - llm_confidence * 0.1)
        elif flag_count <= 2 and llm_confidence < 70:
            kyc_status = "suspicious"
            confidence = 50.0
        else:
            kyc_status = "failed"
            confidence = max(10.0, 100 - llm_confidence)

        return {
            "kyc_status": kyc_status,
            "confidence": round(confidence, 2),
            "flags": all_flags,
            "llm_analysis": llm_result,
        }

"""
agents/cross_reference_agent.py
CrossReferenceAgent — queries Pinecone for similar past fraud cases and
checks consistency of name/DOB/ID across all provided documents.
"""

import logging
from typing import Any

from tools.vector_store import query_similar_cases

logger = logging.getLogger(__name__)


class CrossReferenceAgent:
    """
    Correlates current case against historical fraud cases using vector search.
    Also validates cross-document field consistency.
    """

    name = "CrossReferenceAgent"

    def _build_query_text(
        self,
        raw_documents: list[dict[str, Any]],
        loan_form: dict[str, Any],
    ) -> str:
        """Build a plain-text query string from all available case data."""
        parts = []
        for doc in raw_documents:
            if doc.get("name"):
                parts.append(f"name:{doc['name']}")
            if doc.get("dob"):
                parts.append(f"dob:{doc['dob']}")
            if doc.get("id_number"):
                parts.append(f"id:{doc['id_number']}")
            if doc.get("employer"):
                parts.append(f"employer:{doc['employer']}")

        if loan_form.get("name"):
            parts.append(f"name:{loan_form['name']}")
        if loan_form.get("employer"):
            parts.append(f"employer:{loan_form['employer']}")

        return " | ".join(parts) if parts else "unknown case"

    def _find_mismatches(
        self,
        raw_documents: list[dict[str, Any]],
        loan_form: dict[str, Any],
    ) -> list[str]:
        """
        Cross-check name/DOB/ID/employer across all documents and loan form.
        Returns a list of mismatch descriptions.
        """
        mismatches: list[str] = []

        names: dict[str, str] = {}
        dobs: dict[str, str] = {}
        ids: dict[str, str] = {}
        employers: dict[str, str] = {}

        for doc in raw_documents:
            dt = doc.get("doc_type", "unknown")
            if doc.get("name"):
                names[dt] = doc["name"].strip().lower()
            if doc.get("dob"):
                dobs[dt] = doc["dob"].strip()
            if doc.get("id_number"):
                ids[dt] = doc["id_number"].strip()
            if doc.get("employer"):
                employers[dt] = doc["employer"].strip().lower()

        if loan_form.get("name"):
            names["loan_form"] = loan_form["name"].strip().lower()
        if loan_form.get("employer"):
            employers["loan_form"] = loan_form["employer"].strip().lower()

        def _check_field(field_map: dict[str, str], field_name: str) -> None:
            unique_vals = set(field_map.values())
            if len(unique_vals) > 1:
                mismatches.append(
                    f"{field_name} mismatch across documents: "
                    + ", ".join(f"{src}='{val}'" for src, val in field_map.items())
                )

        _check_field(names, "Name")
        _check_field(dobs, "Date of Birth")
        _check_field(employers, "Employer")

        # ID mismatches are flagged if a doc_type normally has a fixed ID
        # (e.g., two Aadhaar docs with different IDs)
        aadhaar_ids = [v for k, v in ids.items() if "aadhaar" in k]
        if len(set(aadhaar_ids)) > 1:
            mismatches.append(f"Multiple different Aadhaar numbers: {set(aadhaar_ids)}")

        return mismatches

    def _compute_cross_match_score(
        self, similar_cases: list[dict[str, Any]], mismatches: list[str]
    ) -> float:
        """
        Compute a cross-match risk score from 0–100.
        Higher = more suspicious.
        """
        score = 0.0

        # Similar case contribution (max 50 pts)
        if similar_cases:
            top_score = similar_cases[0].get("score", 0.0)
            score += min(50.0, top_score * 50)

        # Mismatch contribution (max 50 pts)
        score += min(50.0, len(mismatches) * 15)

        return round(score, 2)

    def run(
        self,
        raw_documents: list[dict[str, Any]],
        loan_form: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Run cross-reference checks for a given case.

        Returns:
            {
              cross_match_score: float,
              similar_cases: list,
              mismatches: list[str],
              query_text: str,
            }
        """
        query_text = self._build_query_text(raw_documents, loan_form)
        logger.info("CrossRefAgent querying Pinecone with: %s", query_text[:100])

        similar_cases = query_similar_cases(query_text, top_k=5)
        mismatches = self._find_mismatches(raw_documents, loan_form)
        cross_match_score = self._compute_cross_match_score(similar_cases, mismatches)

        return {
            "cross_match_score": cross_match_score,
            "similar_cases": similar_cases,
            "mismatches": mismatches,
            "query_text": query_text,
        }

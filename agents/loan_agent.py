"""
agents/loan_agent.py
LoanDocumentAgent — cross-checks salary vs bank credits, verifies employer,
and uses LLM for semantic inconsistency detection in loan applications.
"""

import json
import logging
import re
from typing import Any

from tools.llm import call_llm

logger = logging.getLogger(__name__)

# Mock MCA employer registry (India) — in production, call the MCA21 API
MOCK_MCA_REGISTRY: set[str] = {
    "Infosys Limited",
    "Tata Consultancy Services",
    "Wipro Limited",
    "HCL Technologies",
    "Tech Mahindra",
    "Accenture India",
    "IBM India",
    "Cognizant",
    "Capgemini India",
    "Reliance Industries",
    "HDFC Bank",
    "ICICI Bank",
    "State Bank of India",
    "Bajaj Finance",
    "Larsen & Toubro",
    "Mahindra & Mahindra",
    "Maruti Suzuki India",
    "Sun Pharmaceutical",
    "Asian Paints",
    "Hindustan Unilever",
}

INCOME_TOLERANCE_PCT = 0.15  # 15% tolerance for salary vs bank credit match


class LoanDocumentAgent:
    """
    Verifies loan application documents for income/employer fraud.
    """

    name = "LoanDocumentAgent"

    def _normalize_name(self, name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    def _check_income_match(
        self, salary_slip_income: float, bank_credits: float
    ) -> tuple[bool, str]:
        """
        Compare salary slip declared income with average monthly bank credits.
        Returns (match_ok, message).
        """
        if salary_slip_income <= 0:
            return False, "Salary slip income is zero or missing."
        if bank_credits <= 0:
            return False, "No significant credits found in bank statement."

        ratio = abs(salary_slip_income - bank_credits) / salary_slip_income
        if ratio <= INCOME_TOLERANCE_PCT:
            return True, f"Income match within {INCOME_TOLERANCE_PCT*100:.0f}% tolerance."
        else:
            return (
                False,
                f"Income mismatch: salary slip ₹{salary_slip_income:,.0f} vs "
                f"bank credits ₹{bank_credits:,.0f} (deviation {ratio*100:.1f}%).",
            )

    def _verify_employer(self, employer_name: str) -> tuple[bool, str]:
        """Check employer against mock MCA registry."""
        if not employer_name:
            return False, "Employer name not found in documents."

        normalized = self._normalize_name(employer_name)
        for registered in MOCK_MCA_REGISTRY:
            if self._normalize_name(registered) in normalized or normalized in self._normalize_name(registered):
                return True, f"Employer '{employer_name}' found in MCA registry."

        return False, f"Employer '{employer_name}' NOT found in MCA registry — may be unregistered or fake."

    def _llm_semantic_check(
        self, loan_form: dict[str, Any], ocr_docs: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Use LLM to detect subtle semantic inconsistencies across documents."""
        doc_texts = []
        for doc in ocr_docs:
            doc_texts.append(
                f"[{doc.get('doc_type', 'unknown')}] "
                f"Name: {doc.get('name', 'N/A')}, "
                f"Employer: {doc.get('employer', 'N/A')}, "
                f"Income: ₹{doc.get('income', 0):,.0f}, "
                f"DOB: {doc.get('dob', 'N/A')}"
            )

        prompt = f"""You are a loan fraud investigator.
Compare the loan application form with OCR-extracted document data and identify inconsistencies.

Loan Application Form:
{json.dumps(loan_form, indent=2)}

OCR-Extracted Document Data:
{chr(10).join(doc_texts)}

Check for:
1. Name mismatch between form and documents
2. Income declared on form vs. documents
3. Employer mismatch
4. Any implausible values (e.g., very high income for stated profession)
5. Inconsistent address or other fields

Respond STRICTLY in JSON (no markdown):
{{
  "semantic_flags": ["flag1", "flag2"],
  "inconsistency_score": 0-100,
  "analysis": "brief explanation"
}}"""

        raw = call_llm(prompt)
        try:
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean)
        except Exception:
            logger.warning("LoanAgent LLM response not valid JSON: %s", raw[:200])
            return {"semantic_flags": [], "inconsistency_score": 0, "analysis": raw[:300]}

    def run(
        self, raw_documents: list[dict[str, Any]], loan_form: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Full loan document verification.

        Returns:
            {
              income_match: bool,
              employer_verified: bool,
              flags: list[str],
              llm_semantic: dict,
              income_message: str,
              employer_message: str,
            }
        """
        flags: list[str] = []

        # Extract income from salary slip and bank statement
        salary_income = 0.0
        bank_credits = 0.0

        for doc in raw_documents:
            dt = doc.get("doc_type", "")
            income_val = float(doc.get("income", 0) or 0)
            if dt == "salary_slip":
                salary_income = income_val
            elif dt == "bank_statement":
                bank_credits = income_val  # monthly credits approximation

        # Income match check
        income_ok, income_msg = self._check_income_match(salary_income, bank_credits)
        if not income_ok:
            flags.append(income_msg)

        # Employer verification
        employer = ""
        for doc in raw_documents:
            if doc.get("employer"):
                employer = doc["employer"]
                break
        if not employer:
            employer = loan_form.get("employer", "")

        employer_ok, employer_msg = self._verify_employer(employer)
        if not employer_ok:
            flags.append(employer_msg)

        # LLM semantic check
        llm_result = self._llm_semantic_check(loan_form, raw_documents)
        flags.extend(llm_result.get("semantic_flags", []))

        return {
            "income_match": income_ok,
            "employer_verified": employer_ok,
            "flags": flags,
            "llm_semantic": llm_result,
            "income_message": income_msg,
            "employer_message": employer_msg,
            "salary_income": salary_income,
            "bank_credits": bank_credits,
        }

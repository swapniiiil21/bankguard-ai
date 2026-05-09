"""
graph/state.py
LangGraph TypedDict state schema for BankGuard AI workflow.
"""

from typing import Any, Literal, Optional
from typing_extensions import TypedDict


class BankGuardState(TypedDict, total=False):
    """
    Shared state object passed between all LangGraph nodes.
    Each agent reads relevant fields and writes its own output fields.
    """

    # ── Case metadata ─────────────────────────────────────────
    case_id: str                          # Unique UUID for this analysis run
    created_at: str                       # ISO-8601 timestamp

    # ── Raw inputs ────────────────────────────────────────────
    raw_documents: list[dict[str, Any]]   # OCR outputs per uploaded document
    transaction_data: list[dict[str, Any]]# Parsed CSV rows from tx history
    loan_form: dict[str, Any]             # Submitted loan application form data

    # ── Per-agent outputs ─────────────────────────────────────
    kyc_result: dict[str, Any]            # KYCVerificationAgent result
    transaction_result: dict[str, Any]    # TransactionAnalystAgent result
    loan_result: dict[str, Any]           # LoanDocumentAgent result
    cross_ref_result: dict[str, Any]      # CrossReferenceAgent result

    # ── Final outputs ─────────────────────────────────────────
    fraud_score: float                    # Weighted score 0–100
    final_report: str                     # Full narrative investigator report
    recommendation: Literal["Approve", "Review", "Reject & Escalate"]

    # ── Human-in-the-loop ─────────────────────────────────────
    human_approved: bool                  # True once a human reviewer confirms
    human_notes: str                      # Optional reviewer notes

    # ── Pipeline control ─────────────────────────────────────
    errors: list[str]                     # Non-fatal errors collected during run
    status: str                           # e.g. "running", "awaiting_review", "complete"

"""
agents/orchestrator.py
OrchestratorAgent — entry point that decomposes the case and routes to
specialist agents. Not a separate LangGraph node; its logic is embedded
in the graph's conditional edges and the workflow.py builder.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Orchestrator: validates inputs, assigns a case_id, and prepares the
    initial state for the LangGraph workflow.
    """

    name = "OrchestratorAgent"

    def run(
        self,
        documents: list[dict[str, Any]],
        transaction_data: list[dict[str, Any]],
        loan_form: dict[str, Any],
        case_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate and initialise the analysis state.

        Args:
            documents: List of raw document bytes dicts (doc_type + content).
            transaction_data: Parsed transaction rows.
            loan_form: Loan application form data.
            case_id: Optional external case ID; generated if not provided.

        Returns:
            Initial BankGuardState dict.
        """
        cid = case_id or str(uuid.uuid4())
        logger.info("Orchestrator initialising case: %s", cid)

        errors: list[str] = []
        if not documents:
            errors.append("No documents provided — KYC analysis will be limited.")
        if not transaction_data:
            errors.append("No transaction data — transaction analysis will be skipped.")
        if not loan_form:
            errors.append("No loan form data — loan analysis will be limited.")

        return {
            "case_id": cid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "raw_documents": [],          # populated by OCRAgent node
            "transaction_data": transaction_data or [],
            "loan_form": loan_form or {},
            "_input_documents": documents,  # passed to OCR node
            "kyc_result": {},
            "transaction_result": {},
            "loan_result": {},
            "cross_ref_result": {},
            "fraud_score": 0.0,
            "final_report": "",
            "recommendation": "Review",
            "human_approved": False,
            "human_notes": "",
            "errors": errors,
            "status": "running",
        }

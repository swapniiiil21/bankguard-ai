"""
graph/workflow.py
Full LangGraph StateGraph definition for BankGuard AI.

Pipeline flow:
  START → ocr_node
        → [kyc_node, transaction_node, loan_node]  (parallel via fan-out)
        → cross_ref_node
        → risk_report_node
        → human_review_node  (interrupt for human-in-the-loop)
        → END
"""

import logging
from typing import Any

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from graph.state import BankGuardState
from agents.ocr_agent import OCRAgent
from agents.kyc_agent import KYCVerificationAgent
from agents.transaction_agent import TransactionAnalystAgent
from agents.loan_agent import LoanDocumentAgent
from agents.cross_reference_agent import CrossReferenceAgent
from agents.risk_report_agent import RiskScoringAndReportAgent

logger = logging.getLogger(__name__)

# ── Singleton agent instances (reused across invocations) ─────────────────
_ocr = OCRAgent()
_kyc = KYCVerificationAgent()
_tx = TransactionAnalystAgent()
_loan = LoanDocumentAgent()
_xref = CrossReferenceAgent()
_risk = RiskScoringAndReportAgent()


# ── Node functions (each receives full state, returns partial state update) ──

def ocr_node(state: BankGuardState) -> dict[str, Any]:
    """Run OCR on all uploaded documents."""
    input_docs = state.get("_input_documents", [])
    logger.info("[OCR] Processing %d documents", len(input_docs))
    raw_documents = _ocr.run(input_docs)
    return {"raw_documents": raw_documents, "status": "ocr_complete"}


def kyc_node(state: BankGuardState) -> dict[str, Any]:
    """Run KYC verification on OCR-extracted documents."""
    logger.info("[KYC] Verifying documents for case %s", state.get("case_id"))
    result = _kyc.run(state.get("raw_documents", []))
    return {"kyc_result": result}


def transaction_node(state: BankGuardState) -> dict[str, Any]:
    """Run transaction anomaly analysis."""
    logger.info("[TX] Analysing %d transactions", len(state.get("transaction_data", [])))
    result = _tx.run(state.get("transaction_data", []))
    return {"transaction_result": result}


def loan_node(state: BankGuardState) -> dict[str, Any]:
    """Run loan document verification."""
    logger.info("[LOAN] Verifying loan documents for case %s", state.get("case_id"))
    result = _loan.run(
        state.get("raw_documents", []),
        state.get("loan_form", {}),
    )
    return {"loan_result": result}


def cross_ref_node(state: BankGuardState) -> dict[str, Any]:
    """Run cross-reference check against Pinecone fraud case history."""
    logger.info("[XREF] Cross-referencing case %s", state.get("case_id"))
    result = _xref.run(
        state.get("raw_documents", []),
        state.get("loan_form", {}),
    )
    return {"cross_ref_result": result}


def risk_report_node(state: BankGuardState) -> dict[str, Any]:
    """Compute fraud score and generate the investigator report."""
    logger.info("[RISK] Scoring case %s", state.get("case_id"))
    result = _risk.run(
        case_id=state.get("case_id", "unknown"),
        kyc_result=state.get("kyc_result", {}),
        tx_result=state.get("transaction_result", {}),
        loan_result=state.get("loan_result", {}),
        cross_ref=state.get("cross_ref_result", {}),
    )
    return {
        "fraud_score": result["fraud_score"],
        "recommendation": result["recommendation"],
        "final_report": result["final_report"],
        "status": "awaiting_review",
    }


def human_review_node(state: BankGuardState) -> dict[str, Any]:
    """
    Human-in-the-loop checkpoint.
    In LangGraph this node is interrupted; the graph resumes when the API
    endpoint calls graph.update_state() with human_approved=True.
    """
    logger.info("[HUMAN] Case %s awaiting human review", state.get("case_id"))
    # If already approved (state updated externally), mark complete.
    if state.get("human_approved"):
        return {"status": "complete"}
    # Otherwise the graph will pause here.
    return {"status": "awaiting_human_review"}


def _should_escalate(state: BankGuardState) -> str:
    """
    Conditional edge: determines whether to go directly to END
    or pause at human_review based on fraud score.
    High-score cases MUST pass human review.
    """
    score = state.get("fraud_score", 0.0)
    threshold = float(__import__("os").getenv("FRAUD_SCORE_THRESHOLD", "70"))
    if score >= threshold:
        return "human_review"
    return "end"


# ── Graph builder ──────────────────────────────────────────────────────────

def build_graph(use_memory: bool = True):
    """
    Construct and compile the BankGuard AI LangGraph StateGraph.

    Args:
        use_memory: If True, attach an in-memory checkpointer for HITL.

    Returns:
        Compiled LangGraph app.
    """
    builder = StateGraph(BankGuardState)

    # Register nodes
    builder.add_node("ocr", ocr_node)
    builder.add_node("kyc", kyc_node)
    builder.add_node("transaction", transaction_node)
    builder.add_node("loan", loan_node)
    builder.add_node("cross_ref", cross_ref_node)
    builder.add_node("risk_report", risk_report_node)
    builder.add_node("human_review", human_review_node)

    # Entry point
    builder.add_edge(START, "ocr")

    # Fan-out from OCR to parallel analysis nodes
    builder.add_edge("ocr", "kyc")
    builder.add_edge("ocr", "transaction")
    builder.add_edge("ocr", "loan")

    # Fan-in: all three must complete before cross-reference
    builder.add_edge("kyc", "cross_ref")
    builder.add_edge("transaction", "cross_ref")
    builder.add_edge("loan", "cross_ref")

    # Cross-ref → risk scoring
    builder.add_edge("cross_ref", "risk_report")

    # Conditional edge: high-risk cases go to human review
    builder.add_conditional_edges(
        "risk_report",
        _should_escalate,
        {"human_review": "human_review", "end": END},
    )

    # Human review → END
    builder.add_edge("human_review", END)

    checkpointer = MemorySaver() if use_memory else None
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"] if use_memory else [],
    )


# Module-level compiled graph for import by API
app_graph = build_graph(use_memory=True)

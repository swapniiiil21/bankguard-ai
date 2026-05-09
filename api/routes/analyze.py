"""
api/routes/analyze.py
POST /api/analyze  — triggers LangGraph workflow, returns fraud report.
GET  /api/cases    — returns all cases from MongoDB.
GET  /api/cases/{case_id} — returns a specific case.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from api.models import (
    AnalyzeRequest,
    CaseListResponse,
    CaseSummary,
    CrossRefResult,
    FraudReport,
    KYCResult,
    LoanResult,
    ScoreBreakdown,
    TransactionResult,
)
from api.routes.upload import clear_upload_cache, get_upload_cache

logger = logging.getLogger(__name__)
router = APIRouter()

FRAUD_THRESHOLD = float(os.getenv("FRAUD_SCORE_THRESHOLD", "70"))


# ── MongoDB helper ────────────────────────────────────────────────────────

def _get_db():
    """Lazy import motor to avoid startup failures when Mongo is unavailable."""
    try:
        import motor.motor_asyncio as motor  # noqa: PLC0415
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/bankguard")
        client = motor.AsyncIOMotorClient(mongo_uri)
        return client["bankguard"]["cases"]
    except Exception as exc:
        logger.warning("MongoDB unavailable: %s", exc)
        return None


# ── In-memory fallback store (used when MongoDB is not available) ──────────
_case_store: dict[str, dict] = {}


async def _save_case(case_data: dict) -> None:
    col = _get_db()
    if col is not None:
        try:
            await col.replace_one(
                {"case_id": case_data["case_id"]},
                case_data,
                upsert=True,
            )
            return
        except Exception as exc:
            logger.warning("Mongo save failed (%s), using in-memory fallback.", exc)
    _case_store[case_data["case_id"]] = case_data


async def _load_case(case_id: str) -> Optional[dict]:
    col = _get_db()
    if col is not None:
        try:
            doc = await col.find_one({"case_id": case_id}, {"_id": 0})
            if doc:
                return doc
        except Exception as exc:
            logger.warning("Mongo load failed: %s", exc)
    return _case_store.get(case_id)


async def _list_cases(skip: int, limit: int) -> list[dict]:
    col = _get_db()
    if col is not None:
        try:
            cursor = col.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
            return [doc async for doc in cursor]
        except Exception as exc:
            logger.warning("Mongo list failed: %s", exc)
    vals = list(_case_store.values())
    vals.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return vals[skip: skip + limit]


# ── Graph runner ──────────────────────────────────────────────────────────

def _run_graph(initial_state: dict[str, Any]) -> dict[str, Any]:
    """
    Execute the LangGraph workflow synchronously.
    Returns the final state dict.
    """
    from graph.workflow import app_graph  # noqa: PLC0415

    thread_config = {"configurable": {"thread_id": initial_state["case_id"]}}
    final_state: dict[str, Any] = {}

    for chunk in app_graph.stream(initial_state, config=thread_config):
        for node_name, node_output in chunk.items():
            logger.debug("Graph node '%s' output: %s", node_name, str(node_output)[:200])
            final_state.update(node_output)

    return final_state


def _build_fraud_report(case_id: str, state: dict[str, Any], loan_form: dict) -> dict:
    """Convert raw graph state into a serializable FraudReport dict."""
    kyc = state.get("kyc_result", {})
    tx = state.get("transaction_result", {})
    loan = state.get("loan_result", {})
    xref = state.get("cross_ref_result", {})

    # score_breakdown may come from risk_report node or be absent
    sb = state.get("score_breakdown", {})

    now = datetime.now(timezone.utc).isoformat()

    return {
        "case_id": case_id,
        "created_at": state.get("created_at", now),
        "fraud_score": state.get("fraud_score", 0.0),
        "recommendation": state.get("recommendation", "Review"),
        "kyc_result": {
            "kyc_status": kyc.get("kyc_status", "unknown"),
            "confidence": kyc.get("confidence", 0.0),
            "flags": kyc.get("flags", []),
            "llm_analysis": kyc.get("llm_analysis", {}),
        },
        "transaction_result": {
            "risk_level": tx.get("risk_level", "clear"),
            "anomaly_score": tx.get("anomaly_score", 0.0),
            "flagged_count": tx.get("flagged_count", 0),
            "total_transactions": tx.get("total_transactions", 0),
            "flagged_transactions": tx.get("flagged_transactions", []),
            "structuring_flags": tx.get("structuring_flags", []),
            "velocity_flags": tx.get("velocity_flags", []),
            "llm_summary": tx.get("llm_summary", ""),
        },
        "loan_result": {
            "income_match": loan.get("income_match", False),
            "employer_verified": loan.get("employer_verified", False),
            "flags": loan.get("flags", []),
            "income_message": loan.get("income_message", ""),
            "employer_message": loan.get("employer_message", ""),
            "salary_income": loan.get("salary_income", 0.0),
            "bank_credits": loan.get("bank_credits", 0.0),
        },
        "cross_ref_result": {
            "cross_match_score": xref.get("cross_match_score", 0.0),
            "similar_cases": xref.get("similar_cases", []),
            "mismatches": xref.get("mismatches", []),
        },
        "final_report": state.get("final_report", ""),
        "score_breakdown": sb if sb else None,
        "status": "complete",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=FraudReport)
async def analyze_case(request: AnalyzeRequest):
    """
    Trigger BankGuard AI fraud analysis for a previously uploaded case.
    """
    cached = get_upload_cache(request.case_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"No uploaded files found for case_id={request.case_id}. Call /upload first.",
        )

    documents = cached.get("documents", [])
    transactions = cached.get("transactions", [])
    loan_form_data = request.loan_form.model_dump()

    # Build initial orchestrator state
    from agents.orchestrator import OrchestratorAgent  # noqa: PLC0415
    orch = OrchestratorAgent()
    initial_state = orch.run(
        documents=documents,
        transaction_data=transactions,
        loan_form=loan_form_data,
        case_id=request.case_id,
    )

    # Override HITL flags if provided
    if request.human_approved:
        initial_state["human_approved"] = True
        initial_state["human_notes"] = request.human_notes

    # Run LangGraph pipeline
    try:
        final_state = _run_graph(initial_state)
    except Exception as exc:
        logger.exception("Graph execution failed for case %s", request.case_id)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    # Upsert to Pinecone for future cross-reference
    try:
        from tools.vector_store import upsert_case  # noqa: PLC0415
        summary = f"{loan_form_data.get('name', '')} | {loan_form_data.get('employer', '')} | score:{final_state.get('fraud_score', 0)}"
        upsert_case(
            case_id=request.case_id,
            case_summary=summary,
            metadata={
                "recommendation": final_state.get("recommendation", "Review"),
                "fraud_score": final_state.get("fraud_score", 0),
                "name": loan_form_data.get("name", ""),
            },
        )
    except Exception as exc:
        logger.warning("Pinecone upsert skipped: %s", exc)

    # Build and persist report
    report_dict = _build_fraud_report(request.case_id, final_state, loan_form_data)
    await _save_case(report_dict)

    # Clean staging cache
    clear_upload_cache(request.case_id)

    return FraudReport(**report_dict)


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    recommendation: Optional[str] = Query(None),
):
    """Return paginated list of past fraud cases."""
    cases = await _list_cases(skip, limit)
    if recommendation:
        cases = [c for c in cases if c.get("recommendation") == recommendation]

    summaries = [
        CaseSummary(
            case_id=c["case_id"],
            created_at=c["created_at"],
            fraud_score=c.get("fraud_score", 0.0),
            recommendation=c.get("recommendation", "Review"),
            status=c.get("status", "complete"),
        )
        for c in cases
    ]
    return CaseListResponse(total=len(summaries), cases=summaries)


@router.get("/cases/{case_id}", response_model=FraudReport)
async def get_case(case_id: str):
    """Return the full fraud report for a specific case."""
    case = await _load_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return FraudReport(**case)


@router.post("/cases/{case_id}/approve")
async def approve_case(case_id: str, notes: str = ""):
    """Mark a human-in-the-loop review as approved for a case."""
    case = await _load_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case["human_approved"] = True
    case["human_notes"] = notes
    case["status"] = "complete"
    await _save_case(case)
    return {"message": f"Case {case_id} approved.", "case_id": case_id}

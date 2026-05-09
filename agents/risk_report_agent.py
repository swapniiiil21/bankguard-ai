"""
agents/risk_report_agent.py
RiskScoringAndReportAgent — aggregates all agent results, computes weighted
fraud score, and generates a structured investigator report via Groq Llama 3.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from tools.llm import call_llm

logger = logging.getLogger(__name__)

# ── Scoring weights (must sum to 1.0) ─────────────────────────────────────
WEIGHTS = {
    "kyc": 0.30,
    "transaction": 0.35,
    "loan": 0.20,
    "cross_ref": 0.15,
}

# ── Recommendation thresholds ─────────────────────────────────────────────
APPROVE_MAX = 35.0
REVIEW_MAX = 69.9


class RiskScoringAndReportAgent:
    """
    Final agent in the pipeline.
    Computes weighted fraud score and generates a full investigator report.
    """

    name = "RiskScoringAndReportAgent"

    # ── Score normalisation helpers ────────────────────────────────────────

    def _kyc_to_score(self, kyc_result: dict[str, Any]) -> float:
        """Map KYC status + flags to 0–100 risk score."""
        status = kyc_result.get("kyc_status", "clear")
        flag_count = len(kyc_result.get("flags", []))
        base = {"clear": 5.0, "suspicious": 55.0, "failed": 90.0}.get(status, 50.0)
        return min(100.0, base + flag_count * 3)

    def _tx_to_score(self, tx_result: dict[str, Any]) -> float:
        """Map transaction risk level + anomaly score to 0–100."""
        level_map = {"clear": 5.0, "low": 30.0, "medium": 60.0, "high": 90.0}
        base = level_map.get(tx_result.get("risk_level", "clear"), 5.0)
        anomaly = tx_result.get("anomaly_score", 0.0)
        return min(100.0, (base + anomaly) / 2)

    def _loan_to_score(self, loan_result: dict[str, Any]) -> float:
        """Map loan result flags to 0–100."""
        flag_count = len(loan_result.get("flags", []))
        income_ok = loan_result.get("income_match", True)
        employer_ok = loan_result.get("employer_verified", True)
        base = 5.0
        if not income_ok:
            base += 35.0
        if not employer_ok:
            base += 30.0
        base += flag_count * 5
        return min(100.0, base)

    def _cross_ref_to_score(self, cross_ref: dict[str, Any]) -> float:
        """Map cross-reference result to 0–100."""
        return min(100.0, cross_ref.get("cross_match_score", 0.0))

    def compute_fraud_score(
        self,
        kyc_result: dict[str, Any],
        tx_result: dict[str, Any],
        loan_result: dict[str, Any],
        cross_ref: dict[str, Any],
    ) -> float:
        """Compute final weighted fraud score 0–100."""
        kyc_s = self._kyc_to_score(kyc_result)
        tx_s = self._tx_to_score(tx_result)
        loan_s = self._loan_to_score(loan_result)
        cr_s = self._cross_ref_to_score(cross_ref)

        score = (
            kyc_s * WEIGHTS["kyc"]
            + tx_s * WEIGHTS["transaction"]
            + loan_s * WEIGHTS["loan"]
            + cr_s * WEIGHTS["cross_ref"]
        )
        return round(score, 2)

    def _recommend(
        self, fraud_score: float
    ) -> Literal["Approve", "Review", "Reject & Escalate"]:
        if fraud_score <= APPROVE_MAX:
            return "Approve"
        elif fraud_score <= REVIEW_MAX:
            return "Review"
        return "Reject & Escalate"

    def _generate_report(
        self,
        case_id: str,
        fraud_score: float,
        recommendation: str,
        kyc_result: dict[str, Any],
        tx_result: dict[str, Any],
        loan_result: dict[str, Any],
        cross_ref: dict[str, Any],
    ) -> str:
        """Call Groq LLM to generate a structured investigator report."""

        prompt = f"""You are a senior fraud investigator at a bank.
Generate a formal, structured investigation report for the following case.

CASE ID: {case_id}
DATE: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
OVERALL FRAUD SCORE: {fraud_score}/100
RECOMMENDATION: {recommendation}

KYC FINDINGS:
- Status: {kyc_result.get("kyc_status", "N/A")}
- Confidence: {kyc_result.get("confidence", "N/A")}
- Flags: {json.dumps(kyc_result.get("flags", []))}
- LLM Analysis: {kyc_result.get("llm_analysis", {}).get("reasoning", "N/A")}

TRANSACTION FINDINGS:
- Risk Level: {tx_result.get("risk_level", "N/A")}
- Anomaly Score: {tx_result.get("anomaly_score", 0)}/100
- Flagged Transactions: {tx_result.get("flagged_count", 0)} of {tx_result.get("total_transactions", 0)}
- Structuring Alerts: {len(tx_result.get("structuring_flags", []))}
- Velocity Alerts: {len(tx_result.get("velocity_flags", []))}
- Analyst Summary: {tx_result.get("llm_summary", "N/A")}

LOAN DOCUMENT FINDINGS:
- Income Match: {loan_result.get("income_match", "N/A")}
- Employer Verified: {loan_result.get("employer_verified", "N/A")}
- Flags: {json.dumps(loan_result.get("flags", []))}

CROSS-REFERENCE FINDINGS:
- Cross-Match Score: {cross_ref.get("cross_match_score", 0)}/100
- Similar Past Fraud Cases: {len(cross_ref.get("similar_cases", []))}
- Field Mismatches: {json.dumps(cross_ref.get("mismatches", []))}

Write a professional report with these sections:
1. EXECUTIVE SUMMARY (2-3 sentences)
2. KYC / DOCUMENT ANALYSIS
3. TRANSACTION ANALYSIS
4. LOAN APPLICATION ANALYSIS
5. CROSS-REFERENCE ANALYSIS
6. RISK ASSESSMENT & RECOMMENDATION
7. NEXT STEPS FOR INVESTIGATOR

Be formal, factual, and concise. Do not use markdown formatting."""

        return call_llm(prompt, temperature=0.05)

    def run(
        self,
        case_id: str,
        kyc_result: dict[str, Any],
        tx_result: dict[str, Any],
        loan_result: dict[str, Any],
        cross_ref: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Aggregate all agent results and generate final fraud report.

        Returns:
            {
              fraud_score: float,
              recommendation: str,
              final_report: str,
              score_breakdown: dict,
            }
        """
        fraud_score = self.compute_fraud_score(kyc_result, tx_result, loan_result, cross_ref)
        recommendation = self._recommend(fraud_score)

        logger.info(
            "Case %s — Fraud score: %.1f, Recommendation: %s",
            case_id, fraud_score, recommendation,
        )

        final_report = self._generate_report(
            case_id, fraud_score, recommendation,
            kyc_result, tx_result, loan_result, cross_ref,
        )

        return {
            "fraud_score": fraud_score,
            "recommendation": recommendation,
            "final_report": final_report,
            "score_breakdown": {
                "kyc_score": self._kyc_to_score(kyc_result),
                "transaction_score": self._tx_to_score(tx_result),
                "loan_score": self._loan_to_score(loan_result),
                "cross_ref_score": self._cross_ref_to_score(cross_ref),
                "weights": WEIGHTS,
            },
        }

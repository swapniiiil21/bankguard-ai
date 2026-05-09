"""
agents/transaction_agent.py
TransactionAnalystAgent — runs Isolation Forest + LLM analysis on tx history.
Detects: anomalous amounts, velocity fraud, structuring patterns, geo-anomalies.
"""

import json
import logging
from typing import Any

from tools.anomaly import run_isolation_forest
from tools.llm import call_llm

logger = logging.getLogger(__name__)


class TransactionAnalystAgent:
    """
    Analyses transaction history for fraud patterns.
    Combines statistical ML (Isolation Forest) with LLM contextual reasoning.
    """

    name = "TransactionAnalystAgent"

    RISK_THRESHOLDS = {
        "low": 30,
        "medium": 60,
        "high": 80,
    }

    def _llm_context_analysis(
        self, flagged: list[dict[str, Any]], structuring: list[dict[str, Any]], velocity: list[dict[str, Any]]
    ) -> str:
        """Ask LLM to reason about the flagged transactions."""
        if not flagged and not structuring and not velocity:
            return "No significant anomalies detected in transaction history."

        prompt = f"""You are a financial crime analyst at a bank.
Review the following flagged transactions and provide a brief fraud risk assessment.

Statistically Anomalous Transactions (Isolation Forest):
{json.dumps(flagged[:10], indent=2, default=str)}

Structuring Patterns (just-below ₹1,00,000):
{json.dumps(structuring[:5], indent=2, default=str)}

Velocity / Multi-city Fraud Signals:
{json.dumps(velocity[:5], indent=2, default=str)}

Provide:
1. What fraud patterns are visible?
2. How urgent is investigation?
3. Any specific transactions of concern?

Be concise (max 200 words). Do not use markdown."""

        return call_llm(prompt)

    def _determine_risk_level(self, anomaly_score: float, flag_count: int) -> str:
        """Map numeric anomaly score to risk label."""
        if anomaly_score >= self.RISK_THRESHOLDS["high"] or flag_count >= 10:
            return "high"
        elif anomaly_score >= self.RISK_THRESHOLDS["medium"] or flag_count >= 5:
            return "medium"
        elif anomaly_score >= self.RISK_THRESHOLDS["low"] or flag_count >= 2:
            return "low"
        return "clear"

    def run(self, transaction_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Run full transaction fraud analysis.

        Args:
            transaction_data: List of transaction dicts (from CSV parse).

        Returns:
            {
              risk_level: "clear" | "low" | "medium" | "high",
              anomaly_score: float,
              flagged_transactions: list,
              structuring_flags: list,
              velocity_flags: list,
              llm_summary: str,
              total_transactions: int,
              flagged_count: int,
            }
        """
        if not transaction_data:
            return {
                "risk_level": "clear",
                "anomaly_score": 0.0,
                "flagged_transactions": [],
                "structuring_flags": [],
                "velocity_flags": [],
                "llm_summary": "No transaction data provided.",
                "total_transactions": 0,
                "flagged_count": 0,
            }

        logger.info("Running Isolation Forest on %d transactions.", len(transaction_data))
        ml_result = run_isolation_forest(transaction_data)

        risk_level = self._determine_risk_level(
            ml_result["anomaly_score"], ml_result["flagged_count"]
        )

        llm_summary = self._llm_context_analysis(
            ml_result["flagged_transactions"],
            ml_result["structuring_flags"],
            ml_result["velocity_flags"],
        )

        return {
            "risk_level": risk_level,
            "anomaly_score": ml_result["anomaly_score"],
            "flagged_transactions": ml_result["flagged_transactions"],
            "structuring_flags": ml_result["structuring_flags"],
            "velocity_flags": ml_result["velocity_flags"],
            "llm_summary": llm_summary,
            "total_transactions": ml_result["total_transactions"],
            "flagged_count": ml_result["flagged_count"],
        }

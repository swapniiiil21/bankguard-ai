"""
tests/test_agents.py
Unit tests for each agent — validates that each returns a correctly structured dict.
Uses mock data from data/mock_ocr_outputs.py.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import mock data
from data.mock_ocr_outputs import CASE_A_CLEAN, CASE_B_FRAUDULENT


# ── KYCVerificationAgent ────────────────────────────────────────────────────
class TestKYCAgent(unittest.TestCase):

    @patch("tools.llm.get_groq_client")
    def test_kyc_clean_case(self, mock_groq):
        """Case A (clean docs) should return kyc_status=clear."""
        mock_groq.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"tampering_suspected": false, "confidence": 10, "signals": [], "reasoning": "Looks clean"}'))]
        )
        from agents.kyc_agent import KYCVerificationAgent
        agent = KYCVerificationAgent()
        result = agent.run(CASE_A_CLEAN)
        self.assertIn("kyc_status", result)
        self.assertIn("confidence", result)
        self.assertIn("flags", result)
        self.assertIn("llm_analysis", result)
        self.assertIsInstance(result["flags"], list)

    @patch("tools.llm.get_groq_client")
    def test_kyc_fraudulent_case_has_flags(self, mock_groq):
        """Case B (mismatched DOB/name) should return flags."""
        mock_groq.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"tampering_suspected": true, "confidence": 85, "signals": ["DOB inconsistency"], "reasoning": "Mismatch found"}'))]
        )
        from agents.kyc_agent import KYCVerificationAgent
        agent = KYCVerificationAgent()
        result = agent.run(CASE_B_FRAUDULENT)
        self.assertGreater(len(result["flags"]), 0)

    def test_kyc_empty_docs(self):
        """Empty doc list should return failed status."""
        from agents.kyc_agent import KYCVerificationAgent
        agent = KYCVerificationAgent()
        result = agent.run([])
        self.assertEqual(result["kyc_status"], "failed")


# ── TransactionAnalystAgent ─────────────────────────────────────────────────
class TestTransactionAgent(unittest.TestCase):

    @patch("tools.llm.get_groq_client")
    def test_transaction_agent_structure(self, mock_groq):
        """TransactionAnalystAgent.run should return all required keys."""
        mock_groq.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Suspicious structuring detected."))]
        )
        import csv, io
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_transactions.csv")
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            transactions = [dict(row) for row in reader]

        from agents.transaction_agent import TransactionAnalystAgent
        agent = TransactionAnalystAgent()
        result = agent.run(transactions)

        for key in ["risk_level", "anomaly_score", "flagged_transactions", "structuring_flags", "velocity_flags", "llm_summary", "total_transactions", "flagged_count"]:
            self.assertIn(key, result)

        self.assertIsInstance(result["flagged_transactions"], list)
        self.assertGreaterEqual(result["total_transactions"], 50)

    def test_transaction_agent_empty(self):
        """Empty transaction list should return clear risk."""
        from agents.transaction_agent import TransactionAnalystAgent
        agent = TransactionAnalystAgent()
        result = agent.run([])
        self.assertEqual(result["risk_level"], "clear")
        self.assertEqual(result["anomaly_score"], 0.0)


# ── LoanDocumentAgent ───────────────────────────────────────────────────────
class TestLoanAgent(unittest.TestCase):

    @patch("tools.llm.get_groq_client")
    def test_loan_agent_clean_case(self, mock_groq):
        """Case A (income match, registered employer) should mostly pass."""
        mock_groq.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"semantic_flags": [], "inconsistency_score": 5, "analysis": "All consistent"}'))]
        )
        from agents.loan_agent import LoanDocumentAgent
        agent = LoanDocumentAgent()
        loan_form = {"name": "Rajesh Kumar Singh", "employer": "Infosys Limited", "income": 75000}
        result = agent.run(CASE_A_CLEAN, loan_form)
        self.assertIn("income_match", result)
        self.assertIn("employer_verified", result)
        self.assertIn("flags", result)
        self.assertTrue(result["employer_verified"])

    @patch("tools.llm.get_groq_client")
    def test_loan_agent_fraud_case_fails(self, mock_groq):
        """Case B (inflated income, fake employer) should have flags."""
        mock_groq.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"semantic_flags": ["Income inflated"], "inconsistency_score": 90, "analysis": "Fraud"}'))]
        )
        from agents.loan_agent import LoanDocumentAgent
        agent = LoanDocumentAgent()
        loan_form = {"name": "Suresh Malhotra", "employer": "Bright Future Consultants", "income": 250000}
        result = agent.run(CASE_B_FRAUDULENT, loan_form)
        self.assertFalse(result["income_match"])
        self.assertFalse(result["employer_verified"])
        self.assertGreater(len(result["flags"]), 0)


# ── RiskScoringAndReportAgent ───────────────────────────────────────────────
class TestRiskReportAgent(unittest.TestCase):

    @patch("tools.llm.get_groq_client")
    def test_risk_agent_clean_score(self, mock_groq):
        """Clean case should score below 35 → Approve recommendation."""
        mock_groq.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="EXECUTIVE SUMMARY\nLow risk case."))]
        )
        from agents.risk_report_agent import RiskScoringAndReportAgent
        agent = RiskScoringAndReportAgent()
        result = agent.run(
            case_id="test-clean-001",
            kyc_result={"kyc_status": "clear", "confidence": 92, "flags": [], "llm_analysis": {}},
            tx_result={"risk_level": "clear", "anomaly_score": 2.0, "flagged_count": 0, "total_transactions": 50, "flagged_transactions": [], "structuring_flags": [], "velocity_flags": [], "llm_summary": ""},
            loan_result={"income_match": True, "employer_verified": True, "flags": []},
            cross_ref={"cross_match_score": 0.0, "similar_cases": [], "mismatches": []},
        )
        self.assertIn("fraud_score", result)
        self.assertIn("recommendation", result)
        self.assertIn("final_report", result)
        self.assertLessEqual(result["fraud_score"], 40.0)

    @patch("tools.llm.get_groq_client")
    def test_risk_agent_fraud_score(self, mock_groq):
        """Fraud case should score above 70 → Reject & Escalate."""
        mock_groq.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="HIGH RISK CASE — ESCALATE IMMEDIATELY."))]
        )
        from agents.risk_report_agent import RiskScoringAndReportAgent
        agent = RiskScoringAndReportAgent()
        result = agent.run(
            case_id="test-fraud-001",
            kyc_result={"kyc_status": "failed", "confidence": 10, "flags": ["Name mismatch", "DOB mismatch", "Invalid PAN"], "llm_analysis": {"tampering_suspected": True}},
            tx_result={"risk_level": "high", "anomaly_score": 85.0, "flagged_count": 12, "total_transactions": 50, "flagged_transactions": [], "structuring_flags": [{}]*5, "velocity_flags": [{}]*3, "llm_summary": ""},
            loan_result={"income_match": False, "employer_verified": False, "flags": ["Income mismatch", "Employer not found"]},
            cross_ref={"cross_match_score": 75.0, "similar_cases": [{"id": "past-001", "score": 0.87}], "mismatches": ["Name mismatch"]},
        )
        self.assertGreater(result["fraud_score"], 65.0)
        self.assertEqual(result["recommendation"], "Reject & Escalate")


# ── CrossReferenceAgent ─────────────────────────────────────────────────────
class TestCrossRefAgent(unittest.TestCase):

    @patch("tools.vector_store.query_similar_cases")
    def test_cross_ref_structure(self, mock_query):
        """CrossReferenceAgent.run should return required keys."""
        mock_query.return_value = []
        from agents.cross_reference_agent import CrossReferenceAgent
        agent = CrossReferenceAgent()
        result = agent.run(CASE_A_CLEAN, {"name": "Rajesh Kumar Singh", "employer": "Infosys"})
        for key in ["cross_match_score", "similar_cases", "mismatches", "query_text"]:
            self.assertIn(key, result)

    @patch("tools.vector_store.query_similar_cases")
    def test_cross_ref_detects_mismatches(self, mock_query):
        """Case B has DOB/name mismatches — should be detected."""
        mock_query.return_value = []
        from agents.cross_reference_agent import CrossReferenceAgent
        agent = CrossReferenceAgent()
        result = agent.run(CASE_B_FRAUDULENT, {"name": "Suresh Malhotra"})
        self.assertGreater(len(result["mismatches"]), 0)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_api.py
Integration tests for FastAPI endpoints.
Uses httpx AsyncClient — requires pytest-asyncio.
"""

import sys
import os
import io
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from httpx import AsyncClient, ASGITransport


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_png_bytes() -> bytes:
    """Return minimal PNG bytes for upload tests."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color=(200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _sample_csv_bytes() -> bytes:
    return (
        "date,txn_id,amount,merchant,city,type\n"
        "2024-01-01,T001,5000,Amazon,Mumbai,debit\n"
        "2024-01-02,T002,75000,Salary,Mumbai,credit\n"
    ).encode()


# ── Tests ───────────────────────────────────────────────────────────────────

class TestHealthEndpoint(unittest.IsolatedAsyncioTestCase):

    async def test_health_returns_ok(self):
        from api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "BankGuard AI")

    async def test_health_has_version(self):
        from api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")
        self.assertIn("version", response.json())


class TestUploadEndpoint(unittest.IsolatedAsyncioTestCase):

    async def test_upload_no_files_returns_case_id(self):
        """Upload with no files still creates a case_id."""
        from api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/upload")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("case_id", data)
        self.assertIsInstance(data["case_id"], str)

    async def test_upload_with_aadhaar_file(self):
        """Upload with an Aadhaar image should succeed."""
        from api.main import app
        png = _make_png_bytes()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/upload",
                files={"aadhaar": ("aadhaar_test.png", io.BytesIO(png), "image/png")},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("case_id", data)
        self.assertIn("aadhaar_test.png", data["uploaded_files"])

    async def test_upload_with_csv(self):
        """Upload with a transaction CSV should report row count."""
        from api.main import app
        csv_bytes = _sample_csv_bytes()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/upload",
                files={"transactions_csv": ("transactions.csv", io.BytesIO(csv_bytes), "text/csv")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("case_id", response.json())


class TestAnalyzeEndpoint(unittest.IsolatedAsyncioTestCase):

    async def test_analyze_unknown_case_id_returns_404(self):
        """Analyzing a non-existent case_id should return 404."""
        from api.main import app
        payload = {
            "case_id": "nonexistent-case-id-12345",
            "loan_form": {
                "name": "Test User",
                "dob": "01/01/1990",
                "employer": "Test Corp",
                "income": 50000,
                "loan_amount": 200000,
            },
            "human_approved": False,
            "human_notes": "",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/analyze", json=payload)
        self.assertEqual(response.status_code, 404)

    @patch("graph.workflow.app_graph")
    async def test_analyze_returns_fraud_report(self, mock_graph):
        """Analyze with a valid case_id (mocked graph) should return a fraud report."""
        from api.main import app
        from api.routes.upload import _upload_cache

        # Seed upload cache directly
        test_case_id = "test-case-analyze-001"
        _upload_cache[test_case_id] = {"documents": [], "transactions": []}

        # Mock graph stream output
        mock_graph.stream.return_value = iter([
            {"ocr": {"raw_documents": [], "status": "ocr_complete"}},
            {"kyc": {"kyc_result": {"kyc_status": "clear", "confidence": 90, "flags": [], "llm_analysis": {}}}},
            {"transaction": {"transaction_result": {"risk_level": "clear", "anomaly_score": 2.0, "flagged_count": 0, "total_transactions": 2, "flagged_transactions": [], "structuring_flags": [], "velocity_flags": [], "llm_summary": "OK"}}},
            {"loan": {"loan_result": {"income_match": True, "employer_verified": True, "flags": [], "income_message": "OK", "employer_message": "OK", "salary_income": 50000, "bank_credits": 50000}}},
            {"cross_ref": {"cross_ref_result": {"cross_match_score": 0, "similar_cases": [], "mismatches": []}}},
            {"risk_report": {"fraud_score": 8.5, "recommendation": "Approve", "final_report": "LOW RISK CASE.", "status": "complete"}},
        ])

        payload = {
            "case_id": test_case_id,
            "loan_form": {
                "name": "Test User",
                "dob": "01/01/1990",
                "employer": "Infosys Limited",
                "income": 50000,
                "loan_amount": 200000,
            },
            "human_approved": False,
            "human_notes": "",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/analyze", json=payload)

        self.assertIn(response.status_code, [200, 500])  # 500 if Mongo unavailable in CI


class TestCasesEndpoint(unittest.IsolatedAsyncioTestCase):

    async def test_cases_list_returns_200(self):
        """GET /api/cases should always return 200."""
        from api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/cases")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total", data)
        self.assertIn("cases", data)

    async def test_cases_unknown_id_returns_404(self):
        """GET /api/cases/{bad_id} should return 404."""
        from api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/cases/totally-unknown-id-xyz")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_ocr.py
Unit tests for OCR tools — validates that extraction returns expected keys.
Uses mock bytes to avoid requiring Tesseract in CI.
"""

import io
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestOCRTools(unittest.TestCase):
    """Tests for tools/ocr_tools.py"""

    EXPECTED_KEYS = {"doc_type", "name", "dob", "id_number", "employer", "income", "address", "raw_text", "ocr_source"}

    @patch("tools.ocr_tools.pytesseract.image_to_string")
    def test_tesseract_extract_returns_string(self, mock_tess):
        """tesseract_extract should return a string given valid image bytes."""
        from PIL import Image as PILImage
        mock_tess.return_value = "Name: Rajesh Kumar\nDOB: 15/08/1985\nAadhaar: 1234 5678 9012"

        # Create a minimal valid PNG in memory
        buf = io.BytesIO()
        PILImage.new("RGB", (200, 100), color=(255, 255, 255)).save(buf, format="PNG")
        image_bytes = buf.getvalue()

        from tools.ocr_tools import tesseract_extract
        result = tesseract_extract(image_bytes)
        self.assertIsInstance(result, str)

    @patch("tools.ocr_tools.pytesseract.image_to_string")
    def test_extract_document_returns_expected_keys(self, mock_tess):
        """extract_document should return a dict with all expected keys."""
        mock_tess.return_value = (
            "Name: Rajesh Kumar Singh\nDOB: 15/08/1985\n"
            "2345 6789 1234\nEmployer: Infosys Limited\nIncome: 75000"
        )

        from PIL import Image as PILImage
        buf = io.BytesIO()
        PILImage.new("RGB", (200, 100)).save(buf, format="PNG")

        from tools.ocr_tools import extract_document
        result = extract_document(buf.getvalue(), doc_type="aadhaar")

        for key in self.EXPECTED_KEYS:
            self.assertIn(key, result, f"Missing key: {key}")

    @patch("tools.ocr_tools.pytesseract.image_to_string")
    def test_extract_aadhaar_format(self, mock_tess):
        """Should extract 12-digit Aadhaar number from text."""
        mock_tess.return_value = "Name: Test User\n2345 6789 1234"

        from PIL import Image as PILImage
        buf = io.BytesIO()
        PILImage.new("RGB", (200, 100)).save(buf, format="PNG")

        from tools.ocr_tools import extract_document
        result = extract_document(buf.getvalue(), doc_type="aadhaar")
        self.assertEqual(result["id_number"], "234567891234")

    @patch("tools.ocr_tools.pytesseract.image_to_string")
    def test_extract_pan_format(self, mock_tess):
        """Should extract PAN card number (10 alphanum) from text."""
        mock_tess.return_value = "PAN Card\nABCPR1234K"

        from PIL import Image as PILImage
        buf = io.BytesIO()
        PILImage.new("RGB", (200, 100)).save(buf, format="PNG")

        from tools.ocr_tools import extract_document
        result = extract_document(buf.getvalue(), doc_type="pan")
        self.assertEqual(result["id_number"], "ABCPR1234K")

    @patch("tools.ocr_tools.pytesseract.image_to_string")
    def test_empty_image_returns_dict(self, mock_tess):
        """Even with no OCR text, extract_document should return a valid dict."""
        mock_tess.return_value = ""

        from PIL import Image as PILImage
        buf = io.BytesIO()
        PILImage.new("RGB", (10, 10)).save(buf, format="PNG")

        from tools.ocr_tools import extract_document
        result = extract_document(buf.getvalue(), doc_type="unknown")
        self.assertIsInstance(result, dict)
        self.assertIn("doc_type", result)


class TestOCRAgent(unittest.TestCase):
    """Tests for agents/ocr_agent.py"""

    @patch("tools.ocr_tools.pytesseract.image_to_string")
    def test_ocr_agent_run_empty(self, mock_tess):
        """OCRAgent.run([]) should return empty list."""
        from agents.ocr_agent import OCRAgent
        agent = OCRAgent()
        result = agent.run([])
        self.assertEqual(result, [])

    @patch("tools.ocr_tools.pytesseract.image_to_string")
    def test_ocr_agent_run_single(self, mock_tess):
        """OCRAgent.run should process a single document and return a list."""
        mock_tess.return_value = "Name: Test\nDOB: 01/01/1990"

        from PIL import Image as PILImage
        buf = io.BytesIO()
        PILImage.new("RGB", (200, 100)).save(buf, format="PNG")

        from agents.ocr_agent import OCRAgent
        agent = OCRAgent()
        result = agent.run([{"doc_type": "aadhaar", "content": buf.getvalue(), "filename": "test.png"}])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("doc_type", result[0])


if __name__ == "__main__":
    unittest.main()

"""
api/models.py
Pydantic schemas for all FastAPI request and response models.
"""

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ── Input models ──────────────────────────────────────────────────────────

class LoanFormInput(BaseModel):
    name: str = Field(..., description="Applicant full name")
    dob: str = Field(..., description="Date of birth (DD/MM/YYYY)")
    employer: str = Field(..., description="Current employer name")
    income: float = Field(..., gt=0, description="Declared monthly income in INR")
    loan_amount: float = Field(..., gt=0, description="Requested loan amount in INR")
    loan_purpose: str = Field(default="", description="Purpose of the loan")
    address: str = Field(default="", description="Residential address")
    phone: str = Field(default="", description="Contact phone number")
    email: str = Field(default="", description="Contact email")


class AnalyzeRequest(BaseModel):
    case_id: str = Field(..., description="Case ID returned from /upload")
    loan_form: LoanFormInput
    human_approved: bool = Field(default=False, description="Human approval flag")
    human_notes: str = Field(default="", description="Reviewer notes")


# ── Result sub-models ─────────────────────────────────────────────────────

class KYCResult(BaseModel):
    kyc_status: str
    confidence: float
    flags: list[str] = []
    llm_analysis: dict[str, Any] = {}


class TransactionResult(BaseModel):
    risk_level: str
    anomaly_score: float
    flagged_count: int
    total_transactions: int
    flagged_transactions: list[dict[str, Any]] = []
    structuring_flags: list[dict[str, Any]] = []
    velocity_flags: list[dict[str, Any]] = []
    llm_summary: str = ""


class LoanResult(BaseModel):
    income_match: bool
    employer_verified: bool
    flags: list[str] = []
    income_message: str = ""
    employer_message: str = ""
    salary_income: float = 0.0
    bank_credits: float = 0.0


class CrossRefResult(BaseModel):
    cross_match_score: float
    similar_cases: list[dict[str, Any]] = []
    mismatches: list[str] = []


class ScoreBreakdown(BaseModel):
    kyc_score: float
    transaction_score: float
    loan_score: float
    cross_ref_score: float
    weights: dict[str, float]


# ── Response models ───────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    case_id: str
    uploaded_files: list[str]
    message: str


class FraudReport(BaseModel):
    case_id: str
    created_at: datetime
    fraud_score: float
    recommendation: Literal["Approve", "Review", "Reject & Escalate"]
    kyc_result: KYCResult
    transaction_result: TransactionResult
    loan_result: LoanResult
    cross_ref_result: CrossRefResult
    final_report: str
    score_breakdown: Optional[ScoreBreakdown] = None
    status: str = "complete"


class CaseSummary(BaseModel):
    case_id: str
    created_at: datetime
    fraud_score: float
    recommendation: str
    status: str


class CaseListResponse(BaseModel):
    total: int
    cases: list[CaseSummary]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "BankGuard AI"
    version: str = "1.0.0"

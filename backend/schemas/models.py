from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

class TransactionIngest(BaseModel):
    """Schema for incoming transactions from the API Gateway."""
    transaction_id: str = Field(default_factory=lambda: str(uuid4()))
    account_id: str = Field(..., description="Source account ID")
    destination_account_id: Optional[str] = Field(None, description="Target account ID")
    amount: float = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(default="USD", max_length=3)
    merchant_name: Optional[str] = None
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "account_id": "ACC_12345",
                "destination_account_id": "ACC_99887",
                "amount": 95000.00,
                "currency": "INR",
                "ip_address": "192.168.1.55",
                "device_id": "DEV_XY789"
            }
        }
    )

class InvestigationResult(BaseModel):
    """Schema for the final fraud verdict."""
    transaction_id: str
    fraud_score: float = Field(..., ge=0.0, le=100.0)
    verdict: str = Field(..., description="APPROVE, REVIEW, or REJECT")
    confidence: float
    explanation: str
    flagged_entities: List[str] = []
    
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: List[str] = []

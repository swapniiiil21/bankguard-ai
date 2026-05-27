import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
import os

# Ensure tools is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from tools.llm import call_llm

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/copilot",
    tags=["copilot"]
)

class CopilotRequest(BaseModel):
    message: str
    documents: list[str] = []

class CopilotResponse(BaseModel):
    response: str

@router.post("/chat", response_model=CopilotResponse)
async def chat_with_copilot(payload: CopilotRequest):
    """
    Interact with the BankGuard AI Investigation Copilot.
    """
    doc_context = ""
    if payload.documents:
        doc_context = f"\n\nThe user has uploaded the following evidence documents: {', '.join(payload.documents)}. Use this context to answer their question."

    system_prompt = (
        "You are BankGuard AI Copilot, an expert enterprise fraud investigation assistant. "
        "Your job is to assist human analysts by analyzing transaction metadata, graph intelligence, "
        "and answering questions concisely and professionally. Keep responses to 2-3 sentences. "
        f"{doc_context}"
        f"\n\nUser: {payload.message}"
    )
    
    try:
        response = call_llm(prompt=system_prompt)
        return {"response": response}
    except Exception as e:
        logger.error(f"Copilot LLM Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate AI response")

"""
Enterprise Supervisor Agent for LangGraph Orchestration
Implements the Hierarchical Agent routing pattern.
"""

from typing import Annotated, Any, Dict, List, Literal, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
import os

# The State represents the current memory/context of the investigation
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "The conversation history"]
    next_agent: str
    transaction_id: str
    fraud_score: float
    confidence: float
    investigation_reports: List[Dict[str, Any]]

# Define the specialized worker nodes
WORKER_NODES = ["planner", "risk_intelligence", "compliance", "reflection"]

def create_supervisor_agent(llm: ChatGroq) -> Any:
    """
    Creates the Supervisor Agent that dynamically routes execution to specialized workers
    based on the state of the investigation.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are the Lead Investigator (Supervisor) in the BankGuard AI enterprise fraud detection platform. "
         "You orchestrate a team of specialized agents: {workers}. "
         "Given the current investigation state and transaction anomalies, decide which agent should act next. "
         "If the investigation is complete and you have a definitive verdict, respond with 'FINISH'. "
         "Never make a final decision without consulting at least the risk_intelligence agent."
        ),
        MessagesPlaceholder(variable_name="messages"),
        ("system", "Given the above conversation, who should act next? Respond ONLY with one of the following: {workers} or 'FINISH'.")
    ])
    
    prompt = prompt.partial(workers=", ".join(WORKER_NODES))
    
    # In a production environment, we'd use OpenAI structured outputs or strict JSON parsing here.
    # For now, we chain it simply.
    supervisor_chain = prompt | llm 
    
    return supervisor_chain

def supervisor_node(state: AgentState):
    """The LangGraph Node representing the Supervisor execution."""
    llm = ChatGroq(model_name="llama3-70b-8192", temperature=0) # High-IQ reasoning model
    supervisor = create_supervisor_agent(llm)
    
    response = supervisor.invoke(state)
    next_step = response.content.strip().lower()
    
    # Handle routing hallucinations gracefully
    if next_step not in WORKER_NODES and next_step != "finish":
        next_step = "reflection" # Fallback to reflection if confused
        
    return {"next_agent": next_step}

# ---------------------------------------------------------
# Boilerplate Worker Nodes (To be implemented in Phase 1.b)
# ---------------------------------------------------------

def planner_node(state: AgentState):
    # Decomposes task
    return {"messages": [HumanMessage(content="Planner: Broke down investigation into 3 subtasks.")]}

def risk_intelligence_node(state: AgentState):
    # Queries Neo4j and Pinecone
    return {"messages": [HumanMessage(content="Risk Intel: Detected shared device anomaly in Neo4j.")]}

def compliance_node(state: AgentState):
    # Verifies KYC and AML constraints
    return {"messages": [HumanMessage(content="Compliance: KYC verified. No OFAC sanctions found.")]}

def reflection_node(state: AgentState):
    # Evaluates the accumulated findings
    return {"messages": [HumanMessage(content="Reflection: High confidence in fraud ring detection.")]}

def build_enterprise_graph() -> StateGraph:
    """Constructs the hierarchical LangGraph state machine."""
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("risk_intelligence", risk_intelligence_node)
    workflow.add_node("compliance", compliance_node)
    workflow.add_node("reflection", reflection_node)
    
    # Add Edges
    workflow.add_edge(START, "supervisor")
    
    # The Supervisor dynamically routes to the next agent or ends
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state["next_agent"],
        {
            "planner": "planner",
            "risk_intelligence": "risk_intelligence",
            "compliance": "compliance",
            "reflection": "reflection",
            "finish": END
        }
    )
    
    # All workers report back to the supervisor
    for node in WORKER_NODES:
        workflow.add_edge(node, "supervisor")
        
    return workflow.compile()

import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .routers import transactions, copilot
from .db.database import engine, Base
from .routers.transactions import producer as kafka_producer

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to manage DB connections and Kafka clients."""
    # Create tables if they don't exist (In prod, use Alembic migrations)
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schemas verified (MOCKED for local run).")
    yield
    # Shutdown Kafka producer
    if kafka_producer:
        await kafka_producer.stop()
    logger.info("Kafka producer stopped.")

app = FastAPI(
    title="BankGuard AI Enterprise API",
    description="Distributed orchestration gateway for Agentic Fraud Detection.",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telemetry Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    # In a full OTel setup, we would append traces to the Jaeger exporter here.
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Include Routers
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(copilot.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

import os
import json
import logging
from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.models import TransactionIngest
from ..db.database import get_db
from ..db.models import Investigation
from ..security.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    dependencies=[Depends(get_current_user)]
)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "transactions.raw"

# We initialize this in the main FastAPI startup event
producer: AIOKafkaProducer = None

async def get_kafka_producer() -> AIOKafkaProducer:
    global producer
    if producer is None:
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
        await producer.start()
    return producer

@router.post("/ingest", status_code=202)
async def ingest_transaction(
    payload: TransactionIngest,
    db: AsyncSession = Depends(get_db),
    kafka: AIOKafkaProducer = Depends(get_kafka_producer)
):
    """
    Ingests a transaction, saves the initial Investigation state to PostgreSQL,
    and publishes an event to Kafka for async processing by LangGraph workers.
    """
    
    # 1. Save Initial State to DB
    new_investigation = Investigation(
        transaction_id=payload.transaction_id,
        status="QUEUED"
    )
    db.add(new_investigation)
    await db.commit()
    
    # 2. Publish to Kafka
    try:
        msg_bytes = json.dumps(payload.model_dump(), default=str).encode("utf-8")
        await kafka.send_and_wait(topic=KAFKA_TOPIC, value=msg_bytes)
        logger.info(f"Transaction {payload.transaction_id} queued to Kafka.")
    except Exception as e:
        logger.error(f"Kafka publishing failed: {str(e)}")
        # Optionally implement an outbox pattern here
        raise HTTPException(status_code=500, detail="Failed to queue transaction.")

    return {
        "status": "Accepted",
        "transaction_id": payload.transaction_id,
        "message": "Transaction queued for asynchronous fraud analysis."
    }

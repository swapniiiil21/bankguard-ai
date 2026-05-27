import os
import json
import asyncio
import logging
from aiokafka import AIOKafkaConsumer
from langsmith import traceable

# We would import the actual supervisor agent from the src we built in Phase 1
# from src.agents.supervisor import build_enterprise_graph 
# For this worker file, we abstract the call.

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "transactions.raw"
GROUP_ID = "langgraph_workers"

@traceable(name="execute_fraud_investigation")
async def process_transaction(tx_data: dict):
    """
    Executes the LangGraph Supervisor agent. 
    Wrapped in @traceable to send token/latency metrics to LangSmith.
    """
    tx_id = tx_data.get("transaction_id")
    logger.info(f"Triggering LangGraph agent for transaction: {tx_id}")
    
    # Example pseudo-execution of the Graph
    # graph = build_enterprise_graph()
    # config = {"configurable": {"thread_id": tx_id}}
    # await graph.ainvoke({"transaction_id": tx_id, "messages": []}, config)
    
    # Simulate processing time
    await asyncio.sleep(2)
    logger.info(f"Investigation complete for {tx_id}")

async def consume():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=GROUP_ID,
        auto_offset_reset='earliest'
    )
    await consumer.start()
    logger.info("Kafka Consumer started. Listening for transactions...")
    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode('utf-8'))
            logger.info(f"Consumed message: {payload.get('transaction_id')}")
            
            try:
                await process_transaction(payload)
            except Exception as e:
                logger.error(f"Failed to process transaction {payload.get('transaction_id')}: {e}")
                # Implementation Note: Send to DLQ (Dead Letter Queue) here
                
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume())

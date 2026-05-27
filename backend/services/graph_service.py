import os
import logging
from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "securepassword123")

class GraphIntelligenceService:
    """
    Service layer interacting with Neo4j to build transaction graphs 
    and run Cypher queries for fraud ring detection.
    """
    
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        logger.info(f"Initialized Neo4j driver connected to {NEO4J_URI}")

    async def close(self):
        await self.driver.close()

    async def ingest_transaction(self, tx_data: dict) -> None:
        """
        Creates nodes and edges for a transaction asynchronously.
        """
        query = """
        MERGE (sender:Account {id: $account_id})
        MERGE (receiver:Account {id: $destination_account_id})
        MERGE (device:Device {id: $device_id})
        MERGE (ip:IPAddress {address: $ip_address})
        
        CREATE (tx:Transaction {id: $transaction_id, amount: $amount, timestamp: $timestamp})
        
        MERGE (sender)-[:MADE_TRANSACTION]->(tx)
        MERGE (tx)-[:TRANSFERRED_TO]->(receiver)
        
        WITH sender, device, ip
        WHERE device.id IS NOT NULL AND ip.address IS NOT NULL
        MERGE (sender)-[:USED_DEVICE]->(device)
        MERGE (sender)-[:LOGGED_IN_FROM]->(ip)
        """
        
        async with self.driver.session() as session:
            await session.run(query, **tx_data)
            logger.debug(f"Graph updated for transaction {tx_data.get('transaction_id')}")

    async def detect_shared_device_ring(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Detects if this account is sharing a device with other accounts that 
        have made high-velocity transfers.
        """
        query = """
        MATCH (a:Account {id: $account_id})-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(other:Account)
        WHERE a <> other
        RETURN other.id AS linked_account, d.id AS shared_device
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, account_id=account_id)
            records = await result.data()
            return records

# Singleton dependency
graph_service = GraphIntelligenceService()

async def get_graph_service() -> GraphIntelligenceService:
    return graph_service

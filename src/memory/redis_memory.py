"""
Enterprise Redis Memory Module for BankGuard AI
Implements low-latency episodic memory for LangGraph agent checkpoints.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from typing import Optional, Dict, Any
import json
import redis.asyncio as redis
import os
import logging

logger = logging.getLogger(__name__)

class AsyncRedisSaver(BaseCheckpointSaver):
    """
    A custom LangGraph CheckpointSaver that uses Redis for high-speed,
    distributed state management across the Kubernetes agent worker pods.
    """
    
    def __init__(self, redis_url: str):
        super().__init__()
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
        
    async def get_client(self) -> redis.Redis:
        """Lazy initialization of the Redis client."""
        if self._client is None:
            logger.info(f"Connecting to Redis at {self.redis_url}")
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def aput(self, config: Dict[str, Any], checkpoint: Dict[str, Any]) -> None:
        """Saves a checkpoint (agent state) to Redis asynchronously."""
        client = await self.get_client()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]
        
        # We use a hash to store the checkpoint and its metadata
        key = f"checkpoint:{thread_id}:{checkpoint_id}"
        
        # Serialize the state
        # In a real enterprise app, ensure custom encoders for complex Langchain message types
        serialized_state = json.dumps(checkpoint, default=str)
        
        await client.hset(
            name=key,
            mapping={
                "checkpoint": serialized_state,
                "timestamp": checkpoint["ts"]
            }
        )
        
        # Maintain a sorted set of checkpoints for this thread to easily get the latest
        await client.zadd(
            name=f"thread:{thread_id}:checkpoints",
            mapping={checkpoint_id: float(checkpoint["ts"])}
        )
        
        # Set an expiration for active working memory (e.g., 24 hours)
        # Long-term storage will be pushed to Postgres
        await client.expire(key, 86400)
        
        logger.debug(f"Saved checkpoint {checkpoint_id} for thread {thread_id}")

    async def aget(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Retrieves a checkpoint from Redis asynchronously."""
        client = await self.get_client()
        thread_id = config["configurable"]["thread_id"]
        
        # Get latest checkpoint ID from the sorted set
        latest_items = await client.zrevrange(f"thread:{thread_id}:checkpoints", 0, 0)
        
        if not latest_items:
            return None
            
        checkpoint_id = latest_items[0]
        key = f"checkpoint:{thread_id}:{checkpoint_id}"
        
        checkpoint_data = await client.hget(key, "checkpoint")
        if not checkpoint_data:
            return None
            
        return json.loads(checkpoint_data)

# Singleton instance for the application
def get_redis_saver() -> AsyncRedisSaver:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return AsyncRedisSaver(redis_url)

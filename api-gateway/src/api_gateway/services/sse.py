import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import Request

from api_gateway.services.redis_protocol import RedisProtocol


class SSEService:
    def __init__(self, redis: RedisProtocol, heartbeat: float) -> None:
        self.redis, self.heartbeat = redis, heartbeat

    async def stream(self, request: Request, account_id: str, generation_id: str) -> AsyncIterator[str]:
        channel = f"ai:stream:{account_id}:{generation_id}"
        iterator = self.redis.subscribe(channel)
        try:
            while not await request.is_disconnected():
                try:
                    message = await asyncio.wait_for(iterator.__anext__(), timeout=self.heartbeat)
                    payload = json.loads(str(message["data"]))
                    event = payload.get("event", "message")
                    data = json.dumps(payload.get("data", {}), separators=(",", ":"))
                    yield f"event: {event}\ndata: {data}\n\n"
                    if event in {"completed", "failed"}:
                        break
                except TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
                except StopAsyncIteration:
                    break
        finally:
            await iterator.aclose()

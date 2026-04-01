
import asyncio
import random
from typing import Dict
from .models import Request, calculate_token_consumption
from .monitor import ResourceMonitor


class MockLLMPool:
    def __init__(self, monitor: ResourceMonitor, min_delay_ms: int = 100, max_delay_ms: int = 500):
        self.monitor = monitor
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms

    async def process_request(self, request: Request) -> Dict:
        self.monitor.record_request(request)
        delay_ms = random.uniform(self.min_delay_ms, self.max_delay_ms)
        delay_seconds = delay_ms / 1000.0
        await asyncio.sleep(delay_seconds)
        token_consumption = calculate_token_consumption(request)
        return {
            "request_id": request.request_id,
            "scene_id": request.scene_id,
            "status": "completed",
            "token_consumption": token_consumption,
            "response": "Mock LLM response based on prompt..."
        }

    def set_delay_range(self, min_ms: int, max_ms: int):
        self.min_delay_ms = min_ms
        self.max_delay_ms = max_ms


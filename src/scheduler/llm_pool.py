"""LLM处理池模块。

本模块提供了LLM请求处理的模拟实现，用于测试和开发环境。
模拟池可以配置延迟范围，模拟真实的LLM响应时间。

主要功能:
    - 模拟LLM请求处理
    - 可配置的响应延迟
    - 资源使用记录
"""

import asyncio
import logging
import random
from typing import Dict
from .models import Request, calculate_token_consumption
from .monitor import ResourceMonitor

logger = logging.getLogger(__name__)


class MockLLMPool:
    """模拟LLM处理池，用于测试和开发。

    该类模拟真实的LLM服务，提供可配置的延迟和模拟响应。
    处理请求时会记录资源使用情况到监控器。

    Attributes:
        monitor: 资源监控器，用于记录请求处理。
        min_delay_ms: 最小延迟时间（毫秒）。
        max_delay_ms: 最大延迟时间（毫秒）。

    Example:
        >>> from src.scheduler.monitor import ResourceMonitor
        >>> monitor = ResourceMonitor()
        >>> llm_pool = MockLLMPool(monitor, min_delay_ms=50, max_delay_ms=200)
        >>> request = Request(scene_id="test", prompt="Hello", max_output_token=100)
        >>> result = await llm_pool.process_request(request)
        >>> print(result["status"])
        completed
    """

    def __init__(self, monitor: ResourceMonitor, min_delay_ms: int = 100, max_delay_ms: int = 500) -> None:
        """初始化模拟LLM处理池。

        Args:
            monitor: 资源监控器实例，用于记录请求处理。
            min_delay_ms: 最小延迟时间（毫秒），默认为100ms。
            max_delay_ms: 最大延迟时间（毫秒），默认为500ms。
        """
        self.monitor: ResourceMonitor = monitor
        self.min_delay_ms: int = min_delay_ms
        self.max_delay_ms: int = max_delay_ms

    async def process_request(self, request: Request) -> Dict[str, object]:
        """处理请求并返回模拟结果。

        模拟LLM处理过程，包括随机延迟和资源记录。
        延迟时间在min_delay_ms和max_delay_ms之间随机选择。

        Args:
            request: 要处理的请求对象。

        Returns:
            包含处理结果的字典，包括:
            - request_id: 请求ID
            - scene_id: 场景ID
            - status: 处理状态（"completed"）
            - token_consumption: Token消耗量
            - response: 模拟响应文本

        Example:
            >>> result = await llm_pool.process_request(request)
            >>> print(result["response"])
            Mock LLM response based on prompt...
        """
        logger.debug(f"Processing request started: request_id={request.request_id}, scene_id={request.scene_id}")
        self.monitor.record_request(request)
        delay_ms = random.uniform(self.min_delay_ms, self.max_delay_ms)
        delay_seconds = delay_ms / 1000.0
        await asyncio.sleep(delay_seconds)
        token_consumption = calculate_token_consumption(request)
        logger.info(f"Request processed: request_id={request.request_id}, token_consumption={token_consumption}")
        return {
            "request_id": request.request_id,
            "scene_id": request.scene_id,
            "status": "completed",
            "token_consumption": token_consumption,
            "response": "Mock LLM response based on prompt..."
        }

    def set_delay_range(self, min_ms: int, max_ms: int) -> None:
        """设置延迟范围。

        用于动态调整模拟延迟，模拟不同的LLM响应时间。

        Args:
            min_ms: 新的最小延迟时间（毫秒）。
            max_ms: 新的最大延迟时间（毫秒）。

        Example:
            >>> llm_pool.set_delay_range(200, 1000)  # 设置更长的延迟
        """
        self.min_delay_ms = min_ms
        self.max_delay_ms = max_ms
        logger.info(f"Delay range updated: min_ms={min_ms}, max_ms={max_ms}")


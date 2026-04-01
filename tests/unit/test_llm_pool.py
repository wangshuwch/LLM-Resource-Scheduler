
import pytest
import asyncio
import time
from src.scheduler.llm_pool import MockLLMPool
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.models import Request


def test_mock_llm_pool_initialization():
    monitor = ResourceMonitor()
    pool = MockLLMPool(monitor)
    assert pool.monitor == monitor
    assert pool.min_delay_ms == 100
    assert pool.max_delay_ms == 500


def test_mock_llm_pool_custom_delay():
    monitor = ResourceMonitor()
    pool = MockLLMPool(monitor, min_delay_ms=200, max_delay_ms=300)
    assert pool.min_delay_ms == 200
    assert pool.max_delay_ms == 300


def test_set_delay_range():
    monitor = ResourceMonitor()
    pool = MockLLMPool(monitor)
    pool.set_delay_range(50, 100)
    assert pool.min_delay_ms == 50
    assert pool.max_delay_ms == 100


@pytest.mark.asyncio
async def test_process_request_basic():
    monitor = ResourceMonitor()
    pool = MockLLMPool(monitor, min_delay_ms=1, max_delay_ms=1)
    request = Request(
        scene_id="test_scene",
        prompt="Hello world",
        max_output_token=100
    )
    response = await pool.process_request(request)
    assert response["request_id"] == request.request_id
    assert response["scene_id"] == "test_scene"
    assert response["status"] == "completed"
    assert response["token_consumption"] > 0
    assert "Mock LLM response" in response["response"]


@pytest.mark.asyncio
async def test_process_request_records_to_monitor():
    monitor = ResourceMonitor()
    pool = MockLLMPool(monitor, min_delay_ms=1, max_delay_ms=1)
    request = Request(
        scene_id="test_scene",
        prompt="Hello world",
        max_output_token=100
    )
    await pool.process_request(request)
    total_load = monitor.get_total_load()
    assert total_load.qpm == 1
    assert total_load.tpm > 0
    scene_load = monitor.get_scene_load("test_scene")
    assert scene_load.qpm == 1


@pytest.mark.asyncio
async def test_delay_simulation():
    monitor = ResourceMonitor()
    pool = MockLLMPool(monitor, min_delay_ms=50, max_delay_ms=50)
    request = Request(
        scene_id="test_scene",
        prompt="Hello",
        max_output_token=10
    )
    start_time = time.time()
    await pool.process_request(request)
    elapsed_ms = (time.time() - start_time) * 1000
    assert elapsed_ms >= 50
    assert elapsed_ms < 150


@pytest.mark.asyncio
async def test_multiple_requests():
    monitor = ResourceMonitor()
    pool = MockLLMPool(monitor, min_delay_ms=1, max_delay_ms=1)
    requests = [
        Request(scene_id=f"scene_{i}", prompt=f"Prompt {i}", max_output_token=10)
        for i in range(3)
    ]
    tasks = [pool.process_request(req) for req in requests]
    responses = await asyncio.gather(*tasks)
    assert len(responses) == 3
    for i, response in enumerate(responses):
        assert response["scene_id"] == f"scene_{i}"
    total_load = monitor.get_total_load()
    assert total_load.qpm == 3

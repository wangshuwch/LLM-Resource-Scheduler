
import pytest
import asyncio
from src.scheduler.models import Request, calculate_token_consumption
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool


@pytest.fixture
def resource_monitor():
    return ResourceMonitor()


@pytest.fixture
def mock_llm_pool(resource_monitor):
    return MockLLMPool(resource_monitor, min_delay_ms=10, max_delay_ms=50)


@pytest.mark.asyncio
async def test_complete_request_flow(mock_llm_pool, resource_monitor):
    request = Request(
        scene_id="integration_scene_1",
        prompt="Test prompt for integration testing",
        max_output_token=200
    )
    
    total_load_before = resource_monitor.get_total_load()
    assert total_load_before.qpm == 0
    assert total_load_before.tpm == 0
    
    result = await mock_llm_pool.process_request(request)
    
    assert result["request_id"] == request.request_id
    assert result["scene_id"] == "integration_scene_1"
    assert result["status"] == "completed"
    assert "token_consumption" in result
    assert result["token_consumption"] == calculate_token_consumption(request)
    
    total_load_after = resource_monitor.get_total_load()
    assert total_load_after.qpm == 1
    assert total_load_after.tpm == result["token_consumption"]
    
    scene_load = resource_monitor.get_scene_load("integration_scene_1")
    assert scene_load.qpm == 1
    assert scene_load.tpm == result["token_consumption"]


@pytest.mark.asyncio
async def test_concurrent_requests(mock_llm_pool, resource_monitor):
    requests = []
    for i in range(10):
        requests.append(Request(
            scene_id=f"concurrent_scene_{i % 3}",
            prompt=f"Concurrent request {i}",
            max_output_token=100
        ))
    
    tasks = [mock_llm_pool.process_request(req) for req in requests]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 10
    for result in results:
        assert result["status"] == "completed"
    
    total_load = resource_monitor.get_total_load()
    assert total_load.qpm == 10
    
    all_scenes_load = resource_monitor.get_all_scenes_load()
    assert len(all_scenes_load) == 3
    for scene_id, load in all_scenes_load.items():
        assert load.qpm in [3, 4]


@pytest.mark.asyncio
async def test_resource_statistics_accuracy(mock_llm_pool, resource_monitor):
    scene1_requests = []
    scene2_requests = []
    
    for i in range(5):
        req = Request(
            scene_id="stats_scene_1",
            prompt=f"Stats request scene 1 - {i}",
            max_output_token=50
        )
        scene1_requests.append(req)
    
    for i in range(3):
        req = Request(
            scene_id="stats_scene_2",
            prompt=f"Stats request scene 2 - {i}",
            max_output_token=150
        )
        scene2_requests.append(req)
    
    all_requests = scene1_requests + scene2_requests
    tasks = [mock_llm_pool.process_request(req) for req in all_requests]
    results = await asyncio.gather(*tasks)
    
    total_expected_tokens = sum(r["token_consumption"] for r in results)
    
    total_load = resource_monitor.get_total_load()
    assert total_load.qpm == 8
    assert total_load.tpm == total_expected_tokens
    
    scene1_load = resource_monitor.get_scene_load("stats_scene_1")
    assert scene1_load.qpm == 5
    
    scene2_load = resource_monitor.get_scene_load("stats_scene_2")
    assert scene2_load.qpm == 3

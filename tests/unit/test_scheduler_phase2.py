
import pytest
import asyncio
from src.scheduler.models import Scene, Request, RequestStatus
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool
from src.scheduler.scheduler import Scheduler
from src.scheduler.config import SceneConfigManager


@pytest.fixture
def resource_monitor():
    return ResourceMonitor()


@pytest.fixture
def mock_llm_pool(resource_monitor):
    return MockLLMPool(resource_monitor, min_delay_ms=10, max_delay_ms=50)


@pytest.fixture
def scene_config_manager():
    return SceneConfigManager()


@pytest.fixture
def scheduler(resource_monitor, mock_llm_pool, scene_config_manager):
    return Scheduler(
        resource_monitor,
        mock_llm_pool,
        total_qpm_limit=100,
        total_tpm_limit=100000,
        scene_config_manager=scene_config_manager
    )


@pytest.mark.asyncio
async def test_scheduler_with_scene_config_manager(scheduler, scene_config_manager):
    assert scheduler.scene_config_manager is not None
    assert scheduler.scene_config_manager == scene_config_manager


@pytest.mark.asyncio
async def test_register_scene_from_config(scheduler, scene_config_manager):
    scene1 = Scene(scene_id="chat", priority=8, max_qpm=20, max_tpm=2000)
    scene2 = Scene(scene_id="code", priority=5, max_qpm=10, max_tpm=1000)
    
    scene_config_manager.add_or_update_scene(scene1)
    scene_config_manager.add_or_update_scene(scene2)
    
    assert len(scheduler.scenes) == 0
    
    scheduler.register_scene_from_config()
    
    assert "chat" in scheduler.scenes
    assert "code" in scheduler.scenes
    assert scheduler.scenes["chat"] == scene1
    assert scheduler.scenes["code"] == scene2


@pytest.mark.asyncio
async def test_sufficient_resources_request_processing(scheduler):
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    request = Request(scene_id="test_scene", prompt="test prompt", max_output_token=100)
    req_id = await scheduler.submit_request(request)
    
    await asyncio.sleep(0.5)
    
    assert scheduler.get_request_status(req_id) == RequestStatus.COMPLETED
    result = scheduler.get_request_result(req_id)
    assert result is not None
    assert result["status"] == "completed"
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scene_resource_limits(scheduler):
    scene = Scene(scene_id="restricted_scene", priority=5, max_qpm=0, max_tpm=0)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    request = Request(scene_id="restricted_scene", prompt="test prompt", max_output_token=100)
    req_id = await scheduler.submit_request(request)
    
    await asyncio.sleep(0.5)
    
    assert scheduler.get_request_status(req_id) == RequestStatus.PENDING
    assert len(scheduler.request_queue) == 1
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scene_tpm_limit(scheduler, resource_monitor):
    scene = Scene(scene_id="tpm_limited", priority=5, max_qpm=10, max_tpm=50)
    scheduler.register_scene(scene)
    
    for _ in range(4):
        req = Request(scene_id="tpm_limited", prompt="test", max_output_token=10)
        resource_monitor.record_request(req)
    
    request = Request(scene_id="tpm_limited", prompt="test", max_output_token=20)
    token_consumption = 30
    
    has_resources = scheduler._has_available_resources("tpm_limited", token_consumption)
    assert has_resources is False


@pytest.mark.asyncio
async def test_scene_qpm_limit(scheduler, resource_monitor):
    scene = Scene(scene_id="qpm_limited", priority=5, max_qpm=5, max_tpm=10000)
    scheduler.register_scene(scene)
    
    for _ in range(5):
        req = Request(scene_id="qpm_limited", prompt="test", max_output_token=10)
        resource_monitor.record_request(req)
    
    request = Request(scene_id="qpm_limited", prompt="test", max_output_token=10)
    token_consumption = 20
    
    has_resources = scheduler._has_available_resources("qpm_limited", token_consumption)
    assert has_resources is False


@pytest.mark.asyncio
async def test_queue_processing_multiple_requests(scheduler):
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=100, max_tpm=100000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    request_ids = []
    for i in range(3):
        req = Request(scene_id="test_scene", prompt=f"test {i}", max_output_token=10)
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
    
    await asyncio.sleep(1)
    
    for req_id in request_ids:
        assert scheduler.get_request_status(req_id) == RequestStatus.COMPLETED
        assert scheduler.get_request_result(req_id) is not None
    
    assert len(scheduler.request_queue) == 0
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_mixed_scene_queue_processing(scheduler):
    scene_high = Scene(scene_id="high_priority", priority=10, max_qpm=10, max_tpm=1000)
    scene_low = Scene(scene_id="low_priority", priority=1, max_qpm=0, max_tpm=0)
    scheduler.register_scene(scene_high)
    scheduler.register_scene(scene_low)
    
    await scheduler.start()
    
    req_low = Request(scene_id="low_priority", prompt="blocked", max_output_token=10)
    req_high = Request(scene_id="high_priority", prompt="normal", max_output_token=10)
    
    req_low_id = await scheduler.submit_request(req_low)
    req_high_id = await scheduler.submit_request(req_high)
    
    await asyncio.sleep(0.5)
    
    assert scheduler.get_request_status(req_high_id) == RequestStatus.COMPLETED
    assert scheduler.get_request_status(req_low_id) == RequestStatus.PENDING
    
    assert len(scheduler.request_queue) == 1
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_default_scene_config_manager(resource_monitor, mock_llm_pool):
    scheduler = Scheduler(
        resource_monitor,
        mock_llm_pool,
        total_qpm_limit=100,
        total_tpm_limit=100000
    )
    
    assert scheduler.scene_config_manager is not None
    assert isinstance(scheduler.scene_config_manager, SceneConfigManager)
    assert len(scheduler.scene_config_manager.get_all_scenes()) == 0


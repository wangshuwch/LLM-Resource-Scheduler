
import pytest
import asyncio
from src.scheduler.models import Scene, Request, RequestStatus
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool
from src.scheduler.scheduler import Scheduler


@pytest.fixture
def resource_monitor():
    return ResourceMonitor()


@pytest.fixture
def mock_llm_pool(resource_monitor):
    return MockLLMPool(resource_monitor, min_delay_ms=10, max_delay_ms=50)


@pytest.fixture
def scheduler(resource_monitor, mock_llm_pool):
    return Scheduler(resource_monitor, mock_llm_pool, total_qpm_limit=100, total_tpm_limit=100000)


@pytest.mark.asyncio
async def test_scheduler_initialization(scheduler):
    assert scheduler is not None
    assert scheduler.total_qpm_limit == 100
    assert scheduler.total_tpm_limit == 100000
    assert len(scheduler.scenes) == 0
    assert len(scheduler.request_queue) == 0


@pytest.mark.asyncio
async def test_register_scene(scheduler):
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    assert "test_scene" in scheduler.scenes
    assert scheduler.scenes["test_scene"] == scene


@pytest.mark.asyncio
async def test_submit_request_unknown_scene(scheduler):
    request = Request(scene_id="unknown_scene", prompt="test", max_output_token=10)
    with pytest.raises(ValueError, match="Scene not registered"):
        await scheduler.submit_request(request)


@pytest.mark.asyncio
async def test_submit_request_valid(scheduler):
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
    req_id = await scheduler.submit_request(request)
    
    assert req_id == request.request_id
    # 资源充足时，请求会直接处理
    assert scheduler.get_request_status(req_id) == RequestStatus.PROCESSING
    assert len(scheduler.request_queue) == 0
    assert req_id in scheduler.processing_requests


@pytest.mark.asyncio
async def test_request_priority_sorting(scheduler):
    # 创建两个场景，设置较低的QPM限制
    scene_high = Scene(scene_id="high_priority", priority=10, max_qpm=0, max_tpm=1000)  # QPM为0，强制进入队列
    scene_low = Scene(scene_id="low_priority", priority=1, max_qpm=0, max_tpm=1000)    # QPM为0，强制进入队列
    scheduler.register_scene(scene_high)
    scheduler.register_scene(scene_low)
    
    req_low = Request(scene_id="low_priority", prompt="low", max_output_token=10)
    req_high = Request(scene_id="high_priority", prompt="high", max_output_token=10)
    
    await scheduler.submit_request(req_low)
    await scheduler.submit_request(req_high)
    
    assert len(scheduler.request_queue) == 2
    # 按优先级排序，高优先级在前
    neg_priority, _, _, request = scheduler.request_queue[0]
    assert neg_priority == -10  # 负数优先级，值越小优先级越高
    assert request.request_id == req_high.request_id


@pytest.mark.asyncio
async def test_process_single_request(scheduler, resource_monitor, mock_llm_pool):
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    request = Request(scene_id="test_scene", prompt="test prompt", max_output_token=100)
    req_id = await scheduler.submit_request(request)
    
    await asyncio.sleep(1)
    
    assert scheduler.get_request_status(req_id) == RequestStatus.COMPLETED
    result = scheduler.get_request_result(req_id)
    assert result is not None
    assert result["status"] == "completed"
    assert result["request_id"] == req_id
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_multiple_requests(scheduler):
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=100, max_tpm=100000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    request_ids = []
    for i in range(5):
        req = Request(scene_id="test_scene", prompt=f"test {i}", max_output_token=10)
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
    
    await asyncio.sleep(1)
    
    for req_id in request_ids:
        assert scheduler.get_request_status(req_id) == RequestStatus.COMPLETED
        assert scheduler.get_request_result(req_id) is not None
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_head_of_line_blocking_fix(scheduler):
    scene_restricted = Scene(scene_id="restricted", priority=10, max_qpm=0, max_tpm=0)
    scene_normal = Scene(scene_id="normal", priority=5, max_qpm=100, max_tpm=100000)
    scheduler.register_scene(scene_restricted)
    scheduler.register_scene(scene_normal)
    
    await scheduler.start()
    
    req_restricted = Request(scene_id="restricted", prompt="blocked", max_output_token=10)
    req_normal = Request(scene_id="normal", prompt="normal", max_output_token=10)
    
    req_restricted_id = await scheduler.submit_request(req_restricted)
    req_normal_id = await scheduler.submit_request(req_normal)
    
    await asyncio.sleep(1)
    
    assert scheduler.get_request_status(req_normal_id) == RequestStatus.COMPLETED
    assert scheduler.get_request_status(req_restricted_id) == RequestStatus.PENDING
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_system_status(scheduler):
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    status = scheduler.get_system_status()
    
    assert status["total_qpm_limit"] == 100
    assert status["total_tpm_limit"] == 100000
    assert status["queue_length"] == 0
    assert status["processing_count"] == 0
    assert "test_scene" in status["scenes"]
    assert status["scenes"]["test_scene"]["priority"] == 5


@pytest.mark.asyncio
async def test_resource_sufficient_direct_processing(scheduler):
    """测试资源充足场景下请求直接处理，不排队"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    # 确保资源充足
    assert scheduler._is_resource_sufficient()
    
    request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
    req_id = await scheduler.submit_request(request)
    
    # 资源充足时，请求应该直接处理，不进入队列
    assert scheduler.get_request_status(req_id) == RequestStatus.PROCESSING
    assert len(scheduler.request_queue) == 0
    assert req_id in scheduler.processing_requests


@pytest.mark.asyncio
async def test_has_available_resources(scheduler):
    """测试资源充足性检查"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
    
    # 资源充足时应返回True
    assert scheduler._has_available_resources("test_scene", 20)
    
    # 模拟场景QPM达到上限
    for _ in range(10):
        scheduler.monitor.record_request(request)
    
    # 场景QPM达到上限时应返回False
    assert not scheduler._has_available_resources("test_scene", 20)

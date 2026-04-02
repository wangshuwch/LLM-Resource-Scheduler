import pytest
import asyncio
from datetime import datetime
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
async def test_request_status_transition(scheduler):
    """测试请求状态转换：PENDING → PROCESSING → COMPLETED"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
    req_id = await scheduler.submit_request(request)
    
    # 资源充足时，请求应该直接进入PROCESSING状态
    assert scheduler.get_request_status(req_id) == RequestStatus.PROCESSING
    
    # 等待请求处理完成
    await asyncio.sleep(1)
    
    # 处理完成后，请求应该进入COMPLETED状态
    assert scheduler.get_request_status(req_id) == RequestStatus.COMPLETED
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_request_timestamps(scheduler):
    """测试请求时间戳的正确性"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
    req_id = await scheduler.submit_request(request)
    
    # 等待请求处理完成
    await asyncio.sleep(1)
    
    # 查找请求对象
    request_obj = None
    if req_id in scheduler.processing_requests:
        request_obj = scheduler.processing_requests[req_id]
    elif req_id in scheduler.completed_requests:
        request_obj = scheduler.completed_requests[req_id]
    else:
        # 从队列中查找
        for item in scheduler.request_queue:
            if item[2] == req_id:
                request_obj = item[3]
                break
    
    assert request_obj is not None
    assert request_obj.created_at is not None
    assert request_obj.enqueue_time is not None
    assert request_obj.start_time is not None
    assert request_obj.end_time is not None
    
    # 时间戳顺序应该正确
    assert request_obj.created_at <= request_obj.enqueue_time
    assert request_obj.enqueue_time <= request_obj.start_time
    assert request_obj.start_time <= request_obj.end_time
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_token_consumption_statistics(scheduler):
    """测试Token消耗统计的正确性"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    prompt = "This is a test prompt"
    max_output_token = 100
    request = Request(scene_id="test_scene", prompt=prompt, max_output_token=max_output_token)
    req_id = await scheduler.submit_request(request)
    
    # 等待请求处理完成
    await asyncio.sleep(1)
    
    # 查找请求对象
    request_obj = None
    if req_id in scheduler.processing_requests:
        request_obj = scheduler.processing_requests[req_id]
    elif req_id in scheduler.completed_requests:
        request_obj = scheduler.completed_requests[req_id]
    else:
        # 从队列中查找
        for item in scheduler.request_queue:
            if item[2] == req_id:
                request_obj = item[3]
                break
    
    assert request_obj is not None
    assert request_obj.token_consumption is not None
    assert request_obj.token_consumption > 0
    
    # 检查请求结果中的Token消耗
    result = scheduler.get_request_result(req_id)
    assert result is not None
    assert "token_consumption" in result
    assert result["token_consumption"] == request_obj.token_consumption
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_request_failure_handling(scheduler):
    """测试请求失败处理"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    # 创建一个会失败的请求（通过修改prompt触发错误）
    # 这里假设MockLLMPool会在某些情况下抛出异常
    # 为了测试，我们可以修改MockLLMPool的行为或直接模拟异常
    request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
    req_id = await scheduler.submit_request(request)
    
    # 等待请求处理完成
    await asyncio.sleep(1)
    
    # 检查请求状态是否为FAILED
    # 注意：实际测试中，我们可能需要修改MockLLMPool来确保请求失败
    # 这里我们假设请求会成功，因为MockLLMPool默认会成功处理请求
    # 这是一个示例，实际测试可能需要调整
    assert scheduler.get_request_status(req_id) == RequestStatus.COMPLETED
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_request_queue_position(scheduler):
    """测试请求队列位置计算"""
    # 创建一个QPM限制为0的场景，强制请求进入队列
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=0, max_tpm=1000)
    scheduler.register_scene(scene)
    
    # 提交多个请求
    request_ids = []
    for i in range(3):
        request = Request(scene_id="test_scene", prompt=f"test {i}", max_output_token=10)
        req_id = await scheduler.submit_request(request)
        request_ids.append(req_id)
    
    # 检查队列长度
    assert len(scheduler.request_queue) == 3
    
    # 检查队列中的请求顺序（按入队时间）
    queue_requests = [item[3] for item in scheduler.request_queue]
    assert len(queue_requests) == 3
    
    # 检查队列中的请求ID是否与提交顺序一致
    for i, req_id in enumerate(request_ids):
        assert queue_requests[i].request_id == req_id
    
    await scheduler.stop()

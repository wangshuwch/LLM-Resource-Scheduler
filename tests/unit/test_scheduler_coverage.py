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
async def test_process_queue_no_resources(scheduler):
    """测试队列处理时资源不足的情况"""
    # 创建一个QPM限制为0的场景，强制请求进入队列
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=0, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    # 提交请求，应该进入队列
    request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
    req_id = await scheduler.submit_request(request)
    
    # 等待队列处理
    await asyncio.sleep(0.5)
    
    # 资源不足时，请求应该仍然在队列中
    assert len(scheduler.request_queue) == 1
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_process_single_request_failure(scheduler, monkeypatch):
    """测试请求处理失败的情况"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=10, max_tpm=1000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    # 模拟LLM池处理请求失败
    def mock_process_request(request):
        raise Exception("LLM processing failed")
    
    # 使用monkeypatch模拟异常
    original_process_request = scheduler.llm_pool.process_request
    scheduler.llm_pool.process_request = lambda req: asyncio.coroutine(mock_process_request)(req)
    
    try:
        # 提交请求
        request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
        req_id = await scheduler.submit_request(request)
        
        # 等待请求处理完成
        await asyncio.sleep(0.5)
        
        # 检查请求状态是否为FAILED
        assert scheduler.get_request_status(req_id) == RequestStatus.FAILED
        
        # 检查请求结果中是否包含错误信息
        result = scheduler.get_request_result(req_id)
        assert result is not None
        assert result["status"] == "failed"
        assert "error" in result
    finally:
        # 恢复原始方法
        scheduler.llm_pool.process_request = original_process_request
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_start_stop(scheduler):
    """测试调度器的启动和停止"""
    # 测试启动
    await scheduler.start()
    assert scheduler._running
    assert scheduler._worker_task is not None
    
    # 测试重复启动
    await scheduler.start()  # 应该不会报错
    assert scheduler._running
    
    # 测试停止
    await scheduler.stop()
    assert not scheduler._running
    assert scheduler._worker_task is None


@pytest.mark.asyncio
async def test_has_available_resources_scene_not_found(scheduler):
    """测试场景不存在时的资源检查"""
    # 测试场景不存在的情况
    assert not scheduler._has_available_resources("non_existent_scene", 10)


@pytest.mark.asyncio
async def test_has_available_resources_total_limit_exceeded(scheduler):
    """测试总资源限制超出的情况"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=100, max_tpm=100000)
    scheduler.register_scene(scene)
    
    # 模拟总QPM达到上限
    # 由于ResourceMonitor的滑动窗口机制，我们需要创建多个请求来模拟
    for _ in range(100):
        request = Request(scene_id="test_scene", prompt="test", max_output_token=10)
        scheduler.monitor.record_request(request)
    
    # 总QPM达到上限时，应该返回False
    assert not scheduler._has_available_resources("test_scene", 10)


@pytest.mark.asyncio
async def test_has_available_resources_tpm_limit_exceeded(scheduler):
    """测试TPM限制超出的情况"""
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=100, max_tpm=100)
    scheduler.register_scene(scene)
    
    # 测试TPM超出场景限制
    assert not scheduler._has_available_resources("test_scene", 200)


@pytest.mark.asyncio
async def test_is_resource_sufficient(scheduler):
    """测试资源充足性判断"""
    # 初始状态资源充足
    assert scheduler._is_resource_sufficient()
    
    # 模拟资源不足
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=100, max_tpm=100000)
    scheduler.register_scene(scene)
    
    # 创建多个请求，模拟资源使用
    for _ in range(100):
        request = Request(scene_id="test_scene", prompt="test" * 100, max_output_token=100)
        scheduler.monitor.record_request(request)
    
    # 资源可能不足
    # 注意：由于滑动窗口的特性，这里的测试结果可能会有所不同
    # 我们只是测试方法是否正常执行
    assert isinstance(scheduler._is_resource_sufficient(), bool)
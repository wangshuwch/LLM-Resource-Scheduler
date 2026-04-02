import pytest
import asyncio
from src.scheduler.models import Request, Scene, calculate_token_consumption, RequestStatus
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
    # 创建调度器实例，设置较高的资源限制以模拟资源充足场景
    scheduler_instance = Scheduler(
        monitor=resource_monitor,
        llm_pool=mock_llm_pool,
        total_qpm_limit=1000,
        total_tpm_limit=1000000,
        scene_config_manager=scene_config_manager
    )
    
    # 注册测试场景
    scene1 = Scene(scene_id="high_priority", priority=10, max_qpm=100, max_tpm=100000)
    scene2 = Scene(scene_id="medium_priority", priority=5, max_qpm=50, max_tpm=50000)
    scene3 = Scene(scene_id="low_priority", priority=1, max_qpm=20, max_tpm=20000)
    
    scene_config_manager.add_or_update_scene(scene1)
    scene_config_manager.add_or_update_scene(scene2)
    scene_config_manager.add_or_update_scene(scene3)
    
    # 从配置中注册场景
    scheduler_instance.register_scene_from_config()
    
    # 启动调度器
    asyncio.run(scheduler_instance.start())
    
    yield scheduler_instance
    
    # 停止调度器
    asyncio.run(scheduler_instance.stop())


@pytest.mark.asyncio
async def test_complete_request_flow(scheduler, resource_monitor):
    """测试完整的请求流程：提交 → 处理 → 完成"""
    request = Request(
        scene_id="high_priority",
        prompt="Test prompt for integration testing",
        max_output_token=200
    )
    
    # 提交请求
    request_id = await scheduler.submit_request(request)
    
    # 等待请求处理完成
    await asyncio.sleep(0.5)  # 等待足够的时间让请求处理完成
    
    # 检查请求状态
    status = scheduler.get_request_status(request_id)
    assert status == RequestStatus.COMPLETED
    
    # 检查请求结果
    result = scheduler.get_request_result(request_id)
    assert result is not None
    assert result["request_id"] == request_id
    assert result["scene_id"] == "high_priority"
    assert result["status"] == "completed"
    assert "token_consumption" in result
    assert result["token_consumption"] == calculate_token_consumption(request)
    
    # 检查资源监控
    total_load = resource_monitor.get_total_load()
    assert total_load.qpm >= 1
    assert total_load.tpm >= result["token_consumption"]
    
    scene_load = resource_monitor.get_scene_load("high_priority")
    assert scene_load.qpm >= 1
    assert scene_load.tpm >= result["token_consumption"]


@pytest.mark.asyncio
async def test_resource_sufficient_scene(scheduler, resource_monitor):
    """测试资源充足场景下的请求处理"""
    # 提交多个请求，确保资源充足
    requests = []
    for i in range(10):
        req = Request(
            scene_id="high_priority",
            prompt=f"Resource sufficient test {i}",
            max_output_token=100
        )
        requests.append(req)
    
    # 提交所有请求
    request_ids = []
    for req in requests:
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
    
    # 等待所有请求处理完成
    await asyncio.sleep(1.0)
    
    # 检查所有请求状态
    for req_id in request_ids:
        status = scheduler.get_request_status(req_id)
        assert status == RequestStatus.COMPLETED
    
    # 检查资源使用
    total_load = resource_monitor.get_total_load()
    assert total_load.qpm == 10
    
    scene_load = resource_monitor.get_scene_load("high_priority")
    assert scene_load.qpm == 10


@pytest.mark.asyncio
async def test_scene_config_management(scene_config_manager):
    """测试场景配置管理功能"""
    # 测试添加场景
    scene = Scene(scene_id="test_scene", priority=7, max_qpm=30, max_tpm=30000)
    result = scene_config_manager.add_or_update_scene(scene)
    assert result is True
    
    # 测试获取场景
    retrieved_scene = scene_config_manager.get_scene("test_scene")
    assert retrieved_scene is not None
    assert retrieved_scene.scene_id == "test_scene"
    assert retrieved_scene.priority == 7
    assert retrieved_scene.max_qpm == 30
    assert retrieved_scene.max_tpm == 30000
    
    # 测试更新场景
    updated_scene = Scene(scene_id="test_scene", priority=8, max_qpm=40, max_tpm=40000)
    result = scene_config_manager.add_or_update_scene(updated_scene)
    assert result is True
    
    retrieved_updated_scene = scene_config_manager.get_scene("test_scene")
    assert retrieved_updated_scene.priority == 8
    assert retrieved_updated_scene.max_qpm == 40
    assert retrieved_updated_scene.max_tpm == 40000
    
    # 测试获取所有场景
    all_scenes = scene_config_manager.get_all_scenes()
    assert "test_scene" in all_scenes
    
    # 测试删除场景
    result = scene_config_manager.delete_scene("test_scene")
    assert result is True
    
    retrieved_deleted_scene = scene_config_manager.get_scene("test_scene")
    assert retrieved_deleted_scene is None


@pytest.mark.asyncio
async def test_priority_based_processing(scheduler):
    """测试基于优先级的请求处理"""
    # 创建不同优先级的请求
    high_priority_request = Request(
        scene_id="high_priority",
        prompt="High priority request",
        max_output_token=100
    )
    
    medium_priority_request = Request(
        scene_id="medium_priority",
        prompt="Medium priority request",
        max_output_token=100
    )
    
    low_priority_request = Request(
        scene_id="low_priority",
        prompt="Low priority request",
        max_output_token=100
    )
    
    # 按低到高的顺序提交请求
    low_req_id = await scheduler.submit_request(low_priority_request)
    medium_req_id = await scheduler.submit_request(medium_priority_request)
    high_req_id = await scheduler.submit_request(high_priority_request)
    
    # 等待所有请求处理完成
    await asyncio.sleep(1.0)
    
    # 检查所有请求都已完成
    assert scheduler.get_request_status(low_req_id) == RequestStatus.COMPLETED
    assert scheduler.get_request_status(medium_req_id) == RequestStatus.COMPLETED
    assert scheduler.get_request_status(high_req_id) == RequestStatus.COMPLETED


@pytest.mark.asyncio
async def test_system_status_report(scheduler):
    """测试系统状态报告功能"""
    # 提交一些请求
    for i in range(5):
        req = Request(
            scene_id="high_priority",
            prompt=f"Status test {i}",
            max_output_token=100
        )
        await scheduler.submit_request(req)
    
    await asyncio.sleep(0.5)
    
    # 获取系统状态
    status = scheduler.get_system_status()
    
    assert "total_qpm_limit" in status
    assert "total_tpm_limit" in status
    assert "current_total_qpm" in status
    assert "current_total_tpm" in status
    assert "queue_length" in status
    assert "processing_count" in status
    assert "scenes" in status
    
    # 检查场景状态
    scenes = status["scenes"]
    assert "high_priority" in scenes
    assert "medium_priority" in scenes
    assert "low_priority" in scenes


@pytest.mark.asyncio
async def test_concurrent_requests(scheduler, resource_monitor):
    """测试并发请求处理"""
    requests = []
    for i in range(20):
        # 交替使用不同优先级的场景
        scene_id = "high_priority" if i % 2 == 0 else "medium_priority"
        req = Request(
            scene_id=scene_id,
            prompt=f"Concurrent request {i}",
            max_output_token=50
        )
        requests.append(req)
    
    # 并发提交所有请求
    tasks = [scheduler.submit_request(req) for req in requests]
    request_ids = await asyncio.gather(*tasks)
    
    # 等待所有请求处理完成
    await asyncio.sleep(1.5)
    
    # 检查所有请求状态
    for req_id in request_ids:
        status = scheduler.get_request_status(req_id)
        assert status == RequestStatus.COMPLETED
    
    # 检查资源使用
    total_load = resource_monitor.get_total_load()
    assert total_load.qpm == 20
    
    high_priority_load = resource_monitor.get_scene_load("high_priority")
    medium_priority_load = resource_monitor.get_scene_load("medium_priority")
    assert high_priority_load.qpm == 10
    assert medium_priority_load.qpm == 10


@pytest.mark.asyncio
async def test_invalid_scene_handling(scheduler):
    """测试无效场景的处理"""
    # 创建一个未注册的场景请求
    invalid_request = Request(
        scene_id="non_existent_scene",
        prompt="Invalid scene request",
        max_output_token=100
    )
    
    # 提交请求应该抛出异常
    with pytest.raises(ValueError, match="Scene not registered"):
        await scheduler.submit_request(invalid_request)

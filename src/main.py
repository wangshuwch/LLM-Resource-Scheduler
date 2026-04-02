"""LLM资源调度器API主模块。

本模块是FastAPI应用的主入口，提供RESTful API接口用于：
    - 请求提交和状态查询
    - 场景配置管理
    - 系统状态监控
    - 队列状态查询

API端点:
    - POST /api/v1/requests: 提交请求
    - GET /api/v1/requests/{request_id}: 查询请求状态
    - GET /api/v1/requests/{request_id}/result: 获取请求结果
    - PUT /api/v1/scenes/{scene_id}: 创建或更新场景
    - GET /api/v1/scenes/{scene_id}: 获取场景配置
    - GET /api/v1/scenes: 获取所有场景配置
    - GET /api/v1/system/status: 获取系统状态
    - GET /api/v1/queue: 获取队列状态
"""

from fastapi import FastAPI, HTTPException
import uvicorn
import asyncio
from typing import Dict, Any

from config.settings import settings
from src.api.schemas import (
    SubmitRequest, SubmitResponse, RequestStatusResponse, RequestResultResponse,
    SceneConfigRequest, SceneConfigResponse, SceneConfigListResponse, SuccessResponse,
    SystemStatusResponse, QueueStatusResponse, QueueRequestItem
)
from src.scheduler.models import Request as SchedulerRequest
from src.scheduler.scheduler import Scheduler
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool
from src.scheduler.config import SceneConfigManager


app = FastAPI(title=settings.app_name, debug=settings.debug)

resource_monitor = ResourceMonitor()
llm_pool = MockLLMPool(resource_monitor)
scene_config_manager = SceneConfigManager()
scheduler = Scheduler(
    resource_monitor,
    llm_pool,
    total_qpm_limit=1000,
    total_tpm_limit=1000000,
    scene_config_manager=scene_config_manager
)

def init_default_scenes() -> None:
    """初始化默认场景配置。

    创建并注册三个默认场景：
        - default: 中等优先级场景
        - high_priority: 高优先级场景
        - low_priority: 低优先级场景
    """
    from src.scheduler.models import Scene
    default_scenes = [
        Scene(scene_id="default", priority=5, max_qpm=100, max_tpm=100000),
        Scene(scene_id="high_priority", priority=10, max_qpm=200, max_tpm=200000),
        Scene(scene_id="low_priority", priority=1, max_qpm=50, max_tpm=50000)
    ]
    for scene in default_scenes:
        scheduler.register_scene(scene)

@app.on_event("startup")
async def startup_event() -> None:
    """应用启动事件处理函数。

    初始化默认场景并启动调度器。
    """
    init_default_scenes()
    await scheduler.start()

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """应用关闭事件处理函数。

    停止调度器，等待所有正在处理的请求完成。
    """
    await scheduler.stop()


@app.get("/")
async def root() -> Dict[str, str]:
    """健康检查端点。

    Returns:
        包含应用名称和健康状态的字典。
    """
    return {
        "app_name": settings.app_name,
        "status": "healthy"
    }


@app.post("/api/v1/requests", response_model=SubmitResponse)
async def submit_request(req: SubmitRequest) -> SubmitResponse:
    """提交LLM请求。

    将请求提交到调度器，根据资源可用性可能立即处理或排队等待。

    Args:
        req: 请求提交模型，包含场景ID、提示词和最大输出Token数。

    Returns:
        提交响应，包含请求ID、状态、队列位置和预估等待时间。

    Raises:
        HTTPException: 当场景未注册时返回400，服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        scheduler_request = SchedulerRequest(
            scene_id=req.scene_id,
            prompt=req.prompt,
            max_output_token=req.max_output_token
        )
        
        request_id = await scheduler.submit_request(scheduler_request)
        
        queue_position = None
        estimated_wait_time_ms = None
        status = scheduler.get_request_status(request_id)
        if status is not None and status.value == "pending":
            queue = [item[3] for item in scheduler.request_queue]
            try:
                queue_position = queue.index(scheduler_request) + 1
            except ValueError:
                queue_position = 0
            
            estimated_wait_time_ms = scheduler.estimate_wait_time(request_id)
        
        return SubmitResponse(
            request_id=request_id,
            status=status.value if status else "unknown",
            queue_position=queue_position or 0,
            estimated_wait_time_ms=estimated_wait_time_ms
        )
    except ValueError as e:
        logger.exception(f"Invalid request parameter: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid request parameter: {str(e)}")
    except KeyError as e:
        logger.exception(f"Missing required field: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Missing required field: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error in request: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid request format: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error submitting request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/v1/requests/{request_id}", response_model=RequestStatusResponse)
async def get_request_status(request_id: str) -> RequestStatusResponse:
    """查询请求状态。

    获取指定请求的当前状态和相关信息。

    Args:
        request_id: 请求ID。

    Returns:
        请求状态响应，包含请求ID、场景ID、状态、队列位置和时间信息。

    Raises:
        HTTPException: 当请求不存在时返回404，服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        status = scheduler.get_request_status(request_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Request not found")
        
        request = None
        if request_id in scheduler.processing_requests:
            request = scheduler.processing_requests[request_id]
        elif request_id in scheduler.completed_requests:
            request = scheduler.completed_requests[request_id]
        else:
            for item in scheduler.request_queue:
                if item[2] == request_id:
                    request = item[3]
                    break
        
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        queue_position = None
        if status.value == "pending":
            queue = [item[3] for item in scheduler.request_queue]
            try:
                queue_position = queue.index(request) + 1
            except ValueError:
                queue_position = 0
        
        return RequestStatusResponse(
            request_id=request_id,
            scene_id=request.scene_id,
            status=status.value,
            queue_position=queue_position,
            enqueue_time=request.enqueue_time,
            start_time=request.start_time,
            end_time=request.end_time,
            token_consumption=request.token_consumption
        )
    except HTTPException:
        raise
    except KeyError as e:
        logger.exception(f"Missing required data for request {request_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Request data incomplete: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error for request {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting request status for {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/v1/requests/{request_id}/result", response_model=RequestResultResponse)
async def get_request_result(request_id: str) -> RequestResultResponse:
    """获取请求处理结果。

    获取已完成请求的处理结果或错误信息。

    Args:
        request_id: 请求ID。

    Returns:
        请求结果响应，包含请求ID、场景ID、状态、Token消耗和处理结果或错误。

    Raises:
        HTTPException: 当请求不存在时返回404，服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        status = scheduler.get_request_status(request_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Request not found")
        
        request = None
        if request_id in scheduler.processing_requests:
            request = scheduler.processing_requests[request_id]
        elif request_id in scheduler.completed_requests:
            request = scheduler.completed_requests[request_id]
        else:
            for item in scheduler.request_queue:
                if item[2] == request_id:
                    request = item[3]
                    break
        
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        result = scheduler.get_request_result(request_id)
        
        return RequestResultResponse(
            request_id=request_id,
            scene_id=request.scene_id,
            status=status.value,
            token_consumption=request.token_consumption,
            result=result.get("result") if result and "result" in result else None,
            error=result.get("error") if result and "error" in result else None
        )
    except HTTPException:
        raise
    except KeyError as e:
        logger.exception(f"Missing required data for request result {request_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Request result data incomplete: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error for request result {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting request result for {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.put("/api/v1/scenes/{scene_id}", response_model=SuccessResponse)
async def create_or_update_scene(scene_id: str, req: SceneConfigRequest) -> SuccessResponse:
    """创建或更新场景配置。

    如果场景已存在则更新配置，否则创建新场景。

    Args:
        scene_id: 场景ID（路径参数）。
        req: 场景配置请求模型。

    Returns:
        成功响应，包含操作结果和场景配置信息。

    Raises:
        HTTPException: 当路径和请求体中的场景ID不匹配时返回400，
            配置无效时返回400，服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from src.scheduler.models import Scene
        
        if req.scene_id != scene_id:
            raise HTTPException(status_code=400, detail="Scene ID in path and request body must match")
        
        scene = Scene(
            scene_id=req.scene_id,
            priority=req.priority,
            max_qpm=req.max_qpm,
            max_tpm=req.max_tpm
        )
        
        if scheduler.scene_config_manager.add_or_update_scene(scene):
            scheduler.register_scene(scene)
            
            scene_load = resource_monitor.get_scene_load(scene_id)
            
            return SuccessResponse(
                success=True,
                scene=SceneConfigResponse(
                    scene_id=scene.scene_id,
                    priority=scene.priority,
                    max_qpm=scene.max_qpm,
                    max_tpm=scene.max_tpm,
                    current_qpm=scene_load.qpm,
                    current_tpm=scene_load.tpm
                )
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid scene configuration: validation failed")
    except HTTPException:
        raise
    except ValueError as e:
        logger.exception(f"Invalid scene configuration value: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid scene configuration value: {str(e)}")
    except KeyError as e:
        logger.exception(f"Missing required field in scene configuration: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Missing required field: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error in scene configuration: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid scene configuration format: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error creating or updating scene {scene_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/v1/scenes/{scene_id}", response_model=SceneConfigResponse)
async def get_scene_config(scene_id: str) -> SceneConfigResponse:
    """获取指定场景的配置。

    Args:
        scene_id: 场景ID。

    Returns:
        场景配置响应，包含场景配置和当前资源使用情况。

    Raises:
        HTTPException: 当场景不存在时返回404，服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        scene = scheduler.scene_config_manager.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        scene_load = resource_monitor.get_scene_load(scene_id)
        
        return SceneConfigResponse(
            scene_id=scene.scene_id,
            priority=scene.priority,
            max_qpm=scene.max_qpm,
            max_tpm=scene.max_tpm,
            current_qpm=scene_load.qpm,
            current_tpm=scene_load.tpm
        )
    except HTTPException:
        raise
    except KeyError as e:
        logger.exception(f"Missing required data for scene {scene_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Scene data incomplete: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error for scene {scene_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting scene config for {scene_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/v1/scenes", response_model=SceneConfigListResponse)
async def get_all_scene_configs() -> SceneConfigListResponse:
    """获取所有场景配置。

    Returns:
        场景配置列表响应，包含所有场景的配置和当前资源使用情况。

    Raises:
        HTTPException: 服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        scenes = scheduler.scene_config_manager.get_all_scenes()
        
        scene_responses = []
        for scene_id, scene in scenes.items():
            scene_load = resource_monitor.get_scene_load(scene_id)
            scene_responses.append(SceneConfigResponse(
                scene_id=scene.scene_id,
                priority=scene.priority,
                max_qpm=scene.max_qpm,
                max_tpm=scene.max_tpm,
                current_qpm=scene_load.qpm,
                current_tpm=scene_load.tpm
            ))
        
        return SceneConfigListResponse(scenes=scene_responses)
    except KeyError as e:
        logger.exception(f"Missing required data in scene configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scene configuration data incomplete: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error in scene configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting all scene configs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/v1/system/status", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """获取系统整体状态。

    Returns:
        系统状态响应，包含全局资源使用情况、队列长度和各场景状态。

    Raises:
        HTTPException: 服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        status = scheduler.get_system_status()
        return SystemStatusResponse(**status)
    except KeyError as e:
        logger.exception(f"Missing required data in system status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"System status data incomplete: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error in system status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting system status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/v1/queue", response_model=QueueStatusResponse)
async def get_queue_status() -> QueueStatusResponse:
    """获取请求队列状态。

    Returns:
        队列状态响应，包含队列长度和所有排队请求的详细信息。

    Raises:
        HTTPException: 服务器错误时返回500。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        queue_items = []
        for item in scheduler.request_queue:
            neg_priority, enqueue_time, req_id, request = item
            priority = -neg_priority
            from datetime import datetime
            enqueue_datetime = datetime.fromtimestamp(enqueue_time)
            
            queue_items.append(QueueRequestItem(
                request_id=req_id,
                scene_id=request.scene_id,
                priority=priority,
                enqueue_time=enqueue_datetime,
                estimated_token_consumption=request.token_consumption or 0
            ))
        
        return QueueStatusResponse(
            length=len(scheduler.request_queue),
            requests=queue_items
        )
    except KeyError as e:
        logger.exception(f"Missing required data in queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Queue status data incomplete: {str(e)}")
    except (AttributeError, TypeError) as e:
        logger.exception(f"Type or attribute error in queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )

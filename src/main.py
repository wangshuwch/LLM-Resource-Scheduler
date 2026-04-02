from fastapi import FastAPI, HTTPException
import uvicorn
import asyncio

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

# 初始化组件
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

# 注册默认场景
def init_default_scenes():
    from src.scheduler.models import Scene
    default_scenes = [
        Scene(scene_id="default", priority=5, max_qpm=100, max_tpm=100000),
        Scene(scene_id="high_priority", priority=10, max_qpm=200, max_tpm=200000),
        Scene(scene_id="low_priority", priority=1, max_qpm=50, max_tpm=50000)
    ]
    for scene in default_scenes:
        scheduler.register_scene(scene)

# 启动调度器
@app.on_event("startup")
async def startup_event():
    init_default_scenes()
    await scheduler.start()

# 关闭调度器
@app.on_event("shutdown")
async def shutdown_event():
    await scheduler.stop()


@app.get("/")
async def root():
    return {
        "app_name": settings.app_name,
        "status": "healthy"
    }


@app.post("/api/v1/requests", response_model=SubmitResponse)
async def submit_request(req: SubmitRequest):
    # 创建调度器请求对象
    try:
        scheduler_request = SchedulerRequest(
            scene_id=req.scene_id,
            prompt=req.prompt,
            max_output_token=req.max_output_token
        )
        
        # 提交请求
        request_id = await scheduler.submit_request(scheduler_request)
        
        # 获取队列位置
        queue_position = None
        status = scheduler.get_request_status(request_id)
        if status.value == "pending":
            # 计算队列位置
            queue = [item[3] for item in scheduler.request_queue]
            try:
                queue_position = queue.index(scheduler_request) + 1
            except ValueError:
                queue_position = 0
        
        return SubmitResponse(
            request_id=request_id,
            status=status.value,
            queue_position=queue_position or 0
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error submitting request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/requests/{request_id}", response_model=RequestStatusResponse)
async def get_request_status(request_id: str):
    try:
        # 获取请求状态
        status = scheduler.get_request_status(request_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # 查找请求对象
        request = None
        if request_id in scheduler.processing_requests:
            request = scheduler.processing_requests[request_id]
        elif request_id in scheduler.completed_requests:
            request = scheduler.completed_requests[request_id]
        else:
            # 从队列中查找
            for item in scheduler.request_queue:
                if item[2] == request_id:
                    request = item[3]
                    break
        
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # 计算队列位置
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
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error getting request status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/requests/{request_id}/result", response_model=RequestResultResponse)
async def get_request_result(request_id: str):
    try:
        # 获取请求状态
        status = scheduler.get_request_status(request_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # 查找请求对象
        request = None
        if request_id in scheduler.processing_requests:
            request = scheduler.processing_requests[request_id]
        elif request_id in scheduler.completed_requests:
            request = scheduler.completed_requests[request_id]
        else:
            # 从队列中查找
            for item in scheduler.request_queue:
                if item[2] == request_id:
                    request = item[3]
                    break
        
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # 获取请求结果
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
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error getting request result: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/api/v1/scenes/{scene_id}", response_model=SuccessResponse)
async def create_or_update_scene(scene_id: str, req: SceneConfigRequest):
    try:
        from src.scheduler.models import Scene
        
        # 确保scene_id一致
        if req.scene_id != scene_id:
            raise HTTPException(status_code=400, detail="Scene ID in path and request body must match")
        
        # 创建场景对象
        scene = Scene(
            scene_id=req.scene_id,
            priority=req.priority,
            max_qpm=req.max_qpm,
            max_tpm=req.max_tpm
        )
        
        # 添加或更新场景
        if scheduler.scene_config_manager.add_or_update_scene(scene):
            # 注册场景到调度器
            scheduler.register_scene(scene)
            
            # 获取当前负载
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
            raise HTTPException(status_code=400, detail="Invalid scene configuration")
    except HTTPException:
        raise
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error creating or updating scene: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/scenes/{scene_id}", response_model=SceneConfigResponse)
async def get_scene_config(scene_id: str):
    try:
        # 获取场景配置
        scene = scheduler.scene_config_manager.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # 获取当前负载
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
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error getting scene config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/scenes", response_model=SceneConfigListResponse)
async def get_all_scene_configs():
    try:
        # 获取所有场景配置
        scenes = scheduler.scene_config_manager.get_all_scenes()
        
        # 构建响应
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
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error getting all scene configs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    try:
        # 获取系统状态
        status = scheduler.get_system_status()
        return SystemStatusResponse(**status)
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error getting system status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/queue", response_model=QueueStatusResponse)
async def get_queue_status():
    try:
        # 构建队列状态响应
        queue_items = []
        for item in scheduler.request_queue:
            neg_priority, enqueue_time, req_id, request = item
            # 计算实际优先级（取反）
            priority = -neg_priority
            # 转换时间戳为datetime
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
    except Exception as e:
        # 捕获其他未知错误
        import logging
        logging.error(f"Error getting queue status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )

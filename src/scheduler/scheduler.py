
import asyncio
import time
import heapq
import logging
from datetime import datetime

from .models import Scene, Request, calculate_token_consumption, RequestStatus
from .monitor import ResourceMonitor
from .llm_pool import MockLLMPool
from .config import SceneConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        monitor,
        llm_pool,
        total_qpm_limit=1000,
        total_tpm_limit=1000000,
        scene_config_manager=None,
        completed_requests_max_size=1000,
    ):
        self.monitor = monitor
        self.llm_pool = llm_pool
        self.total_qpm_limit = total_qpm_limit
        self.total_tpm_limit = total_tpm_limit
        
        self.scene_config_manager = scene_config_manager or SceneConfigManager()
        
        self.scenes = {}
        self.request_queue = []  # 优先队列
        self.processing_requests = {}
        self.completed_requests = {}
        self.request_status = {}
        self.request_results = {}
        
        self.completed_requests_max_size = completed_requests_max_size
        
        self._lock = asyncio.Lock()
        self._running = False
        self._worker_task = None
        self._cleanup_task = None

    def register_scene(self, scene):
        self.scenes[scene.scene_id] = scene

    def register_scene_from_config(self):
        scenes = self.scene_config_manager.get_all_scenes()
        for scene_id, scene in scenes.items():
            self.register_scene(scene)

    async def submit_request(self, request):
        async with self._lock:
            if request.scene_id not in self.scenes:
                logger.error(f"Submit request failed: Scene {request.scene_id} not registered")
                raise ValueError("Scene not registered")
            
            # 计算Token消耗并存储在请求对象中
            request.token_consumption = calculate_token_consumption(request)
            
            # 检查是否资源充足且该请求可以直接处理
            if self._has_available_resources(request.scene_id, request.token_consumption):
                # 资源充足，直接处理
                request.status = RequestStatus.PROCESSING
                request.start_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.PROCESSING
                self.processing_requests[request.request_id] = request
                
                asyncio.create_task(self._process_single_request(request))
                logger.info(f"Request {request.request_id} from scene {request.scene_id} submitted and immediately processing")
                return request.request_id
            else:
                # 资源不足，进入队列
                request.status = RequestStatus.PENDING
                request.enqueue_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.PENDING
                
                scene = self.scenes[request.scene_id]
                priority = scene.priority
                enqueue_time = time.time()
                
                # 使用优先队列，自动排序
                heapq.heappush(self.request_queue, (-priority, enqueue_time, request.request_id, request))
                
                logger.info(f"Request {request.request_id} from scene {request.scene_id} submitted and queued")
                return request.request_id

    def get_request_status(self, request_id):
        return self.request_status.get(request_id)

    def get_request_result(self, request_id):
        return self.request_results.get(request_id)

    def _has_available_resources(self, scene_id, token_consumption):
        total_load = self.monitor.get_total_load()
        scene_load = self.monitor.get_scene_load(scene_id)
        
        if scene_id not in self.scenes:
            return False
        
        scene = self.scenes[scene_id]
        
        # 检查总资源是否充足
        if total_load.qpm >= self.total_qpm_limit:
            return False
        if total_load.tpm + token_consumption > self.total_tpm_limit:
            return False
        
        # 检查场景资源是否充足（按最大限制）
        if scene_load.qpm >= scene.max_qpm:
            return False
        if scene_load.tpm + token_consumption > scene.max_tpm:
            return False
        
        return True
    
    def _is_resource_sufficient(self):
        """判断是否处于资源充足场景"""
        total_load = self.monitor.get_total_load()
        return total_load.qpm < self.total_qpm_limit and total_load.tpm < self.total_tpm_limit

    async def _process_queue(self):
        while self._running:
            async with self._lock:
                if not self.request_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                # 从优先队列中获取最高优先级的请求
                processed = False
                temp_queue = []
                
                while self.request_queue:
                    neg_priority, enqueue_time, req_id, request = heapq.heappop(self.request_queue)
                    token_consumption = calculate_token_consumption(request)
                    
                    # 检查资源是否充足，包括总资源和场景资源
                    if self._has_available_resources(request.scene_id, token_consumption):
                        request.status = RequestStatus.PROCESSING
                        request.start_time = datetime.now()
                        
                        self.request_status[request.request_id] = RequestStatus.PROCESSING
                        self.processing_requests[request.request_id] = request
                        
                        asyncio.create_task(self._process_single_request(request))
                        processed = True
                        break
                    else:
                        # 资源不足，放回临时队列
                        temp_queue.append((neg_priority, enqueue_time, req_id, request))
                
                # 将未处理的请求放回优先队列
                for item in temp_queue:
                    heapq.heappush(self.request_queue, item)
                
                if not processed:
                    await asyncio.sleep(0.1)

    async def _process_single_request(self, request):
        try:
            logger.info(f"Processing request {request.request_id} from scene {request.scene_id}")
            result = await self.llm_pool.process_request(request)
            async with self._lock:
                request.status = RequestStatus.COMPLETED
                request.end_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.COMPLETED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "completed",
                    "token_consumption": request.token_consumption,
                    "result": result
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
                # 将已完成的请求添加到completed_requests字典中
                self.completed_requests[request.request_id] = request
            logger.info(f"Request {request.request_id} completed successfully")
        except Exception as e:
            # 错误处理，MockLLMPool已经记录了资源使用
            logger.error(f"Request {request.request_id} failed: {str(e)}")
            async with self._lock:
                request.status = RequestStatus.FAILED
                request.end_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.FAILED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "failed",
                    "token_consumption": request.token_consumption,
                    "error": str(e)
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
                # 将失败的请求也添加到completed_requests字典中
                self.completed_requests[request.request_id] = request

    async def _cleanup_completed_requests(self):
        """定期清理已完成的请求，防止内存泄漏"""
        while self._running:
            await asyncio.sleep(60)  # 每分钟清理一次
            async with self._lock:
                if len(self.completed_requests) > self.completed_requests_max_size:
                    # 按完成时间排序，保留最新的请求
                    sorted_requests = sorted(
                        self.completed_requests.items(),
                        key=lambda x: x[1].end_time or x[1].created_at,
                        reverse=True
                    )
                    # 只保留最近的completed_requests_max_size个请求
                    to_keep = dict(sorted_requests[:self.completed_requests_max_size])
                    # 删除超出限制的请求
                    cleaned_count = 0
                    for req_id in list(self.completed_requests.keys()):
                        if req_id not in to_keep:
                            del self.completed_requests[req_id]
                            # 同时清理对应的状态和结果
                            if req_id in self.request_status:
                                del self.request_status[req_id]
                            if req_id in self.request_results:
                                del self.request_results[req_id]
                            cleaned_count += 1
                    logger.info(f"Cleaned up {cleaned_count} completed requests to prevent memory leak")

    async def start(self):
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        self._cleanup_task = asyncio.create_task(self._cleanup_completed_requests())
        logger.info("Scheduler started")

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._worker_task = None
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._cleanup_task = None
        logger.info("Scheduler stopped")

    def get_system_status(self):
        total_load = self.monitor.get_total_load()
        scenes_status = {}
        
        for scene_id, scene in self.scenes.items():
            scene_load = self.monitor.get_scene_load(scene_id)
            scenes_status[scene_id] = {
                "priority": scene.priority,
                "max_qpm": scene.max_qpm,
                "max_tpm": scene.max_tpm,
                "current_qpm": scene_load.qpm,
                "current_tpm": scene_load.tpm
            }
        
        return {
            "total_qpm_limit": self.total_qpm_limit,
            "total_tpm_limit": self.total_tpm_limit,
            "current_total_qpm": total_load.qpm,
            "current_total_tpm": total_load.tpm,
            "queue_length": len(self.request_queue),
            "processing_count": len(self.processing_requests),
            "scenes": scenes_status
        }


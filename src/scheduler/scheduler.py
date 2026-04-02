"""LLM资源调度器模块。

本模块实现了基于优先级的LLM请求调度系统，支持多场景资源管理和
QPM/TPM限制。调度器使用优先队列管理待处理请求，并根据资源可用性
动态分配处理资源。

主要功能:
    - 基于优先级的请求调度
    - 场景级别的QPM/TPM限制
    - 全局资源监控和管理
    - 异步请求处理
    - 自动清理已完成请求

典型使用场景:
    - 多租户LLM服务资源隔离
    - 不同业务场景的优先级管理
    - API调用频率控制
"""

import asyncio
import time
import heapq
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from .models import Scene, Request, calculate_token_consumption, RequestStatus
from .monitor import ResourceMonitor
from .llm_pool import MockLLMPool
from .config import SceneConfigManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Scheduler:
    """LLM请求调度器，管理请求的提交、排队和处理。

    该调度器实现了基于优先级的请求调度机制，支持多场景资源隔离
    和QPM/TPM限制。请求根据场景优先级排队，在资源可用时被处理。

    Attributes:
        monitor: 资源监控器，用于跟踪QPM/TPM使用情况。
        llm_pool: LLM处理池，用于实际处理请求。
        total_qpm_limit: 全局QPM限制。
        total_tpm_limit: 全局TPM限制。
        scene_config_manager: 场景配置管理器。
        scenes: 已注册的场景字典，键为场景ID。
        request_queue: 请求优先队列，存储待处理请求。
        processing_requests: 正在处理的请求字典。
        completed_requests: 已完成的请求字典。
        request_status: 请求状态字典。
        request_results: 请求结果字典。
        completed_requests_max_size: 已完成请求的最大保留数量。
        processing_times: 请求处理时间样本列表。

    Example:
        >>> from src.scheduler.monitor import ResourceMonitor
        >>> from src.scheduler.llm_pool import MockLLMPool
        >>> from src.scheduler.config import SceneConfigManager
        >>> from src.scheduler.models import Scene, Request
        >>>
        >>> monitor = ResourceMonitor()
        >>> llm_pool = MockLLMPool(monitor)
        >>> config_manager = SceneConfigManager()
        >>> scheduler = Scheduler(monitor, llm_pool, scene_config_manager=config_manager)
        >>>
        >>> scene = Scene(scene_id="test", priority=5, max_qpm=100, max_tpm=10000)
        >>> scheduler.register_scene(scene)
        >>>
        >>> request = Request(scene_id="test", prompt="Hello", max_output_token=100)
        >>> request_id = await scheduler.submit_request(request)
    """

    def __init__(
        self,
        monitor: ResourceMonitor,
        llm_pool: MockLLMPool,
        total_qpm_limit: int = 1000,
        total_tpm_limit: int = 1000000,
        scene_config_manager: Optional[SceneConfigManager] = None,
        completed_requests_max_size: int = 1000,
    ) -> None:
        """初始化调度器实例。

        Args:
            monitor: 资源监控器实例，用于跟踪资源使用情况。
            llm_pool: LLM处理池实例，用于处理请求。
            total_qpm_limit: 全局每分钟查询数限制，默认为1000。
            total_tpm_limit: 全局每分钟Token数限制，默认为1000000。
            scene_config_manager: 场景配置管理器实例，可选。
            completed_requests_max_size: 已完成请求的最大保留数量，
                用于防止内存泄漏，默认为1000。
        """
        self.monitor: ResourceMonitor = monitor
        self.llm_pool: MockLLMPool = llm_pool
        self.total_qpm_limit: int = total_qpm_limit
        self.total_tpm_limit: int = total_tpm_limit
        
        self.scene_config_manager: SceneConfigManager = scene_config_manager or SceneConfigManager()
        
        self.scenes: Dict[str, Scene] = {}
        self.request_queue: List[tuple[int, float, str, Request]] = []
        self.processing_requests: Dict[str, Request] = {}
        self.completed_requests: Dict[str, Request] = {}
        self.request_status: Dict[str, RequestStatus] = {}
        self.request_results: Dict[str, Dict[str, Any]] = {}
        
        self.completed_requests_max_size: int = completed_requests_max_size
        
        self._lock: asyncio.Lock = asyncio.Lock()
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        
        self.processing_times: List[float] = []
        self.max_processing_times_samples: int = 100

    def register_scene(self, scene: Scene) -> None:
        """注册一个场景到调度器。

        Args:
            scene: 要注册的场景对象，包含场景ID、优先级和资源限制。

        Example:
            >>> scene = Scene(scene_id="chat", priority=8, max_qpm=200, max_tpm=50000)
            >>> scheduler.register_scene(scene)
        """
        self.scenes[scene.scene_id] = scene

    def register_scene_from_config(self) -> None:
        """从配置管理器加载并注册所有场景。

        该方法从scene_config_manager获取所有场景配置并注册到调度器。
        通常在调度器启动前调用。

        Example:
            >>> scheduler.register_scene_from_config()
        """
        scenes = self.scene_config_manager.get_all_scenes()
        for scene_id, scene in scenes.items():
            self.register_scene(scene)

    async def submit_request(self, request: Request) -> str:
        """提交一个请求到调度器。

        根据当前资源可用性，请求可能被立即处理或加入等待队列。
        如果资源充足，请求会立即开始处理；否则进入优先队列等待。

        Args:
            request: 要提交的请求对象，包含场景ID、提示词和输出Token限制。

        Returns:
            请求ID，用于后续查询请求状态和结果。

        Raises:
            ValueError: 当请求的场景未注册时抛出。

        Example:
            >>> request = Request(
            ...     scene_id="chat",
            ...     prompt="What is AI?",
            ...     max_output_token=500
            ... )
            >>> request_id = await scheduler.submit_request(request)
            >>> print(f"Request ID: {request_id}")
        """
        async with self._lock:
            if request.scene_id not in self.scenes:
                logger.error(f"Submit request failed: Scene {request.scene_id} not registered")
                raise ValueError("Scene not registered")
            
            request.token_consumption = calculate_token_consumption(request)
            
            if self._has_available_resources(request.scene_id, request.token_consumption):
                request.status = RequestStatus.PROCESSING
                request.start_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.PROCESSING
                self.processing_requests[request.request_id] = request
                
                asyncio.create_task(self._process_single_request(request))
                logger.info(f"Request {request.request_id} from scene {request.scene_id} submitted and immediately processing, token_consumption={request.token_consumption}")
                return request.request_id
            else:
                request.status = RequestStatus.PENDING
                request.enqueue_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.PENDING
                
                scene = self.scenes[request.scene_id]
                priority = scene.priority
                enqueue_time = time.time()
                
                heapq.heappush(self.request_queue, (-priority, enqueue_time, request.request_id, request))
                
                logger.info(f"Request {request.request_id} from scene {request.scene_id} submitted and queued, token_consumption={request.token_consumption}")
                return request.request_id

    def get_request_status(self, request_id: str) -> Optional[RequestStatus]:
        """获取请求的当前状态。

        Args:
            request_id: 请求ID。

        Returns:
            请求状态枚举值，如果请求不存在则返回None。

        Example:
            >>> status = scheduler.get_request_status("req-123")
            >>> if status == RequestStatus.COMPLETED:
            ...     print("Request completed!")
        """
        return self.request_status.get(request_id)

    def get_request_result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """获取请求的处理结果。

        Args:
            request_id: 请求ID。

        Returns:
            包含请求结果的字典，如果请求不存在或未完成则返回None。
            结果字典包含request_id、scene_id、status、token_consumption
            和result或error字段。

        Example:
            >>> result = scheduler.get_request_result("req-123")
            >>> if result and result.get("status") == "completed":
            ...     print(f"Response: {result.get('result')}")
        """
        return self.request_results.get(request_id)

    def _has_available_resources(self, scene_id: str, token_consumption: int) -> bool:
        """检查是否有足够的资源处理请求。

        检查全局QPM/TPM限制和场景级别的QPM/TPM限制。

        Args:
            scene_id: 场景ID。
            token_consumption: 预估的Token消耗量。

        Returns:
            如果资源充足返回True，否则返回False。
        """
        total_load = self.monitor.get_total_load()
        scene_load = self.monitor.get_scene_load(scene_id)
        
        if scene_id not in self.scenes:
            return False
        
        scene = self.scenes[scene_id]
        
        logger.debug(f"Resource check for scene {scene_id}: global_qpm={total_load.qpm}/{self.total_qpm_limit}, global_tpm={total_load.tpm}/{self.total_tpm_limit}, scene_qpm={scene_load.qpm}/{scene.max_qpm}, scene_tpm={scene_load.tpm}/{scene.max_tpm}, token_needed={token_consumption}")
        
        if total_load.qpm >= self.total_qpm_limit:
            return False
        if total_load.tpm + token_consumption > self.total_tpm_limit:
            return False
        
        if scene_load.qpm >= scene.max_qpm:
            return False
        if scene_load.tpm + token_consumption > scene.max_tpm:
            return False
        
        return True
    
    def _is_resource_sufficient(self) -> bool:
        """判断系统是否处于资源充足状态。

        检查全局QPM和TPM是否都低于限制阈值。

        Returns:
            如果资源充足返回True，否则返回False。
        """
        total_load = self.monitor.get_total_load()
        return total_load.qpm < self.total_qpm_limit and total_load.tpm < self.total_tpm_limit

    async def _process_queue(self) -> None:
        """持续处理队列中的请求。

        该方法作为后台任务运行，从优先队列中取出请求并处理。
        当资源不足时，请求会被放回队列等待。

        Note:
            这是一个内部方法，由start()方法启动的后台任务调用。
        """
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

    async def _process_single_request(self, request: Request) -> None:
        """处理单个请求。

        将请求发送到LLM池处理，并记录处理时间和结果。
        处理完成后更新请求状态和结果。

        Args:
            request: 要处理的请求对象。

        Note:
            这是一个内部方法，处理过程中发生的异常会被捕获并记录，
            请求状态会被更新为FAILED。
        """
        try:
            logger.info(f"Processing request {request.request_id} from scene {request.scene_id}")
            start_process_time = time.time()
            result = await self.llm_pool.process_request(request)
            processing_time = time.time() - start_process_time
            
            async with self._lock:
                self.processing_times.append(processing_time)
                if len(self.processing_times) > self.max_processing_times_samples:
                    self.processing_times.pop(0)
                
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
                self.completed_requests[request.request_id] = request
            logger.info(f"Request {request.request_id} completed successfully in {processing_time:.3f}s, token_consumption={request.token_consumption}")
        except asyncio.CancelledError as e:
            logger.exception(f"Request {request.request_id} was cancelled")
            async with self._lock:
                request.status = RequestStatus.FAILED
                request.end_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.FAILED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "failed",
                    "token_consumption": request.token_consumption,
                    "error": "Request was cancelled"
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
                self.completed_requests[request.request_id] = request
            raise
        except ValueError as e:
            logger.exception(f"Request {request.request_id} failed due to invalid value: {str(e)}")
            async with self._lock:
                request.status = RequestStatus.FAILED
                request.end_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.FAILED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "failed",
                    "token_consumption": request.token_consumption,
                    "error": f"Invalid value: {str(e)}"
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
                self.completed_requests[request.request_id] = request
        except KeyError as e:
            logger.exception(f"Request {request.request_id} failed due to missing key: {str(e)}")
            async with self._lock:
                request.status = RequestStatus.FAILED
                request.end_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.FAILED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "failed",
                    "token_consumption": request.token_consumption,
                    "error": f"Missing required data: {str(e)}"
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
                self.completed_requests[request.request_id] = request
        except (AttributeError, TypeError) as e:
            logger.exception(f"Request {request.request_id} failed due to type or attribute error: {str(e)}")
            async with self._lock:
                request.status = RequestStatus.FAILED
                request.end_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.FAILED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "failed",
                    "token_consumption": request.token_consumption,
                    "error": f"Type or attribute error: {str(e)}"
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
                self.completed_requests[request.request_id] = request
        except Exception as e:
            logger.exception(f"Request {request.request_id} failed with unexpected error: {str(e)}")
            async with self._lock:
                request.status = RequestStatus.FAILED
                request.end_time = datetime.now()
                
                self.request_status[request.request_id] = RequestStatus.FAILED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "failed",
                    "token_consumption": request.token_consumption,
                    "error": f"Unexpected error: {str(e)}"
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
                self.completed_requests[request.request_id] = request

    async def _cleanup_completed_requests(self) -> None:
        """定期清理已完成的请求，防止内存泄漏。

        该方法作为后台任务运行，每分钟检查一次已完成请求数量，
        如果超过限制则保留最新的请求，删除旧的请求记录。

        Note:
            这是一个内部方法，由start()方法启动的后台任务调用。
        """
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

    async def start(self) -> None:
        """启动调度器。

        启动队列处理任务和清理任务。如果调度器已经在运行，
        则不会重复启动。

        Example:
            >>> await scheduler.start()
        """
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        self._cleanup_task = asyncio.create_task(self._cleanup_completed_requests())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """停止调度器。

        停止队列处理任务和清理任务，等待正在运行的任务完成。

        Example:
            >>> await scheduler.stop()
        """
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

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统整体状态。

        返回全局资源使用情况、队列长度、处理中请求数量和各场景状态。

        Returns:
            包含系统状态的字典，包括:
            - total_qpm_limit: 全局QPM限制
            - total_tpm_limit: 全局TPM限制
            - current_total_qpm: 当前全局QPM
            - current_total_tpm: 当前全局TPM
            - queue_length: 队列长度
            - processing_count: 处理中请求数量
            - scenes: 各场景状态字典

        Example:
            >>> status = scheduler.get_system_status()
            >>> print(f"Queue length: {status['queue_length']}")
        """
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
    
    def estimate_wait_time(self, request_id: str) -> int | None:
        """估算请求的等待时间。

        基于队列中优先级更高的请求数量和平均处理时间估算等待时间。

        Args:
            request_id: 请求ID。

        Returns:
            预估等待时间（毫秒），如果请求不在队列中或没有历史处理数据则返回None。

        Example:
            >>> wait_time = scheduler.estimate_wait_time("req-123")
            >>> if wait_time:
            ...     print(f"Estimated wait: {wait_time}ms")
        """
        if not self.processing_times:
            return None
        
        avg_processing_time = sum(self.processing_times) / len(self.processing_times)
        
        request_info = None
        request_priority = 0
        for item in self.request_queue:
            neg_priority, enqueue_time, req_id, request = item
            if req_id == request_id:
                request_info = item
                request_priority = -neg_priority
                break
        
        if not request_info:
            return None
        
        higher_priority_count = 0
        same_priority_ahead = 0
        found_self = False
        
        for item in self.request_queue:
            neg_priority, enqueue_time, req_id, request = item
            priority = -neg_priority
            
            if req_id == request_id:
                found_self = True
                continue
            
            if not found_self:
                if priority > request_priority:
                    higher_priority_count += 1
                elif priority == request_priority and enqueue_time < request_info[1]:
                    same_priority_ahead += 1
        
        total_requests_ahead = higher_priority_count + same_priority_ahead
        
        estimated_wait_seconds = total_requests_ahead * avg_processing_time
        
        estimated_wait_ms = int(estimated_wait_seconds * 1000)
        
        return estimated_wait_ms


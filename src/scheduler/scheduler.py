
import asyncio
import time

from .models import Scene, Request, calculate_token_consumption, RequestStatus
from .monitor import ResourceMonitor
from .llm_pool import MockLLMPool


class Scheduler:
    def __init__(
        self,
        monitor,
        llm_pool,
        total_qpm_limit=1000,
        total_tpm_limit=1000000,
    ):
        self.monitor = monitor
        self.llm_pool = llm_pool
        self.total_qpm_limit = total_qpm_limit
        self.total_tpm_limit = total_tpm_limit
        
        self.scenes = {}
        self.request_queue = []
        self.processing_requests = {}
        self.request_status = {}
        self.request_results = {}
        
        self._lock = asyncio.Lock()
        self._running = False
        self._worker_task = None

    def register_scene(self, scene):
        self.scenes[scene.scene_id] = scene

    async def submit_request(self, request):
        async with self._lock:
            self.request_status[request.request_id] = RequestStatus.PENDING
            
            if request.scene_id not in self.scenes:
                raise ValueError("Scene not registered")
            
            scene = self.scenes[request.scene_id]
            priority = scene.priority
            enqueue_time = time.time()
            
            self.request_queue.append((-priority, enqueue_time, request.request_id, request))
            self.request_queue.sort(key=lambda x: (x[0], x[1], x[2]))
            
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
        
        if total_load.qpm >= self.total_qpm_limit:
            return False
        if total_load.tpm + token_consumption > self.total_tpm_limit:
            return False
        
        if scene_load.qpm >= scene.max_qpm:
            return False
        if scene_load.tpm + token_consumption > scene.max_tpm:
            return False
        
        return True

    async def _process_queue(self):
        while self._running:
            async with self._lock:
                if not self.request_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                processed_index = None
                for i in range(len(self.request_queue)):
                    neg_priority, enqueue_time, req_id, request = self.request_queue[i]
                    token_consumption = calculate_token_consumption(request)
                    
                    if self._has_available_resources(request.scene_id, token_consumption):
                        self.request_queue.pop(i)
                        self.request_status[request.request_id] = RequestStatus.PROCESSING
                        self.processing_requests[request.request_id] = request
                        
                        asyncio.create_task(self._process_single_request(request))
                        processed_index = i
                        break
                
                if processed_index is None:
                    await asyncio.sleep(0.1)

    async def _process_single_request(self, request):
        try:
            result = await self.llm_pool.process_request(request)
            async with self._lock:
                self.request_status[request.request_id] = RequestStatus.COMPLETED
                self.request_results[request.request_id] = result
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]
        except Exception as e:
            async with self._lock:
                self.request_status[request.request_id] = RequestStatus.FAILED
                self.request_results[request.request_id] = {
                    "request_id": request.request_id,
                    "scene_id": request.scene_id,
                    "status": "failed",
                    "error": str(e)
                }
                if request.request_id in self.processing_requests:
                    del self.processing_requests[request.request_id]

    async def start(self):
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

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


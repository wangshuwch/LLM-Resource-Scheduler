
import asyncio
import sys
import os
import random
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scheduler.models import Scene, Request, RequestStatus
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool
from src.scheduler.scheduler import Scheduler


async def monitor_system_status(scheduler: Scheduler, stop_event: asyncio.Event, interval: float = 0.5):
    print("\n" + "=" * 100)
    print("时间".ljust(15) + "总QPM".ljust(12) + "总TPM".ljust(15) + "队列长度".ljust(12) + "处理中".ljust(10))
    print("-" * 100)
    
    while not stop_event.is_set():
        try:
            status = scheduler.get_system_status()
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            row = (timestamp.ljust(15) + 
                   str(status['current_total_qpm']).ljust(12) + 
                   str(status['current_total_tpm']).ljust(15) + 
                   str(status['queue_length']).ljust(12) + 
                   str(status['processing_count']).ljust(10))
            print(row)
            
            for scene_id, scene_status in status['scenes'].items():
                scene_row = ("  " + scene_id.ljust(12) + 
                           " QPM: " + str(scene_status['current_qpm']).ljust(4) + "/" + 
                           str(scene_status['max_qpm']).ljust(4) + 
                           " TPM: " + str(scene_status['current_tpm']).ljust(7) + "/" + 
                           str(scene_status['max_tpm']).ljust(7))
                print(scene_row)
            
            print("-" * 100)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break


async def generate_requests(scheduler: Scheduler, scene_id: str, num_requests: int, delay: float = 0.1):
    request_ids = []
    for i in range(num_requests):
        prompt = "Request " + str(i+1) + " for " + scene_id + ": " + "x" * random.randint(50, 150)
        req = Request(
            scene_id=scene_id,
            prompt=prompt,
            max_output_token=random.randint(50, 200)
        )
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
        await asyncio.sleep(delay)
    return request_ids


async def wait_for_requests(scheduler: Scheduler, request_ids, timeout=30):
    start_time = asyncio.get_event_loop().time()
    while True:
        all_completed = True
        completed_count = 0
        failed_count = 0
        
        for req_id in request_ids:
            status = scheduler.get_request_status(req_id)
            if status == RequestStatus.COMPLETED:
                completed_count += 1
            elif status == RequestStatus.FAILED:
                failed_count += 1
            else:
                all_completed = False
        
        if all_completed:
            return completed_count, failed_count
        
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout:
            return completed_count, failed_count
        
        await asyncio.sleep(0.5)


async def main():
    print("=" * 100)
    print("LLM 资源调度器 - 完整 Mock 资源池调度演示")
    print("=" * 100)
    
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=30, max_delay_ms=100)
    
    total_qpm_limit = 100
    total_tpm_limit = 100000
    scheduler = Scheduler(monitor, llm_pool, total_qpm_limit=total_qpm_limit, total_tpm_limit=total_tpm_limit)
    
    print("\n系统配置:")
    print("  总 QPM 限制:", total_qpm_limit)
    print("  总 TPM 限制:", total_tpm_limit)
    
    print("\n注册场景:")
    scene_vip = Scene(scene_id="vip_service", priority=10, max_qpm=50, max_tpm=50000)
    scene_normal = Scene(scene_id="standard_service", priority=5, max_qpm=30, max_tpm=30000)
    scene_batch = Scene(scene_id="batch_jobs", priority=2, max_qpm=20, max_tpm=20000)
    
    scheduler.register_scene(scene_vip)
    scheduler.register_scene(scene_normal)
    scheduler.register_scene(scene_batch)
    
    print("  vip_service     (优先级 10): QPM=", scene_vip.max_qpm, ", TPM=", scene_vip.max_tpm)
    print("  standard_service (优先级 5): QPM=", scene_normal.max_qpm, ", TPM=", scene_normal.max_tpm)
    print("  batch_jobs      (优先级 2): QPM=", scene_batch.max_qpm, ", TPM=", scene_batch.max_tpm)
    
    await scheduler.start()
    
    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(monitor_system_status(scheduler, stop_event, interval=0.8))
    
    print("\n开始生成请求...")
    
    all_request_ids = []
    
    vip_task = asyncio.create_task(generate_requests(scheduler, "vip_service", 15, delay=0.08))
    normal_task = asyncio.create_task(generate_requests(scheduler, "standard_service", 25, delay=0.06))
    batch_task = asyncio.create_task(generate_requests(scheduler, "batch_jobs", 30, delay=0.1))
    
    vip_ids = await vip_task
    normal_ids = await normal_task
    batch_ids = await batch_task
    
    all_request_ids = vip_ids + normal_ids + batch_ids
    
    print("\n所有", len(all_request_ids), "个请求已提交，等待处理完成...")
    
    completed_count, failed_count = await wait_for_requests(scheduler, all_request_ids, timeout=60)
    
    stop_event.set()
    await monitor_task
    
    await scheduler.stop()
    
    print("\n" + "=" * 100)
    print("调度结果统计:")
    print("=" * 100)
    print("  总请求数:", len(all_request_ids))
    print("  成功完成:", completed_count)
    print("  失败:", failed_count)
    
    final_status = scheduler.get_system_status()
    print("\n  最终总 QPM:", final_status['current_total_qpm'], "/", final_status['total_qpm_limit'])
    print("  最终总 TPM:", final_status['current_total_tpm'], "/", final_status['total_tpm_limit'])
    
    print("\n  各场景状态:")
    for scene_id, scene_status in final_status['scenes'].items():
        print("    ", scene_id, ": QPM=", scene_status['current_qpm'], "/", scene_status['max_qpm'], 
              ", TPM=", scene_status['current_tpm'], "/", scene_status['max_tpm'])
    
    print("\n" + "=" * 100)
    print("演示完成！")
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())

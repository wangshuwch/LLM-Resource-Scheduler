
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


async def monitor_system_status(scheduler: Scheduler, interval: float = 0.5):
    print("\n" + "=" * 80)
    print(f"{'时间':<20} {'总QPM':<10} {'总TPM':<15} {'队列长度':<10} {'处理中':<10}")
    print("-" * 80)
    
    while True:
        try:
            status = scheduler.get_system_status()
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"{timestamp:<20} {status['current_total_qpm']:<10} {status['current_total_tpm']:<15} {status['queue_length']:<10} {status['processing_count']:<10}")
            
            for scene_id, scene_status in status['scenes'].items():
                print(f"  {scene_id:<15} QPM: {scene_status['current_qpm']:<5}/{scene_status['max_qpm']:<5} TPM: {scene_status['current_tpm']:<8}/{scene_status['max_tpm']:<8}")
            
            print("-" * 80)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break


async def generate_requests(scheduler: Scheduler, scene_id: str, num_requests: int, delay: float = 0.1):
    for i in range(num_requests):
        prompt = f"Request {i+1} for {scene_id}: " + "x" * random.randint(50, 200)
        req = Request(
            scene_id=scene_id,
            prompt=prompt,
            max_output_token=random.randint(50, 300)
        )
        await scheduler.submit_request(req)
        await asyncio.sleep(delay)


async def main():
    print("=" * 80)
    print("LLM 资源调度器 - 资源竞争与超卖场景演示")
    print("=" * 80)
    
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=50, max_delay_ms=150)
    
    total_qpm_limit = 50
    total_tpm_limit = 50000
    scheduler = Scheduler(monitor, llm_pool, total_qpm_limit=total_qpm_limit, total_tpm_limit=total_tpm_limit)
    
    print(f"\n系统配置:")
    print(f"  总 QPM 限制: {total_qpm_limit}")
    print(f"  总 TPM 限制: {total_tpm_limit}")
    
    print("\n注册场景（超卖配置）:")
    scene_high = Scene(scene_id="critical", priority=10, max_qpm=40, max_tpm=40000)
    scene_medium = Scene(scene_id="standard", priority=5, max_qpm=30, max_tpm=30000)
    scene_low = Scene(scene_id="batch", priority=2, max_qpm=20, max_tpm=20000)
    
    scheduler.register_scene(scene_high)
    scheduler.register_scene(scene_medium)
    scheduler.register_scene(scene_low)
    
    print(f"  critical (优先级 10): QPM={scene_high.max_qpm}, TPM={scene_high.max_tpm}")
    print(f"  standard (优先级 5): QPM={scene_medium.max_qpm}, TPM={scene_medium.max_tpm}")
    print(f"  batch (优先级 2): QPM={scene_low.max_qpm}, TPM={scene_low.max_tpm}")
    print(f"  场景总和: QPM={scene_high.max_qpm + scene_medium.max_qpm + scene_low.max_qpm} (超卖!), TPM={scene_high.max_tpm + scene_medium.max_tpm + scene_low.max_tpm} (超卖!)")
    
    await scheduler.start()
    
    monitor_task = asyncio.create_task(monitor_system_status(scheduler, interval=1.0))
    
    print("\n开始生成请求...")
    
    critical_task = asyncio.create_task(generate_requests(scheduler, "critical", 20, delay=0.05))
    standard_task = asyncio.create_task(generate_requests(scheduler, "standard", 30, delay=0.08))
    batch_task = asyncio.create_task(generate_requests(scheduler, "batch", 40, delay=0.1))
    
    await asyncio.gather(critical_task, standard_task, batch_task)
    
    print("\n所有请求已提交，等待处理完成...")
    await asyncio.sleep(5)
    
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    
    await scheduler.stop()
    
    print("\n" + "=" * 80)
    print("演示完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())


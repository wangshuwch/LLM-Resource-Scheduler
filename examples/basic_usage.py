
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scheduler.models import Scene, Request
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool
from src.scheduler.scheduler import Scheduler


async def main():
    print("=" * 60)
    print("LLM 资源调度器 - 基础使用示例")
    print("=" * 60)
    
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=100, max_delay_ms=300)
    scheduler = Scheduler(monitor, llm_pool, total_qpm_limit=100, total_tpm_limit=100000)
    
    print("\n1. 注册场景...")
    scene1 = Scene(scene_id="chatbot", priority=8, max_qpm=50, max_tpm=50000)
    scene2 = Scene(scene_id="analytics", priority=5, max_qpm=30, max_tpm=30000)
    scene3 = Scene(scene_id="background", priority=2, max_qpm=20, max_tpm=20000)
    
    scheduler.register_scene(scene1)
    scheduler.register_scene(scene2)
    scheduler.register_scene(scene3)
    print(f"   ✓ 已注册 3 个场景")
    print(f"     - chatbot (优先级: 8, QPM: 50, TPM: 50000)")
    print(f"     - analytics (优先级: 5, QPM: 30, TPM: 30000)")
    print(f"     - background (优先级: 2, QPM: 20, TPM: 20000)")
    
    await scheduler.start()
    
    print("\n2. 提交请求...")
    requests = []
    request_ids = []
    
    for i in range(5):
        req = Request(
            scene_id="chatbot",
            prompt=f"Chatbot request {i+1}: Hello, how are you?",
            max_output_token=100
        )
        requests.append(req)
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
        print(f"   ✓ 提交 chatbot 请求 {i+1}, ID: {req_id[:8]}...")
    
    for i in range(3):
        req = Request(
            scene_id="analytics",
            prompt=f"Analytics request {i+1}: Analyze this data...",
            max_output_token=200
        )
        requests.append(req)
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
        print(f"   ✓ 提交 analytics 请求 {i+1}, ID: {req_id[:8]}...")
    
    print("\n3. 等待请求处理...")
    await asyncio.sleep(2)
    
    print("\n4. 查询请求状态和结果...")
    for req_id in request_ids:
        status = scheduler.get_request_status(req_id)
        result = scheduler.get_request_result(req_id)
        print(f"   请求 {req_id[:8]}: 状态={status}, 结果={result}")
    
    print("\n5. 系统状态...")
    status = scheduler.get_system_status()
    print(f"   总 QPM: {status['current_total_qpm']}/{status['total_qpm_limit']}")
    print(f"   总 TPM: {status['current_total_tpm']}/{status['total_tpm_limit']}")
    print(f"   队列长度: {status['queue_length']}")
    print(f"   处理中: {status['processing_count']}")
    
    await scheduler.stop()
    print("\n" + "=" * 60)
    print("示例执行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())


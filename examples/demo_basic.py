
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scheduler.models import Scene, Request, RequestStatus, calculate_token_consumption
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool


async def main():
    print("=" * 60)
    print("LLM 资源调度器 - 基础功能演示")
    print("=" * 60)
    
    print("\n1. 初始化组件...")
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=100, max_delay_ms=300)
    print("   ✓ ResourceMonitor 初始化完成")
    print("   ✓ MockLLMPool 初始化完成")
    
    print("\n2. 定义场景...")
    scene1 = Scene(scene_id="chatbot", priority=8, max_qpm=50, max_tpm=50000)
    scene2 = Scene(scene_id="analytics", priority=5, max_qpm=30, max_tpm=30000)
    print(f"   ✓ 场景 1: {scene1.scene_id} (优先级: {scene1.priority})")
    print(f"   ✓ 场景 2: {scene2.scene_id} (优先级: {scene2.priority})")
    
    print("\n3. 测试 Token 计算...")
    test_req = Request(
        scene_id="chatbot",
        prompt="Hello, how are you today?",
        max_output_token=100
    )
    token_count = calculate_token_consumption(test_req)
    print(f"   ✓ Prompt: '{test_req.prompt}'")
    print(f"   ✓ Max output tokens: {test_req.max_output_token}")
    print(f"   ✓ 总 Token 消耗: {token_count}")
    
    print("\n4. 处理请求...")
    requests = []
    for i in range(3):
        req = Request(
            scene_id="chatbot",
            prompt=f"Test request {i+1}",
            max_output_token=50
        )
        requests.append(req)
        print(f"   提交请求 {i+1}: {req.request_id[:8]}...")
    
    print("\n5. 异步处理请求...")
    results = await asyncio.gather(*[llm_pool.process_request(req) for req in requests])
    for i, result in enumerate(results):
        print(f"   请求 {i+1} 结果: {result['status']}, Token消耗: {result['token_consumption']}")
    
    print("\n6. 查看资源监控...")
    total_load = monitor.get_total_load()
    print(f"   总 QPM: {total_load.qpm}")
    print(f"   总 TPM: {total_load.tpm}")
    
    scene_load = monitor.get_scene_load("chatbot")
    print(f"   chatbot 场景 QPM: {scene_load.qpm}")
    print(f"   chatbot 场景 TPM: {scene_load.tpm}")
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())


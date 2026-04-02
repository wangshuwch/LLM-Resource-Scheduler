
import asyncio
import time
from src.scheduler.models import Scene, Request, RequestStatus
from src.scheduler.monitor import ResourceMonitor
from src.scheduler.llm_pool import MockLLMPool
from src.scheduler.scheduler import Scheduler


async def test_resource_monitoring_accuracy():
    print("\n" + "="*80)
    print("测试1: 资源监控准确性验证 (误差<5%)")
    print("="*80)
    
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=10, max_delay_ms=20)
    scheduler = Scheduler(monitor, llm_pool, total_qpm_limit=1000, total_tpm_limit=1000000)
    
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=100, max_tpm=100000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    num_requests = 50
    requests = []
    for i in range(num_requests):
        req = Request(
            scene_id="test_scene",
            prompt=f"Test request {i}",
            max_output_token=100
        )
        requests.append(req)
    
    request_ids = []
    for req in requests:
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
    
    await asyncio.sleep(3)
    
    total_load = monitor.get_total_load()
    scene_load = monitor.get_scene_load("test_scene")
    
    expected_qpm = num_requests
    actual_qpm = total_load.qpm
    qpm_error = abs(actual_qpm - expected_qpm) / expected_qpm * 100
    
    print(f"\nQPM 统计:")
    print(f"  预期 QPM: {expected_qpm}")
    print(f"  实际 QPM: {actual_qpm}")
    print(f"  误差: {qpm_error:.2f}%")
    
    expected_tpm_min = num_requests * 100
    actual_tpm = total_load.tpm
    tpm_error_min = abs(actual_tpm - expected_tpm_min) / expected_tpm_min * 100
    
    print(f"\nTPM 统计:")
    print(f"  预期 TPM (最小): {expected_tpm_min}")
    print(f"  实际 TPM: {actual_tpm}")
    print(f"  误差 (最小): {tpm_error_min:.2f}%")
    
    await scheduler.stop()
    
    qpm_passed = qpm_error < 5
    tpm_passed = tpm_error_min < 5
    
    print(f"\n测试结果:")
    print(f"  QPM 监控准确性: {'✓ 通过' if qpm_passed else '✗ 未通过'} (误差 {qpm_error:.2f}% < 5%)")
    print(f"  TPM 监控准确性: {'✓ 通过' if tpm_passed else '✗ 未通过'} (误差 {tpm_error_min:.2f}% < 5%)")
    
    return qpm_passed and tpm_passed


async def test_resource_utilization():
    print("\n" + "="*80)
    print("测试2: 资源充足时利用率验证 (>90%)")
    print("="*80)
    
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=10, max_delay_ms=20)
    
    total_qpm_limit = 100
    total_tpm_limit = 10000
    scheduler = Scheduler(monitor, llm_pool, total_qpm_limit=total_qpm_limit, total_tpm_limit=total_tpm_limit)
    
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=total_qpm_limit, max_tpm=total_tpm_limit)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    num_requests = 95
    requests = []
    for i in range(num_requests):
        req = Request(
            scene_id="test_scene",
            prompt=f"Utilization test {i}",
            max_output_token=100
        )
        requests.append(req)
    
    request_ids = []
    for req in requests:
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
        await asyncio.sleep(0.01)
    
    await asyncio.sleep(3)
    
    total_load = monitor.get_total_load()
    
    qpm_utilization = total_load.qpm / total_qpm_limit * 100
    
    print(f"\n资源利用率:")
    print(f"  总 QPM 限制: {total_qpm_limit}")
    print(f"  实际 QPM: {total_load.qpm}")
    print(f"  QPM 利用率: {qpm_utilization:.2f}%")
    
    await scheduler.stop()
    
    utilization_passed = qpm_utilization >= 90
    
    print(f"\n测试结果:")
    print(f"  资源利用率: {'✓ 通过' if utilization_passed else '✗ 未通过'} (利用率 {qpm_utilization:.2f}% >= 90%)")
    
    return utilization_passed


async def test_scene_resource_limits():
    print("\n" + "="*80)
    print("测试3: 各场景按最大资源限制充分使用")
    print("="*80)
    
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=10, max_delay_ms=20)
    
    total_qpm_limit = 200
    total_tpm_limit = 200000
    scheduler = Scheduler(monitor, llm_pool, total_qpm_limit=total_qpm_limit, total_tpm_limit=total_tpm_limit)
    
    scene1 = Scene(scene_id="scene1", priority=10, max_qpm=50, max_tpm=50000)
    scene2 = Scene(scene_id="scene2", priority=5, max_qpm=30, max_tpm=30000)
    scene3 = Scene(scene_id="scene3", priority=1, max_qpm=20, max_tpm=20000)
    
    scheduler.register_scene(scene1)
    scheduler.register_scene(scene2)
    scheduler.register_scene(scene3)
    
    await scheduler.start()
    
    tasks = []
    
    async def generate_scene_requests(scene_id, count):
        for i in range(count):
            req = Request(
                scene_id=scene_id,
                prompt=f"Scene request {i}",
                max_output_token=100
            )
            await scheduler.submit_request(req)
            await asyncio.sleep(0.01)
    
    tasks.append(generate_scene_requests("scene1", 50))
    tasks.append(generate_scene_requests("scene2", 30))
    tasks.append(generate_scene_requests("scene3", 20))
    
    await asyncio.gather(*tasks)
    
    await asyncio.sleep(3)
    
    scene1_load = monitor.get_scene_load("scene1")
    scene2_load = monitor.get_scene_load("scene2")
    scene3_load = monitor.get_scene_load("scene3")
    
    print(f"\n场景资源使用情况:")
    print(f"  scene1 (优先级10): QPM {scene1_load.qpm}/{scene1.max_qpm}, TPM {scene1_load.tpm}/{scene1.max_tpm}")
    print(f"  scene2 (优先级5): QPM {scene2_load.qpm}/{scene2.max_qpm}, TPM {scene2_load.tpm}/{scene2.max_tpm}")
    print(f"  scene3 (优先级1): QPM {scene3_load.qpm}/{scene3.max_qpm}, TPM {scene3_load.tpm}/{scene3.max_tpm}")
    
    scene1_qpm_ok = scene1_load.qpm <= scene1.max_qpm
    scene2_qpm_ok = scene2_load.qpm <= scene2.max_qpm
    scene3_qpm_ok = scene3_load.qpm <= scene3.max_qpm
    
    scene1_tpm_ok = scene1_load.tpm <= scene1.max_tpm
    scene2_tpm_ok = scene2_load.tpm <= scene2.max_tpm
    scene3_tpm_ok = scene3_load.tpm <= scene3.max_tpm
    
    await scheduler.stop()
    
    all_passed = all([scene1_qpm_ok, scene2_qpm_ok, scene3_qpm_ok, 
                      scene1_tpm_ok, scene2_tpm_ok, scene3_tpm_ok])
    
    print(f"\n测试结果:")
    print(f"  scene1 QPM 限制: {'✓ 通过' if scene1_qpm_ok else '✗ 未通过'}")
    print(f"  scene2 QPM 限制: {'✓ 通过' if scene2_qpm_ok else '✗ 未通过'}")
    print(f"  scene3 QPM 限制: {'✓ 通过' if scene3_qpm_ok else '✗ 未通过'}")
    print(f"  scene1 TPM 限制: {'✓ 通过' if scene1_tpm_ok else '✗ 未通过'}")
    print(f"  scene2 TPM 限制: {'✓ 通过' if scene2_tpm_ok else '✗ 未通过'}")
    print(f"  scene3 TPM 限制: {'✓ 通过' if scene3_tpm_ok else '✗ 未通过'}")
    
    return all_passed


async def test_system_stability():
    print("\n" + "="*80)
    print("测试4: 系统稳定性验证")
    print("="*80)
    
    monitor = ResourceMonitor()
    llm_pool = MockLLMPool(monitor, min_delay_ms=5, max_delay_ms=10)
    scheduler = Scheduler(monitor, llm_pool, total_qpm_limit=500, total_tpm_limit=500000)
    
    scene = Scene(scene_id="test_scene", priority=5, max_qpm=500, max_tpm=500000)
    scheduler.register_scene(scene)
    
    await scheduler.start()
    
    num_requests = 200
    print(f"\n提交 {num_requests} 个并发请求...")
    
    request_ids = []
    for i in range(num_requests):
        req = Request(
            scene_id="test_scene",
            prompt=f"Stability test {i}",
            max_output_token=50
        )
        req_id = await scheduler.submit_request(req)
        request_ids.append(req_id)
    
    print("等待所有请求处理完成...")
    await asyncio.sleep(5)
    
    completed_count = 0
    failed_count = 0
    pending_count = 0
    
    for req_id in request_ids:
        status = scheduler.get_request_status(req_id)
        if status == RequestStatus.COMPLETED:
            completed_count += 1
        elif status == RequestStatus.FAILED:
            failed_count += 1
        else:
            pending_count += 1
    
    print(f"\n请求处理结果:")
    print(f"  总请求数: {num_requests}")
    print(f"  成功完成: {completed_count}")
    print(f"  失败: {failed_count}")
    print(f"  待处理: {pending_count}")
    
    await scheduler.stop()
    
    success_rate = completed_count / num_requests * 100
    stability_passed = success_rate >= 99 and failed_count == 0
    
    print(f"\n测试结果:")
    print(f"  系统稳定性: {'✓ 通过' if stability_passed else '✗ 未通过'} (成功率 {success_rate:.2f}%)")
    
    return stability_passed


async def main():
    print("\n" + "="*80)
    print("LLM 资源调度器 - 验收标准验证")
    print("="*80)
    
    results = {}
    
    results['resource_monitoring'] = await test_resource_monitoring_accuracy()
    results['resource_utilization'] = await test_resource_utilization()
    results['scene_limits'] = await test_scene_resource_limits()
    results['system_stability'] = await test_system_stability()
    
    print("\n" + "="*80)
    print("验收测试总结")
    print("="*80)
    
    all_passed = all(results.values())
    
    print(f"\n1. 资源监控准确性 (误差<5%): {'✓ 通过' if results['resource_monitoring'] else '✗ 未通过'}")
    print(f"2. 资源充足时利用率 (>90%): {'✓ 通过' if results['resource_utilization'] else '✗ 未通过'}")
    print(f"3. 场景资源限制执行: {'✓ 通过' if results['scene_limits'] else '✗ 未通过'}")
    print(f"4. 系统稳定性: {'✓ 通过' if results['system_stability'] else '✗ 未通过'}")
    
    print(f"\n总体结果: {'✓ 所有验收标准通过' if all_passed else '✗ 部分验收标准未通过'}")
    print("="*80 + "\n")
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(main())

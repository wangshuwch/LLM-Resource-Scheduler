# 示例脚本说明

本目录包含了 LLM 资源调度器的使用示例脚本。

## 快速开始

### 前置条件

确保已安装项目依赖：

```bash
pip install -r ../requirements.txt
```

## 示例脚本

### 1. demo_basic.py - 基础功能演示

这个脚本演示了系统的基础功能：

- 初始化 ResourceMonitor 和 MockLLMPool
- 创建场景配置
- 计算 Token 消耗
- 处理请求
- 查看资源监控数据

**运行方式：**

```bash
python demo_basic.py
```

**输出示例：**

```
============================================================
LLM 资源调度器 - 基础功能演示
============================================================

1. 初始化组件...
   ✓ ResourceMonitor 初始化完成
   ✓ MockLLMPool 初始化完成

2. 定义场景...
   ✓ 场景 1: chatbot (优先级: 8)
   ✓ 场景 2: analytics (优先级: 5)

3. 测试 Token 计算...
   ✓ Prompt: 'Hello, how are you today?'
   ✓ Max output tokens: 100
   ✓ 总 Token 消耗: 107

4. 处理请求...
   提交请求 1: bb13ae18...
   提交请求 2: e9f741f7...
   提交请求 3: 53bf3469...

5. 异步处理请求...
   请求 1 结果: completed, Token消耗: 54
   请求 2 结果: completed, Token消耗: 54
   请求 3 结果: completed, Token消耗: 54

6. 查看资源监控...
   总 QPM: 3
   总 TPM: 162
   chatbot 场景 QPM: 3
   chatbot 场景 TPM: 162

============================================================
演示完成！
============================================================
```

## 核心模块说明

### 1. ResourceMonitor（资源监控模块）

负责实时跟踪 QPM 和 TPM：

```python
from src.scheduler.monitor import ResourceMonitor

monitor = ResourceMonitor()
monitor.record_request(request)
total_load = monitor.get_total_load()
scene_load = monitor.get_scene_load("scene_id")
```

### 2. MockLLMPool（Mock LLM 资源池）

模拟 LLM 服务，用于测试：

```python
from src.scheduler.llm_pool import MockLLMPool

llm_pool = MockLLMPool(monitor, min_delay_ms=100, max_delay_ms=300)
result = await llm_pool.process_request(request)
```

### 3. 数据模型

- **Scene**: 场景配置（优先级、最大 QPM/TPM）
- **Request**: 请求数据（场景 ID、Prompt、最大输出 Token）
- **LoadMetrics**: 负载指标（QPM、TPM）

```python
from src.scheduler.models import Scene, Request, calculate_token_consumption

scene = Scene(scene_id="chatbot", priority=8, max_qpm=50, max_tpm=50000)
request = Request(scene_id="chatbot", prompt="Hello", max_output_token=100)
token_count = calculate_token_consumption(request)
```

## 项目结构

```
examples/
├── README.md              # 本文档
├── demo_basic.py          # 基础功能演示
└── basic_usage.py         # 高级功能（待完善）
```

## 下一步

- 查看 [tests/](../tests/) 目录了解更多测试用例
- 参考 [design plan](../.trae/documents/llm-resource-scheduler-plan.md) 了解系统设计

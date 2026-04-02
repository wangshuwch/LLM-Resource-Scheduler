# LLM多场景资源动态分配系统设计计划

## 1. 系统架构设计

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway Layer                          │
│  (资源分配核心接口 / 场景配置接口 / 请求提交接口)                  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      场景配置模块 (Scene Config)                   │
│  - 场景优先级管理                                                   │
│  - 最大资源限制配置                                                 │
│  - QPM/TPM阈值设置                                                 │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      动态调度引擎 (Scheduler Engine)                │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  │ 资源计算模块      │  │ 优先级分配算法    │  │ 队列调度算法      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘
└─────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│      资源监控模块 (Monitor)       │  │      请求队列管理 (Queue)        │
├─────────────────────────────────┤  ├─────────────────────────────────┤
│  - 总负载跟踪 (QPM/TPM)          │  │  - 优先级+时间排序               │
│  - 各场景资源使用统计             │  │  - 队列状态管理                   │
│  - 实时指标采集                   │  │  - 队列消费策略                   │
└─────────────────────────────────┘  └─────────────────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Mock LLM 资源池 (LLM Pool)                      │
│  - 模拟LLM服务                                                     │
│  - 资源使用模拟                                                     │
│  - 响应延迟模拟                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心模块职责

#### 资源监控模块 (Resource Monitor)

* 实时跟踪LLM服务总负载：QPM（每分钟查询次数）、TPM（每分钟令牌数）

* 按场景维度统计资源使用情况

* 维护滑动窗口计数器

* 提供资源状态查询接口

#### 动态调度引擎 (Scheduler Engine)

* 资源充足场景：各场景充分利用资源

* 资源竞争场景：按优先级分配资源

* 实现超卖机制：各场景最大资源限制总和可超过整体资源

* Token消耗量计算：基于prompt长度和max\_output\_token

#### 请求队列管理 (Request Queue)

* 基于优先级和入队时间的请求排序

* 队列消费策略：高优先级优先，同优先级先来先服务

* 队列状态查询：队列长度、等待时间等

#### 场景配置模块 (Scene Config)

* 场景优先级配置

* 各场景最大QPM/TPM限制配置

* 配置热更新支持

## 2. 核心功能实现方案

### 2.1 资源充足场景 (总请求 ≤ 总负载)

* 各场景按配置的最大资源限制充分使用

* 无需排队，直接处理请求

* 实时监控资源使用，防止超限

### 2.2 资源竞争场景 (总请求 > 总负载)

* 基于优先级的资源分配算法

* 高优先级场景优先分配资源

* 低优先级场景请求进入队列等待

* 动态调整各场景资源配额

### 2.3 超卖机制

* 各场景配置独立的最大资源限制

* 所有场景最大资源限制总和可超过LLM整体资源

* 动态调度引擎根据实际负载进行资源分配

### 2.4 请求排队机制

* 队列元素：场景ID、请求ID、优先级、入队时间、token消耗预估

* 排序规则：优先级降序 → 入队时间升序

* 队列消费：按排序顺序依次处理

## 3. 关键算法设计

### 3.1 资源计算模型

```python
def calculate_token_consumption(request):
    prompt_tokens = len(tiktoken.encode(request.prompt))
    total_tokens = prompt_tokens + request.max_output_token
    return total_tokens
```

### 3.2 动态分配算法

```
输入：
- total_qpm_limit: LLM总QPM限制
- total_tpm_limit: LLM总TPM限制
- scenes: 场景配置列表 [scene_id, priority, max_qpm, max_tpm]
- current_load: 当前负载 {scene_id: {qpm, tpm}}
- pending_requests: 待处理请求队列

算法：
1. 计算总剩余可用资源
   available_qpm = total_qpm_limit - sum(current_load[scene].qpm for all scenes)
   available_tpm = total_tpm_limit - sum(current_load[scene].tpm for all scenes)

2. 按优先级对场景排序（高优先级在前）

3. 对每个场景：
   a. 计算该场景可使用的最大资源
      scene_max_qpm = min(scene.config.max_qpm, available_qpm)
      scene_max_tpm = min(scene.config.max_tpm, available_tpm)
   
   b. 计算该场景当前已使用资源
      scene_used_qpm = current_load[scene].qpm
      scene_used_tpm = current_load[scene].tpm
   
   c. 计算该场景剩余可用资源
      scene_available_qpm = scene_max_qpm - scene_used_qpm
      scene_available_tpm = scene_max_tpm - scene_used_tpm
   
   d. 处理该场景的待处理请求：
      按队列顺序处理，直到场景资源用尽或队列空
      每处理一个请求，更新available_qpm和available_tpm
```

### 3.3 队列调度算法

```
队列排序键：(-priority, enqueue_time)
- 先按优先级降序
- 同优先级按入队时间升序

消费策略：
1. 从队列头部取出请求
2. 检查资源是否充足
3. 充足则处理，不足则重新入队（或等待）
```

## 4. 分阶段实现计划

### 阶段一：基础架构搭建与资源监控模块实现

**目标**：搭建项目基础架构，实现资源监控功能

**任务**：

* [ ] 初始化项目结构（Python/Go，选择Python）

* [ ] 定义核心数据模型（场景、请求、负载）

* [ ] 实现资源监控模块

  * 滑动窗口计数器

  * QPM/TPM统计

  * 场景级资源使用统计

* [ ] 实现Mock LLM资源池

* [ ] 编写单元测试

**输出**：

* 可运行的基础项目结构

* 资源监控模块

* Mock LLM服务

### 阶段二：资源充足场景下的分配机制实现

**目标**：实现资源充足时各场景充分利用资源

**任务**：

* [ ] 实现场景配置模块

* [ ] 实现基础调度引擎

* [ ] 实现资源充足场景的分配逻辑

* [ ] 实现请求处理流程

* [ ] 集成测试

**输出**：

* 场景配置管理

* 资源充足时的调度功能

### 阶段三：资源竞争场景下的优先级分配算法实现

**目标**：实现资源竞争时基于优先级的资源分配

**任务**：

* [ ] 实现动态分配算法

* [ ] 实现优先级资源分配逻辑

* [ ] 实现资源配额动态调整

* [ ] 集成测试

**输出**：

* 优先级资源分配算法

* 资源竞争场景处理

### 阶段四：请求队列管理与超卖机制实现

**目标**：实现请求队列和超卖机制

**任务**：

* [ ] 实现请求队列数据结构

* [ ] 实现队列排序和消费逻辑

* [ ] 实现超卖机制配置

* [ ] 实现队列状态查询接口

* [ ] 集成测试

**输出**：

* 请求队列管理

* 超卖机制

### 阶段五：系统集成测试与性能优化

**目标**：完整系统测试与性能优化

**任务**：

* [ ] 完整系统集成测试

* [ ] 性能测试（不同负载场景）

* [ ] 边界测试（资源极限）

* [ ] 性能优化

* [ ] 文档完善

**输出**：

* 完整可运行的系统

* 测试报告

* 性能优化结果

## 5. 接口设计

### 5.1 资源分配核心接口

#### 提交请求接口

```
POST /api/v1/requests
Request:
{
  "scene_id": "string",
  "prompt": "string",
  "max_output_token": int
}

Response:
{
  "request_id": "string",
  "status": "pending|processing|completed|failed",
  "queue_position": int,
  "estimated_wait_time_ms": int
}
```

#### 查询请求状态接口

```
GET /api/v1/requests/{request_id}

Response:
{
  "request_id": "string",
  "scene_id": "string",
  "status": "pending|processing|completed|failed",
  "queue_position": int,
  "enqueue_time": "timestamp",
  "start_time": "timestamp",
  "end_time": "timestamp",
  "token_consumption": int
}
```

### 5.2 场景配置管理接口

#### 创建/更新场景配置

```
PUT /api/v1/scenes/{scene_id}
Request:
{
  "scene_id": "string",
  "priority": int,  // 1-10, 10最高
  "max_qpm": int,
  "max_tpm": int
}

Response:
{
  "success": true,
  "scene": {...}
}
```

#### 获取场景配置

```
GET /api/v1/scenes/{scene_id}

Response:
{
  "scene_id": "string",
  "priority": int,
  "max_qpm": int,
  "max_tpm": int,
  "current_qpm": int,
  "current_tpm": int
}
```

#### 获取所有场景配置

```
GET /api/v1/scenes

Response:
{
  "scenes": [...]
}
```

### 5.3 系统状态接口

#### 获取系统资源状态

```
GET /api/v1/system/status

Response:
{
  "total_qpm_limit": int,
  "total_tpm_limit": int,
  "current_total_qpm": int,
  "current_total_tpm": int,
  "queue_length": int,
  "scenes": [...]
}
```

#### 获取队列状态

```
GET /api/v1/queue

Response:
{
  "length": int,
  "requests": [
    {
      "request_id": "string",
      "scene_id": "string",
      "priority": int,
      "enqueue_time": "timestamp",
      "estimated_token_consumption": int
    }
  ]
}
```

## 6. 测试策略

### 6.1 单元测试

* 资源监控模块：滑动窗口计数准确性

* 调度引擎：资源分配算法正确性

* 队列管理：排序和消费逻辑

* Token计算：prompt和max\_output\_token计算

### 6.2 集成测试

* 完整请求流程：提交 → 排队 → 处理 → 完成

* 多场景并发：不同优先级场景同时请求

* 配置热更新：运行时更新场景配置

### 6.3 性能测试

* 高负载场景：1000+ QPS

* 长时间运行：24小时稳定性测试

* 资源利用率：接近100%时的表现

### 6.4 边界测试

* 资源耗尽：所有场景同时达到最大限制

* 优先级反转：低优先级请求长时间等待

* 超卖场景：各场景请求总和超过整体资源

## 7. 系统部署与监控

### 7.1 部署架构

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer                         │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐    ┌─────────────────────┐
│  Scheduler Instance 1│    │  Scheduler Instance 2│
│  - 调度引擎           │    │  - 调度引擎           │
│  - 资源监控           │    │  - 资源监控           │
│  - 队列管理           │    │  - 队列管理           │
└─────────────────────┘    └─────────────────────┘
          │                               │
          └───────────────┬───────────────┘
                          ▼
              ┌─────────────────────┐
              │     Redis (共享)      │
              │  - 队列存储           │
              │  - 状态同步           │
              └─────────────────────┘
                          │
                          ▼
              ┌─────────────────────┐
              │   Mock LLM Pool      │
              └─────────────────────┘
```

### 7.2 关键指标监控

* 系统级：总QPM、总TPM、队列长度、平均等待时间

* 场景级：各场景QPM、TPM、请求成功率

* 业务级：请求处理时长、Token消耗统计

### 7.3 告警机制

* 队列长度超过阈值

* 平均等待时间超过阈值

* 资源利用率超过90%

* 场景资源长时间超限

## 8. 预期成果与验收标准

### 验收标准

1. ✅ Mock LLM资源池能够模拟线上接入及资源调度
2. ✅ 系统能够准确监控LLM资源使用情况（误差<5%）
3. ✅ 资源分配符合优先级策略：

   * 高优先级场景优先获得资源

   * 低优先级场景在资源充足时可使用
4. ✅ 资源利用率最大化：资源充足时利用率>90%
5. ✅ 请求排队机制按预期顺序处理：

   * 高优先级先处理

   * 同优先级先来先服务
6. ✅ 系统能够稳定处理超卖场景，保证服务可用性
7. ✅ 系统稳定运行24小时无故障

## 技术栈选择

* **编程语言**: Python 3.11+

* **Web框架**: FastAPI

* **队列存储**: Redis

* **Token计算**: tiktoken

* **监控**: Prometheus + Grafana

* **测试**: pytest

* **异步处理**: asyncio

## 项目结构

```
LLM-Resource-Scheduler/
├── src/
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── models.py          # 数据模型
│   │   ├── monitor.py         # 资源监控模块
│   │   ├── scheduler.py       # 调度引擎
│   │   ├── queue.py           # 请求队列
│   │   ├── config.py          # 场景配置
│   │   └── llm_pool.py        # Mock LLM池
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py          # API路由
│   │   └── schemas.py         # API schemas
│   └── main.py                 # 应用入口
├── tests/
│   ├── unit/
│   ├── integration/
│   └── performance/
├── config/
│   └── settings.py
├── docs/
├── README.md
└── requirements.txt
```


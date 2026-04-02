# LLM Resource Scheduler

## 项目简介

LLM Resource Scheduler 是一个用于管理大语言模型资源的多场景动态分配系统。它通过智能调度算法，在资源充足时让各场景充分利用资源，在资源竞争时基于优先级进行分配，同时支持超卖机制和请求排队管理，以最大化资源利用率。

### 核心功能

- **资源监控**: 实时跟踪 QPM（每分钟查询次数）和 TPM（每分钟令牌数）
- **动态调度**: 资源充足时充分利用，资源竞争时按优先级分配
- **场景配置**: 支持多场景配置，独立设置优先级和最大资源限制
- **请求队列**: 基于优先级和时间的队列管理，保证高优先级场景优先处理
- **超卖机制**: 各场景最大资源限制总和可超过整体资源，动态调度
- **队头阻塞修复**: 支持跳过不可处理的请求，继续处理队列中后续的可处理请求

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行示例

项目包含了完整的示例脚本，演示了系统的核心功能：

#### 1. 完整 Mock 调度演示（推荐）
```bash
python examples/mock_scheduler_demo.py
```
这个脚本展示了完整的调度流程：
- 基于 MockLLMPool 的资源调度
- 多优先级场景调度（VIP、标准、批量）
- 实时系统状态监控
- 完整的调度结果统计

#### 2. 基础使用示例
```bash
python examples/basic_usage.py
```
这将运行一个基础演示，展示：
- 初始化 ResourceMonitor 和 MockLLMPool
- 创建场景配置
- Token 消耗计算
- 请求处理
- 资源监控数据展示

#### 3. 资源竞争演示
```bash
python examples/resource_competition.py
```
展示资源竞争和超卖场景下的调度效果。

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行测试并查看覆盖率
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### 项目结构

```
LLM-Resource-Scheduler/
├── src/
│   ├── scheduler/        # 调度引擎核心模块
│   │   ├── __init__.py
│   │   ├── models.py     # 数据模型定义
│   │   ├── monitor.py    # 资源监控模块
│   │   ├── llm_pool.py   # Mock LLM 池
│   │   ├── config.py     # 场景配置管理
│   │   └── scheduler.py  # 调度器（已完成）
│   ├── api/              # API 接口模块
│   │   ├── __init__.py
│   │   └── schemas.py    # API 数据模型
│   └── main.py           # 应用入口
├── examples/             # 示例脚本
│   ├── mock_scheduler_demo.py  # 完整 Mock 调度演示
│   ├── basic_usage.py    # 基础使用示例
│   ├── demo_basic.py     # 基础功能演示
│   ├── resource_competition.py  # 资源竞争演示
│   └── README.md         # 示例说明
├── tests/
│   ├── unit/             # 单元测试
│   │   ├── test_scheduler.py      # 调度器测试
│   │   ├── test_scheduler_phase2.py # 阶段二测试
│   │   ├── test_scheduler_coverage.py # 调度器覆盖率测试
│   │   ├── test_config.py          # 配置模块测试
│   │   ├── test_config_coverage.py # 配置模块覆盖率测试
│   │   ├── test_request_processing.py # 请求处理测试
│   │   ├── test_monitor.py         # 监控模块测试
│   │   ├── test_llm_pool.py        # LLM 池测试
│   │   ├── test_models.py          # 数据模型测试
│   │   └── test_api_schemas.py     # API 数据模型测试
│   ├── integration/      # 集成测试
│   │   ├── __init__.py
│   │   ├── test_integration.py     # 集成测试
│   │   └── test_api_integration.py # API 集成测试
│   └── conftest.py       # 测试配置
├── config/               # 配置文件
│   └── settings.py       # 系统设置
├── .trae/                # 项目规格和文档
│   ├── documents/        # 设计文档
│   └── specs/            # 实现规格
├── requirements.txt      # 依赖包
├── fix_escape.py         # 修复工具脚本
├── verify_acceptance_criteria.py # 验收标准验证脚本
└── README.md
```

## 技术栈

- **Web 框架**: FastAPI
- **Token 计算**: tiktoken
- **数据验证**: Pydantic
- **测试框架**: pytest
- **异步处理**: asyncio

## 核心模块

### 1. 数据模型 (src/scheduler/models.py)

定义了系统核心数据结构：
- `Scene`: 场景配置（优先级、最大 QPM/TPM）
- `Request`: 请求数据
- `LoadMetrics`: 负载指标
- `calculate_token_consumption()`: Token 消耗计算函数

### 2. 资源监控 (src/scheduler/monitor.py)

实现了资源监控功能：
- `SlidingWindowCounter`: 滑动窗口计数器
- `ResourceMonitor`: 资源监控器，支持总负载和场景级负载统计

### 3. Mock LLM 池 (src/scheduler/llm_pool.py)

模拟 LLM 服务，用于测试：
- `MockLLMPool`: 模拟 LLM 请求处理
- 支持配置延迟范围
- 自动更新资源监控

### 4. 场景配置管理 (src/scheduler/config.py)

场景配置管理模块，支持配置热更新：
- 场景配置的创建、更新、删除和查询
- 配置参数的合法性验证
- 配置热更新支持，无需重启服务
- 线程安全的配置操作

### 5. 调度器 (src/scheduler/scheduler.py)

核心调度引擎，已完成开发：
- 基于优先级和时间的请求队列管理
- 资源可用性检查（总资源和场景资源）
- 异步请求处理
- 队头阻塞修复（支持跳过不可处理的请求）
- 系统状态监控
- 资源充足场景下的直接处理

## 开发阶段

### 阶段一（已完成）✅
- 项目结构初始化
- 核心数据模型实现
- 资源监控模块实现
- Mock LLM 资源池实现
- 调度器实现（含优先级排序和队头阻塞修复）
- 完整的单元测试和集成测试
- 示例脚本和演示

### 阶段二（已完成）✅
- 场景配置模块完善（支持热更新）
- 调度引擎优化（资源充足场景分配逻辑）
- 请求处理流程完善（状态跟踪和Token消耗统计）
- 完整的单元测试和集成测试
- 系统问题修复和优化

## 修复记录

### scheduler.py 修复
1. **优先级排序问题**: 添加 `request_id` 作为第三排序键，避免 Request 对象比较错误
2. **队头阻塞问题**: 遍历整个队列寻找可处理的请求，而非只检查队头

### 其他文件修复
1. **requirements.txt**: 修复 HTML 转义字符问题（`&gt;=` → `>=`）
2. **resource_competition.py**: 修复 HTML 转义字符问题
3. **添加 mock_scheduler_demo.py**: 完整的 Mock 调度演示脚本

## 更多信息

- [示例脚本说明](./examples/README.md)
- [设计文档](./.trae/documents/llm-resource-scheduler-plan.md)

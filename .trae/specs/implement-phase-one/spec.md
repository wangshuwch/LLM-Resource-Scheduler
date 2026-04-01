# LLM资源调度器 - 阶段一实现规格说明

## Why
需要搭建LLM多场景资源动态分配系统的基础架构，实现核心的资源监控模块和Mock LLM资源池，为后续功能奠定基础。

## What Changes
- 初始化Python项目结构
- 定义核心数据模型（场景、请求、负载、Token计算）
- 实现资源监控模块（滑动窗口计数器、QPM/TPM统计）
- 实现Mock LLM资源池
- 编写单元测试

## Impact
- 受影响的规格：无（初始实现）
- 受影响的代码：所有核心模块

## ADDED Requirements

### Requirement: 项目初始化
系统应提供标准的Python项目结构，包含必要的依赖配置和构建工具。

#### Scenario: 项目结构创建
- **WHEN** 系统初始化完成
- **THEN** 应包含 src/、tests/、config/ 等标准目录
- **THEN** 应包含 requirements.txt 依赖文件

### Requirement: 核心数据模型
系统应定义完整的数据模型，包括场景配置、请求、负载统计等。

#### Scenario: 数据模型定义
- **WHEN** 数据模型模块加载
- **THEN** 应包含 Scene、Request、LoadMetrics 等数据类
- **THEN** 应支持Token消耗量计算：len(tiktoken(prompt)) + max_output_token

### Requirement: 资源监控模块
系统应实现资源监控功能，包括滑动窗口计数器、QPM/TPM统计。

#### Scenario: QPM统计
- **WHEN** 请求被处理
- **THEN** 系统应记录该请求并更新QPM（每分钟查询次数）
- **THEN** 应支持按场景维度统计QPM

#### Scenario: TPM统计
- **WHEN** 请求被处理
- **THEN** 系统应计算Token消耗并更新TPM（每分钟令牌数）
- **THEN** 应支持按场景维度统计TPM

#### Scenario: 滑动窗口
- **WHEN** 时间流逝
- **THEN** 系统应自动清理过期的统计数据
- **THEN** 只保留最近一分钟的数据用于计算

### Requirement: Mock LLM资源池
系统应提供Mock LLM服务，用于模拟真实LLM的响应和资源消耗。

#### Scenario: Mock LLM响应
- **WHEN** 请求提交到Mock LLM
- **THEN** 应返回模拟的响应
- **THEN** 应模拟处理延迟

#### Scenario: 资源消耗记录
- **WHEN** Mock LLM处理请求
- **THEN** 应记录实际的资源消耗
- **THEN** 应更新监控模块的统计数据

### Requirement: 单元测试
系统应包含完整的单元测试覆盖核心模块。

#### Scenario: 测试执行
- **WHEN** 运行pytest
- **THEN** 所有单元测试应通过
- **THEN** 测试覆盖率应达到80%以上

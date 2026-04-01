# Tasks

- [x] Task 1: 初始化项目结构
  - [x] 创建标准Python项目目录结构（src/、tests/、config/、docs/）
  - [x] 创建 requirements.txt 并添加必要依赖（fastapi、uvicorn、tiktoken、pytest、pydantic等）
  - [x] 创建 README.md 项目说明文档
  - [x] 创建 .gitignore 文件

- [x] Task 2: 实现核心数据模型
  - [x] 在 src/scheduler/models.py 中定义数据类
    - [x] Scene：场景配置（scene_id、priority、max_qpm、max_tpm）
    - [x] Request：请求（scene_id、prompt、max_output_token、request_id）
    - [x] LoadMetrics：负载指标（qpm、tpm）
    - [x] RequestStatus：请求状态枚举
  - [x] 实现 Token 计算函数：calculate_token_consumption(request)
  - [x] 为数据模型编写单元测试

- [x] Task 3: 实现资源监控模块
  - [x] 在 src/scheduler/monitor.py 中实现滑动窗口计数器
    - [x] SlidingWindowCounter 类，支持时间窗口管理
    - [x] 自动清理过期数据
  - [x] 实现 ResourceMonitor 类
    - [x] 总QPM/TPM统计
    - [x] 按场景QPM/TPM统计
    - [x] record_request() 方法记录请求
    - [x] get_current_load() 方法获取当前负载
  - [x] 为资源监控模块编写单元测试

- [x] Task 4: 实现 Mock LLM 资源池
  - [x] 在 src/scheduler/llm_pool.py 中实现 MockLLMPool 类
    - [x] 模拟LLM请求处理
    - [x] 模拟响应延迟（可配置）
    - [x] 与资源监控模块集成，更新负载统计
  - [x] 实现 async 处理支持
  - [x] 为 Mock LLM 编写单元测试

- [x] Task 5: 编写配置和主入口
  - [x] 创建 config/settings.py 配置文件
  - [x] 创建 src/main.py 作为应用入口（预留 FastAPI 结构）
  - [x] 创建基础的 API schema（src/api/schemas.py）

- [x] Task 6: 集成测试和验证
  - [x] 编写集成测试，验证模块间协作
  - [x] 运行完整测试套件，确保所有测试通过
  - [x] 验证测试覆盖率达到80%以上

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 5

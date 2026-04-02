# Tasks - 代码质量改进和问题修复

## 高优先级任务

- [x] Task 1: 提升测试覆盖率至80%
  - [x] 为src/api/schemas.py编写单元测试
  - [x] 为src/main.py编写API集成测试
  - [x] 验证测试覆盖率达到80%以上
  - [x] 运行pytest --cov验证覆盖率

- [x] Task 2: 添加完整的类型注解
  - [x] 为src/scheduler/scheduler.py添加类型注解
    - [x] 为__init__方法参数添加类型注解
    - [x] 为所有方法参数添加类型注解
    - [x] 为所有方法返回值添加类型注解
    - [x] 为实例变量添加类型注解
  - [x] 为src/scheduler/config.py添加类型注解
  - [x] 为src/scheduler/llm_pool.py添加类型注解
  - [x] 为src/scheduler/monitor.py添加类型注解
  - [x] 为src/api/schemas.py添加类型注解
  - [x] 为src/main.py添加类型注解
  - [x] 为models.py的calculate_token_consumption添加返回值类型注解
  - [x] 运行mypy验证类型正确性

- [x] Task 3: 添加文档字符串
  - [x] 为src/scheduler/scheduler.py添加文档字符串
    - [x] 添加模块级文档字符串
    - [x] 为Scheduler类添加文档字符串
    - [x] 为所有公共方法添加文档字符串
  - [x] 为src/scheduler/config.py添加文档字符串
    - [x] 添加模块级文档字符串
    - [x] 为SceneConfigManager类添加文档字符串
    - [x] 为所有公共方法添加文档字符串
  - [x] 为src/scheduler/llm_pool.py添加文档字符串
    - [x] 添加模块级文档字符串
    - [x] 为MockLLMPool类添加文档字符串
    - [x] 为所有公共方法添加文档字符串
  - [x] 为src/scheduler/monitor.py添加文档字符串
    - [x] 添加模块级文档字符串
    - [x] 为SlidingWindowCounter类添加文档字符串
    - [x] 为ResourceMonitor类添加文档字符串
    - [x] 为所有公共方法添加文档字符串
  - [x] 为src/api/schemas.py添加文档字符串
  - [x] 为src/main.py添加文档字符串

## 中优先级任务

- [ ] Task 4: 改进异常处理
  - [ ] 改进src/scheduler/scheduler.py的异常处理
    - [ ] 将except Exception改为捕获特定异常
    - [ ] 为不同类型的异常提供详细的错误信息
    - [ ] 在异常处理中添加详细的日志记录
  - [ ] 改进src/main.py的异常处理
    - [ ] 将except Exception改为捕获特定异常
    - [ ] 为HTTP异常提供详细的错误响应
  - [ ] 改进src/scheduler/config.py的异常处理
    - [ ] 在观察者模式中记录异常日志
    - [ ] 为配置验证失败提供详细的错误信息

- [ ] Task 5: 完善日志记录
  - [ ] 为src/scheduler/config.py添加日志记录
    - [ ] 添加场景配置变更日志
    - [ ] 添加配置验证失败日志
    - [ ] 添加观察者通知日志
  - [ ] 为src/scheduler/llm_pool.py添加日志记录
    - [ ] 添加请求处理开始和完成日志
    - [ ] 添加延迟设置变更日志
  - [ ] 为src/scheduler/monitor.py添加日志记录
    - [ ] 添加资源监控数据记录日志
    - [ ] 添加场景计数器清理日志
  - [ ] 改进src/scheduler/scheduler.py的日志记录
    - [ ] 添加更详细的请求处理日志
    - [ ] 添加Token消耗和处理时间信息
    - [ ] 添加资源使用情况信息

- [ ] Task 6: 修复代码格式问题
  - [ ] 清理未使用的导入
    - [ ] 清理src/main.py中未使用的asyncio导入
    - [ ] 清理src/scheduler/monitor.py中未使用的datetime导入
    - [ ] 清理src/scheduler/scheduler.py中未使用的导入
  - [ ] 修复空白行问题
    - [ ] 移除空白行中的尾随空格
    - [ ] 修复文件末尾空白行
    - [ ] 添加函数定义前的空白行
  - [ ] 移动导入语句到文件顶部
    - [ ] 将src/main.py中函数内的import logging移到文件顶部

## 低优先级任务

- [x] Task 7: 补充缺失的依赖
  - [x] 在requirements.txt中添加pydantic-settings>=2.0.0
  - [x] 验证所有依赖都已声明

- [x] Task 8: 添加预估等待时间功能
  - [x] 在SubmitResponse中添加estimated_wait_time_ms字段
  - [x] 实现等待时间预估逻辑
  - [x] 更新API返回该字段

- [ ] Task 9: 代码重构(可选)
  - [ ] 将队列逻辑从scheduler.py提取到独立的queue.py
  - [ ] 将API路由从main.py提取到独立的routes.py
  - [ ] 创建tests/performance/目录

## 验证任务

- [ ] Task 10: 运行完整测试套件
  - [ ] 运行所有单元测试
  - [ ] 运行所有集成测试
  - [ ] 验证测试覆盖率≥80%

- [ ] Task 11: 代码质量检查
  - [ ] 运行flake8检查代码格式
  - [ ] 运行mypy检查类型注解
  - [ ] 验证无严重错误

- [ ] Task 12: 功能验证
  - [ ] 运行演示脚本验证功能正常
  - [ ] 验证所有API接口正常工作
  - [ ] 验证资源监控准确性

## Task Dependencies

- Task 2 depends on Task 1 (类型注解有助于测试编写)
- Task 3 depends on Task 2 (文档字符串在类型注解后添加更合适)
- Task 4 depends on Task 3 (异常处理改进需要完整的文档)
- Task 5 depends on Task 4 (日志记录需要配合异常处理)
- Task 6 depends on Task 5 (代码格式修复在其他改进后进行)
- Task 7 can run in parallel
- Task 8 can run in parallel
- Task 9 can run in parallel
- Task 10 depends on Task 1, Task 2, Task 3, Task 4, Task 5, Task 6
- Task 11 depends on Task 10
- Task 12 depends on Task 11

"""机载软件 AI 中台 API 路由集合。

各路由模块按功能域拆分：
- common: 健康检查等基础接口
- task_ws: 任务 WebSocket 推送
- pipeline: 生成、SCADE 上传、修复、契约校验、仿真
- reports: DO-178C 合规报告
- composition: 组件组合验证
- hil: 人机协作审批
- models: 模型选择与 MISRA 规则检索
- generate: Agent 流式推送
"""

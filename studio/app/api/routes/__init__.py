"""机载软件 AI 中台 API 路由集合。

各路由模块按功能域拆分：
- common: 健康检查等基础接口
- task_ws: 任务 WebSocket 推送
- pipeline: 生成、SCADE 上传、修复、契约校验、仿真
- reports: DO-178C 合规报告
- composition: 组件组合验证
- hitl: HITL（Human-in-the-Loop）人工审查
  注意：与 HIL（Hardware-in-the-Loop 硬件在环，digital_twin/）无关；
  URL 路径 /api/hil/* 仍保留以兼容旧调用方
- models: 模型选择与 MISRA 规则检索
- generate: Agent 流式推送
"""

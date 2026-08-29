"""mini_agent：一个从零手写的极简 Agent 框架（面试向教学代码）。

模块划分（每个文件对应一类面试题）：
    tools.py  工具注册 + 从函数签名自动生成 JSON Schema（function calling 协议）
    llm.py    统一 LLM 客户端（OpenAI 兼容协议，可切换任意服务商）
    memory.py 上下文管理（MessageBuffer，字符预算窗口截断）
    agent.py  Agent 主循环（ReAct：模型生成 -> 解析工具调用 -> 执行 -> 回填 -> 循环）
"""
from mini_agent.agent import Agent
from mini_agent.tools import Tool, ToolRegistry
from mini_agent.llm import ChatClient, LLMError
from mini_agent.memory import MessageBuffer

__all__ = ["Agent", "Tool", "ToolRegistry", "ChatClient", "LLMError", "MessageBuffer"]
# AI Prompt 与问题解决记录

## 项目概述

用 AI 辅助从零实现最小可用 Agent，不依赖 LangChain / OpenHands 等框架，核心 Runtime 完全手写。

---

## 一、设计阶段

### Prompt: 需求分析

> "从零实现一个最小可用 Agent，支持多轮对话、session 维护、工具调用循环，至少 3 个工具，最大步数限制，基本异常处理，工具调用 trace，跨轮次继续执行。你先说一下思路。"

**AI 给出的方案：**

- Agent 核心循环采用 ReAct 模式（Reasoning + Acting）
- 用 OpenAPI/DeepSeek 的 Function Calling 来实现工具调用
- Tool 基类 + ToolRegistry 管理工具
- Session 管理对话历史
- Todo 工具作为跨轮次状态的载体

**设计决策：** 确定五层架构：`main → Session → AgentLoop → LLMClient / ToolRegistry → Tools`

### Prompt: 框架 vs 手写对比

> "不用 LangChain 是不是就要这样写？base.py 啥意思？工具写法有区别不？api 请求格式也要自己定义？模型返回的消息有没有框架都一样？"

**学到的东西：**

- **不用框架**：需要自己写 Tool 基类、自己管理注册表、自己生成 JSON Schema、自己处理 Function Calling 响应
- **用 LangChain**：`@tool` 装饰器自动生成 schema，`AgentExecutor` 封装整个循环，工具结果自动序列化
- **模型返回的格式**：不管用不用框架都一样（都是 OpenAI 格式的 `choices[0].message.tool_calls`），但框架帮你自动解析了
- **最大的区别**：框架替你写了 AgentLoop，手写需要自己实现整个循环逻辑

---

## 二、实现阶段

### 问题 1: Git Push 443 错误

**现象：**
```
fatal: unable to access 'https://github.com/haoyundd/minagent.git/':
Failed to connect to github.com port 443 after 21205 ms: Could not connect to server
```

**根因：** 代理（梯子）影响了 Git 的网络连接。

**解决：**
```bash
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
git -c http.sslVerify=false push origin master
```

**教训：** 国内开发环境代理配置是常见坑，需要根据实际情况开关。

### 问题 2: Calculator 工具的安全限制

**Prompt:**
> "eval 会不会有安全问题？怎么限制？"

**方案：** 使用 `eval(expression, {"__builtins__": {}}, {})` 限制命名空间，切断对 `__import__`、`open` 等危险函数的访问。

**后面的简化：** 用户觉得太复杂，简化成只支持加减乘除 + 括号的 `eval`。

### 问题 3: Search Mock 匹配失败（核心问题）

**现象：**
```
LLM 搜 "北京3天旅游攻略 必去景点 2024 2025"  → "未找到相关结果"
LLM 搜 "北京3天行程安排 故宫 长城"           → "未找到相关结果"
```

LLM 连续 4 步搜索全部返回空，浪费大量 token 和步数。

**根因：** LLM 生成的搜索词会自己添加修饰词、年份、长尾关键词（如"北京3天旅游攻略 必去景点 2024"），不可能恰好命中 Mock 数据的固定精确 key（"北京攻略"）。

**改前：**
```python
"北京攻略": "北京3天游经典路线..."

# 匹配逻辑：精确匹配
if key in query_lower or query_lower in key:
    return content
```

**改后：**
```python
("北京攻略", "北京旅游", "北京3天", "北京行程", "旅游攻略"): "北京3天游经典路线..."

# 匹配逻辑：多关键词子串命中
for keywords, content in MOCK_RESULTS.items():
    for kw in keywords:
        if kw in query_lower:  # "旅游攻略" in "北京3天旅游攻略..." → True
            return content
```

**教训：** LLM 的搜索行为不可控，检索策略必须有模糊性。真实系统会引入 embedding 向量检索来解决这个问题。

### 问题 4: LLM 不主动调 Todo 工具

**现象：** LLM 搜到北京攻略后直接在文字里输出旅行计划，不调用 `todo.create` 创建任务。

**根因：** 系统提示词没有明确要求 LLM 使用 todo 工具来组织任务。

**解决：** 在 System Prompt 中加入：
```
规划任务时，请使用 todo 工具创建和跟踪任务。
需要搜索信息时，请使用 search 工具。
需要计算时，请使用 calculator 工具。
```

**教训：** Prompt Engineering 直接影响 Agent 的行为模式，需要明确告诉 LLM 在什么场景用什么工具。

---

## 三、设计决策

### 跨轮次状态存哪里？

| 方案 | 优点 | 缺点 |
|:--|:--|:--|
| Session.messages | 简单，LLM 直接可读 | 只存文本，无法精确查询状态 |
| TodoTool.tasks | 结构化数据，精确 CRUD | 需要 LLM 主动调用 `todo.list()` |
| 外部数据库 | 持久化，可扩展 | 过度设计 |

**选择：TodoTool.tasks** —— 最小可用方案，任务状态存在工具实例属性中，进程内全局共享，满足跨轮次需求。

### 为什么不用向量检索做 Memory？

当前场景对话量少（< 20 轮），DeepSeek 上下文窗口（128K tokens）足够承载全部历史。引入向量检索会增加复杂度，对 Demo 没有实际收益。面试时可以说清楚"什么场景下会升级"。

---

## 四、关键 Prompt 记录

| 提问 | 目的 |
|:--|:--|
| "base.py 什么意思？不用框架怎么注册工具？" | 理解 Tool 抽象基类 + Registry 模式 |
| "工具函数的 description 字段是不是用了框架就不用写？" | 理解框架的 `@tool` 装饰器原理 |
| "模型返回的 finish_reason 是什么？" | 理解 Function Calling 协议 |
| "框架是怎么管理上下文内容的？自己写怎么做？" | 理解 Session.messages 本质 |
| "企业级上下文工程怎么做？" | 了解 RAG、摘要压缩、结构化记忆等进阶方案 |
| "跨轮次继续执行和同一次会话有什么区别？" | 理解状态持久化 vs 对话历史的差异 |
| "eval 的安全限制怎么做的？" | 理解沙箱执行原理 |

---

## 五、项目时间线

| 阶段 | 内容 | 耗时估计 |
|:--|:--|:--|
| 1 | 需求分析 + 架构设计 | 对接思路 |
| 2 | 搭建项目框架 + `.env` + `config.py` | 基础搭建 |
| 3 | `tools/base.py` + `ToolRegistry` | 工具基类 |
| 4 | `agent/llm_client.py` | LLM 客户端 |
| 5 | `tool/calculator.py` | 计算器工具 |
| 6 | `tool/search.py` | Mock 搜索 |
| 7 | `tool/todo.py` | 任务管理 + 跨轮次状态 |
| 8 | `agent/loop.py` + `agent/session.py` | 核心循环 + 会话管理 |
| 9 | `trace_logger.py` + `main.py` | 日志 + 入口 |
| 10 | 调试 + 搜索匹配修复 + Prompt 优化 | 问题修复 |
| 11 | README + 文档 | 面试交付 |
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

> "LangChain 的 BaseTool 背后本质上做了什么事？不用框架的话，Tool 的注册、schema 生成、参数校验、结果序列化这些环节分别要自己实现哪些？Function Calling 协议层框架替我们屏蔽了什么？"

**对比结论：**

| 环节 | 手写 | LangChain |
|:--|:--|:--|
| Tool 定义 | 继承 Tool 基类，手动写 name/description/parameters | `@tool` 装饰器，从函数签名 + docstring 自动提取 |
| Schema 生成 | 手动构造 `{"type":"object", "properties":{...}}` | `StructuredTool.from_function()` 自动生成 |
| 注册管理 | 自己写 `ToolRegistry` 类 | `Tool.list()` 全局注册 |
| 循环控制 | 自己写 `AgentLoop.run()` | `AgentExecutor.invoke()` |
| 异常处理 | 手动三层 try/except | 框架内置 `handle_parsing_errors` |

**设计决策：** 手写不是"不会用框架"，而是为了理解 Agent 的底层机制——每一层该做什么、数据怎么流转、异常在哪里兜底。理解了这些再去用框架，才能知道框架替你做了什么、边界在哪里。

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

**第一版方案：** 使用 Python 内置求值能力，并限制命名空间，切断对危险函数的访问。

**第二版修正：** 面试反馈后重新审视工具治理，改成 AST 白名单计算，只允许数字、括号、加减乘除和正负号。

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
| 工具实例属性 | 结构化数据，精确 CRUD | 多 session 时容易串状态 |
| 外部数据库 | 持久化，可扩展 | 过度设计 |

**第一版选择：工具实例属性。** 当时满足单 session demo，但会导致多个窗口共享任务状态。

**第二版修正：Session.state。** todo 数据进入当前 session 的私有结构化 state，窗口 1 和窗口 2 互不影响。

### 为什么不用向量检索做 Memory？

当前场景对话量少（< 20 轮），DeepSeek 上下文窗口（128K tokens）足够承载全部历史。引入向量检索会增加复杂度，对 Demo 没有实际收益。面试时可以说清楚"什么场景下会升级"。

---

## 四、关键 Prompt 记录

| 提问 | 目的 |
|:--|:--|
| "ReAct 循环中，LLM 的 finish_reason 和 tool_calls 的时序关系是怎样的？一次请求可以返回多个 tool_call，是串行还是并行执行更合理？" | 设计 AgentLoop 的调度策略 |
| "不用框架的情况下，Tool 的 schema 应该遵循什么规范？OpenAI Function Calling 的 JSON Schema 和标准 JSON Schema 有什么差异？" | 确保工具定义与 LLM API 兼容 |
| "Session.messages 的 token 增长是线性的，什么临界点需要引入摘要压缩或滑动窗口？DeepSeek 的 128K 上下文在实际 tool calling 场景下有效利用率大概多少？" | 评估 Memory 策略的升级时机 |
| "跨轮次状态放在 Tool 实例属性里 vs 放在 Session 里 vs 外部存储，在一致性、可恢复性、并发安全性上各有什么 trade-off？" | 设计跨轮次状态方案 |
| "LLM 调用失败的降级策略：重试、降级提示词、fallback 到无工具模式，各自的适用场景是什么？" | 设计异常处理的分级策略 |
| "Function Calling 模式下，tool message 的 role 必须是 'tool' 且必须带 tool_call_id，这个约束是 OpenAI 协议强制的还是 DeepSeek 也遵循？" | 验证 API 兼容性 |
| "如果工具执行耗时较长（如外部 API 调用），同步阻塞式循环会有什么问题？异步化改造的核心改动点在哪？" | 思考架构演进方向 |

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

---

## 六、二次改造：从 ReAct Demo 到 Runtime 治理

### 面试官反馈

> "无工具治理，无 memory 的治理，无 message 的拼接治理，暂时只有 ReAct 实现。"

### 问题复盘

第一版项目已经能跑 ReAct 循环：LLM 判断是否调用工具、工具结果回填、继续 loop 或返回答案。但这只能证明"会调工具"，不能证明 Runtime 有治理能力。

这次用 AI 辅助重新拆解反馈后，明确了三个改造目标：

| 反馈 | 代码层问题 | 改造方向 |
|:--|:--|:--|
| 无工具治理 | `AgentLoop` 直接 `tool.execute(**args)` | 增加 `ToolExecutor`，统一做存在性检查、required 参数校验、异常捕获、结构化返回和 trace |
| 无 memory 治理 | `Session.messages` 全量保存，todo 是工具实例全局状态 | 把 memory 拆成 messages、summary、session.state；todo 进入 session 私有 state |
| 无 message 拼接治理 | 调 LLM 时直接传 `session.messages` | 增加 `ContextBuilder`，按 system、summary、state、最近消息、当前输入拼接 |

### 关键设计决策

1. **工具治理层要独立于具体工具。**
   LLM 输出不是可信输入，因此不能让模型直接驱动任意函数执行。`ToolExecutor` 负责把模型输出转成可控、可观测、可失败恢复的工具调用。

2. **Memory 不是一个 messages 数组。**
   短期对话、长期摘要、结构化业务状态是三类不同 memory。尤其是 todo 这种结构化状态，必须归属到当前 session，否则多窗口会互相污染。

3. **Context 拼接是 Runtime 职责。**
   直接塞全量历史虽然简单，但无法解释哪些信息进入模型、为什么进入、过长时怎么处理。`ContextBuilder` 把拼接顺序固定下来，并配合 summary 做基础压缩。

4. **保持最小实现，不做过度工程。**
   这次不引入数据库、向量库、异步任务系统或复杂 JSON Schema validator。笔试代码重点展示 Runtime 思路，复杂能力放到架构设计题里讨论。

### 新版验证 Prompt

| 提问 | 目的 |
|:--|:--|
| "如何证明工具调用不是 LLM 直接执行函数，而是经过 Runtime 治理？" | 推导 `ToolExecutor` 的职责 |
| "两个聊天窗口都使用 todo 工具，状态应该放在工具实例还是 session？" | 推导 session 私有 state |
| "长对话时哪些信息应该进入 context？顺序是什么？" | 推导 `ContextBuilder` |
| "压缩 memory 一定要调用 LLM 吗？最小实现能不能用规则摘要？" | 控制复杂度，避免过度工程 |

### 新版面试讲法

> 第一版只是 ReAct demo，第二版把它升级成最小 Agent Runtime：ReAct loop 负责调度，ToolExecutor 负责工具治理，Session 负责 memory 分层和隔离，ContextBuilder 负责 message 拼接和压缩，TraceLogger 负责可观测性。这样即使不用框架，也能说清楚 LangChain / OpenHands 这类框架在 Runtime 层帮我们做了什么。

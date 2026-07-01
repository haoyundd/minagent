# MinAgent

一个从零实现的最小可用 Agent Runtime。

本项目不依赖 LangChain、LangGraph、OpenHands、OpenClaw 等 Agent 框架，核心 Runtime 手写实现。重点不是“堆很多工具”，而是展示一个最小 Agent 如何完成：

- ReAct 循环
- 工具注册与工具治理
- 多 session 隔离
- memory 分层治理
- message/context 拼接治理
- trace 可观测性
- 单元测试验证

## 项目定位

面试官对第一版的反馈是：

> 无工具治理，无 memory 的治理，无 message 的拼接治理，暂时只有 ReAct 实现。

因此第二版的目标不是继续加工具，而是把项目从“会调工具的 demo”升级成“最小 Agent Runtime”。

一句话概括：

> LLM 负责判断意图，Runtime 负责治理上下文、工具、状态和执行过程。

## 快速开始

### 环境要求

- Python 3.10+
- DeepSeek API Key

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
MAX_STEPS=10
```

### 启动 CLI

```bash
python main.py
```

交互命令：

| 输入 | 作用 |
|:--|:--|
| 任意问题 | 交给 Agent 处理 |
| `trace` | 查看 LLM、工具调用、context 压缩等执行日志 |
| `/new` | 创建新 session，模拟打开新聊天窗口 |
| `/sessions` | 查看当前进程内的所有 session |
| `/use <session_id>` | 切换到指定 session |
| `exit` | 退出 |

### 运行测试

```bash
python -m unittest discover -s tests
```

当前测试覆盖：

- 工具不存在、参数缺失、工具异常
- calculator 的 AST 白名单计算
- todo 的 session 隔离
- ContextBuilder 的 message 拼接
- context 超长后的 summary 压缩
- AgentLoop 的直接回复、工具调用、最大步数兜底

## 推荐演示流程


```text
python main.py

你: 帮我规划一个3天北京旅游计划，并记成待办
Agent: ...

你: trace
Agent: 展示 llm_request / tool_call / tool_result / final_answer

你: /new
你: 帮我写周报，并记成待办
Agent: ...

你: /sessions
Agent: 展示两个独立 session

你: /use <第一个session_id>
你: 看一下我的待办
Agent: 只看到第一个 session 的 todo，不会看到周报 todo
```

这个流程可以证明：

- LLM 会自主选择工具。
- 工具调用有 trace。
- 多 session 之间 memory 隔离。
- todo 状态属于 session，而不是全局工具实例。

## 系统架构

```text
main.py
  ├─ CLI session 池
  │   ├─ /new
  │   ├─ /sessions
  │   └─ /use <session_id>
  │
  ├─ AgentLoop
  │   ├─ ContextBuilder
  │   ├─ LLMClient
  │   └─ ToolExecutor
  │
  ├─ ToolRegistry
  │   ├─ calculator
  │   ├─ search
  │   └─ todo
  │
  └─ TraceLogger
```

核心数据流：

```text
用户输入
  ↓
ContextBuilder 组装 messages
  ↓
LLM 判断直接回答或 tool_calls
  ↓
ToolExecutor 治理并执行工具
  ↓
工具结果写回 Session
  ↓
必要时压缩旧 messages 到 summary
  ↓
LLM 基于工具结果继续 loop 或返回最终答案
```

## 核心模块

| 模块 | 文件 | 说明 |
|:--|:--|:--|
| LLM 客户端 | `agent/llm_client.py` | 封装 DeepSeek OpenAI-compatible API，支持 Function Calling 和重试 |
| Agent 循环 | `agent/loop.py` | ReAct 调度器，负责 LLM 调用、工具调用回填、最大步数限制 |
| Session | `agent/session.py` | 管理 messages、summary、session 私有 state |
| ContextBuilder | `agent/context.py` | 统一治理 message/context 拼接 |
| ToolRegistry | `tools/base.py` | 注册工具并导出 OpenAI Function Calling schema |
| ToolExecutor | `tools/base.py` | 工具治理层，统一校验、执行、异常处理和 trace |
| TraceLogger | `trace_logger.py` | 记录每一步 Runtime 行为 |

## 工具治理

第一版的问题是：`AgentLoop` 拿到 LLM 返回的工具名和参数后，直接执行工具。

第二版增加 `ToolExecutor`，所有工具调用必须先经过治理层：

- 检查工具是否存在。
- 检查 schema 中的 required、type、enum 参数约束。
- 捕获工具内部异常。
- 识别工具返回值里的业务错误，并统一归一化为 `ok: false`。
- 统一包装工具结果。
- 写入 trace，方便复盘。

统一返回结构：

```json
{
  "ok": true,
  "tool": "calculator",
  "input": { "expression": "2+3*4" },
  "output": { "result": 14, "expression": "2+3*4" },
  "error": ""
}
```

当前工具：

| 工具 | 类型 | 说明 |
|:--|:--|:--|
| `calculator` | safe | 使用 AST 白名单计算加减乘除，不使用 `eval` |
| `search` | mock | Mock 搜索，多关键词子串匹配 |
| `todo` | stateful | 读写当前 session 私有 todo state |

设计原则：

> LLM 输出不是可信输入。LLM 可以提出工具调用意图，但 Runtime 必须决定能不能执行、怎么执行、如何失败恢复。

当前没有引入完整 JSON Schema validator，而是手写最小校验：`required`、`type`、`enum`。这样足够拦住 LLM 常见的参数错误，也避免为了笔试 demo 引入额外复杂度。

## Memory 治理

Memory 被拆成三层：

| 层级 | 放置位置 | 内容 | 召回方式 |
|:--|:--|:--|:--|
| 短期对话 | `Session.messages` | 用户、assistant、tool 的最近消息 | ContextBuilder 放入最近 N 条 |
| 摘要 memory | `Session.state["summary"]` | 被压缩的旧消息摘要 | ContextBuilder 作为 system message 放入 |
| 结构化 state | `Session.state["todos"]` | 当前 session 的 todo 数据 | todo 工具显式读写，ContextBuilder 放入状态摘要 |

多 session 隔离：

- `/new` 创建一个新的 `Session`。
- `/use <session_id>` 可以切回旧 session。
- 每个 session 都有自己的 messages、summary 和 todos。
- todo 不存放在全局 `TodoTool` 实例中，避免窗口之间互相污染。

设计原则：

> Memory 不是一个无限增长的 messages 数组。对话历史、压缩摘要、结构化业务状态应该分开治理。

## Message / Context 拼接治理

第一版直接把完整 `session.messages` 传给 LLM。这样虽然简单，但有两个问题：

- 长对话会越来越大，first token latency 和成本都会上升。
- 无法解释哪些信息应该进 context、为什么进、进多少。

第二版增加 `ContextBuilder`，每轮固定按下面顺序拼接：

1. system prompt
2. session summary
3. session state 摘要
4. 最近 N 条消息
5. 当前用户输入

当历史消息超过阈值时，`Session.compact_if_needed()` 会把旧消息压缩进 `summary`，只保留最近消息。

当前压缩使用规则版摘要，不额外调用 LLM。这样实现足够小，但能展示 Runtime 的关键思想：

> Context 不是历史消息的简单堆叠，而是一次受治理的信息选择。

## ReAct Loop

`AgentLoop` 保留标准 ReAct 思路：

```text
接收用户输入
  → 调 LLM
  → 判断 stop / tool_calls
  → 执行工具
  → 工具结果回填
  → 继续 loop 或返回最终答案
```

但第二版中，`AgentLoop` 不再负责所有细节，而是变成协调器：

- context 拼接交给 `ContextBuilder`
- 工具执行交给 `ToolExecutor`
- memory 状态交给 `Session`
- trace 记录交给 `TraceLogger`

这也是项目的核心思路：

> ReAct 是执行模式，Runtime 治理才是工程能力。

## Trace 可观测性

输入 `trace` 可以查看执行日志。主要事件类型：

- `llm_request`
- `llm_response`
- `tool_call`
- `tool_result`
- `context_compact`
- `final_answer`
- `error`

trace 的意义是让 Agent 不再是黑盒。面试时可以用它解释：

- LLM 为什么调工具。
- 工具拿到了什么参数。
- 工具返回了什么结果。
- context 有没有被压缩。
- 最终答案是在哪一步生成的。

## 设计取舍

本项目故意保持最小实现：

- 不做数据库持久化。
- 不做向量检索 memory。
- 不做异步工具。
- 不做复杂权限系统。
- 不做完整 JSON Schema validator。
- 不引入任何 Agent 框架。

这些能力在真实生产 Agent 中很重要，但对笔试代码来说会稀释重点。本项目优先展示 Runtime 最核心的三个治理能力：

1. 工具治理
2. Memory 治理
3. Message 拼接治理


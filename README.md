# MinAgent

从零实现的最小可用 Agent Runtime，不依赖 LangChain / LangGraph / OpenHands / OpenClaw 等 Agent 框架。项目重点不是堆工具数量，而是展示一个最小 Runtime 如何治理工具、memory 和 message context。

## 运行方式

### 环境要求

- Python 3.10+
- DeepSeek API Key

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 API Key

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
MAX_STEPS=10
```

### 启动

```bash
python main.py
```

交互命令：

| 输入 | 作用 |
|:--|:--|
| 任意问题 | Agent 处理并回答 |
| `trace` | 查看工具调用和上下文治理日志 |
| `/new` | 创建新 session，模拟打开新聊天窗口 |
| `/sessions` | 查看当前进程内的所有 session |
| `/use <session_id>` | 切换到指定 session |
| `exit` | 退出 |

### 测试

```bash
python -m unittest discover -s tests
```

## 系统设计

```text
main.py
  ├─ Session 池：多个窗口/会话隔离
  ├─ AgentLoop：ReAct 调度器
  │   ├─ ContextBuilder：message 拼接治理
  │   ├─ LLMClient：DeepSeek OpenAI-compatible API
  │   └─ ToolExecutor：工具治理
  ├─ ToolRegistry：工具注册和 schema 输出
  └─ TraceLogger：执行日志
```

核心流程：

```text
用户输入
  → ContextBuilder 组装 context
  → LLM 判断直接回答或 tool_calls
  → ToolExecutor 校验并执行工具
  → 工具结果写回 Session
  → 必要时压缩旧 messages 到 summary
  → LLM 基于工具结果继续 loop 或返回最终答案
```

## 工具治理

LLM 输出不直接调用 Python 函数，而是先经过 `ToolExecutor`：

- 检查工具是否存在。
- 按 schema 的 `required` 做最小参数校验。
- 捕获工具异常，避免单个工具拖垮 Runtime。
- 统一返回 `ok/tool/input/output/error` 结构。
- 写入 trace，方便复盘每一步执行。

工具通过 `ToolRegistry` 注册，每个工具包含：

- `name`
- `description`
- `parameters`
- `risk_level`
- `stateful`

当前工具：

| 工具 | 说明 |
|:--|:--|
| `calculator` | 使用 AST 白名单计算加减乘除和括号，不使用 `eval` |
| `search` | Mock 搜索，多关键词子串匹配 |
| `todo` | 读写当前 session 的私有 todo state |

## Memory 的放置方式与召回时机

Memory 被拆成三层：

| 层级 | 放置位置 | 内容 | 召回方式 |
|:--|:--|:--|:--|
| 短期对话 | `Session.messages` | 最近用户、assistant、tool 消息 | ContextBuilder 放入最近 N 条 |
| 摘要 memory | `Session.state["summary"]` | 被压缩的旧消息摘要 | ContextBuilder 以 system message 放入 |
| 结构化 state | `Session.state["todos"]` | 当前 session 的 todo 数据 | todo 工具显式读写，ContextBuilder 放入状态摘要 |

多 session 隔离：

- `/new` 创建新的 `Session`。
- `/use <session_id>` 切换回旧 session。
- 每个 session 拥有自己的 `messages`、`summary` 和 `todos`。
- todo 不再存在工具实例的全局属性里，避免窗口 1 和窗口 2 串数据。

## Message / Context 拼接治理

Runtime 不再无脑把完整 `session.messages` 传给 LLM，而是由 `ContextBuilder` 固定拼接：

1. system prompt
2. session summary
3. session state 摘要
4. 最近 N 条消息
5. 当前用户输入

当历史消息超过阈值时，`Session.compact_if_needed()` 会把旧消息压缩进 `summary`，只保留最近消息。当前压缩是规则版摘要，不额外调用 LLM，目的是保持 demo 足够小，同时展示 context 治理思想。

## Trace

`trace` 命令可以查看 Runtime 过程：

- `llm_request`
- `llm_response`
- `tool_call`
- `tool_result`
- `context_compact`
- `final_answer`
- `error`

这能证明 Agent 不是黑盒：每一步为什么调工具、工具返回什么、是否压缩上下文，都可以复盘。

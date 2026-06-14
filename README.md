# MinAgent

从零实现的最小可用 Agent，不依赖 LangChain / OpenHands 等现成框架，核心 Runtime 完全手写。

## 运行方式

### 1. 环境要求

- Python 3.10+
- DeepSeek API Key

### 2. 安装依赖

```bash
pip install openai python-dotenv
```

### 3. 配置 API Key

在项目根目录创建 `.env` 文件：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
MAX_STEPS=10
```

### 4. 启动

```bash
python main.py
```

交互命令：

| 输入 | 作用 |
|:--|:--|
| 任意问题 | Agent 处理并回答 |
| `trace` | 查看执行日志 |
| `exit` | 退出 |

### 5. 示例对话

```
你: 帮我规划一个3天北京旅游计划
Agent: [搜索北京攻略 → 创建3天行程任务 → 输出完整计划]

你: 第二天换成室内景点
Agent: [取消原Day2任务 → 搜索室内景点 → 创建新计划]
```

---

## 系统设计

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│                      main.py                        │
│         初始化组件 + 交互循环                          │
└──────────┬──────────┬──────────┬───────────────────┘
           │          │          │
     ┌─────▼──┐  ┌───▼───┐  ┌──▼──────┐
     │ Session │  │ Agent │  │ Trace   │
     │ (Memory)│  │ Loop  │  │ Logger  │
     └────┬────┘  └───┬───┘  └─────────┘
          │           │
     ┌────▼────┐ ┌───▼────────┐
     │ LLM     │ │ Tool       │
     │ Client  │ │ Registry   │
     └─────────┘ └──┬──┬──┬──┘
                    │  │  │
               ┌────▼──▼──▼────┐
               │ Calculator    │
               │ Search (Mock) │
               │ Todo          │
               └───────────────┘
```

### 各模块职责

| 模块 | 文件 | 职责 |
|:--|:--|:--|
| **LLM Client** | `agent/llm_client.py` | 封装 DeepSeek API，支持 Function Calling，含重试机制 |
| **Tool Base** | `tools/base.py` | Tool 抽象基类 + ToolRegistry 注册/查询/schema 生成 |
| **Calculator** | `tools/calculator.py` | 数学表达式计算（加减乘除+括号） |
| **Search** | `tools/search.py` | Mock 搜索，多关键词子串匹配 |
| **Todo** | `tools/todo.py` | 任务 CRUD，支持跨轮次状态持久化 |
| **Agent Loop** | `agent/loop.py` | ReAct 循环核心：接收输入 → 调 LLM → 判断/执行工具 → 循环 |
| **Session** | `agent/session.py` | 对话历史管理，session_id + messages 维护 |
| **Trace Logger** | `trace_logger.py` | 执行日志记录（步骤、动作、详情） |
| **Config** | `config.py` | 环境变量读取 |

### ReAct 循环流程

```
用户输入
  │
  ▼
session.add_user_message()    ← Memory 写入
  │
  ▼
┌─────────────────────┐
│  for step in 1..10  │  ← 最大步数限制
│  ┌───────────────┐  │
│  │ LLM.chat()    │  │  ← 传入完整 messages + tools schema
│  │               │  │
│  │ finish_reason?│  │
│  │  ├─ "stop"    │──┼──▶ return 答案
│  │  └─ "tool_..."│  │
│  │      │        │  │
│  │      ▼        │  │
│  │  执行工具 ──────┼──▶ session.add_tool_result()  ← Memory 写入
│  │  结果塞回消息   │  │
│  │  continue ────┼──▶ 下一轮循环
│  └───────────────┘  │
└─────────────────────┘
```

---

## Memory 的召回时机与放置方式

### 放置（写入记忆）有三个时机

| 时机 | 代码位置 | 存储内容 | 存储位置 |
|:--|:--|:--|:--|
| 用户输入 | `loop.py:28` `session.add_user_message()` | 用户原始消息 | `session.messages` |
| LLM 返回 | `loop.py:44` `session.add_assistant_message()` | LLM 的回复 / tool_call 请求 | `session.messages` |
| 工具执行 | `loop.py:79` `session.add_tool_result()` | 工具返回的结构化结果 | `session.messages` |
| Todo 任务 | `todo.py` `self.tasks[key] = ...` | 跨轮次任务状态 | `TodoTool.tasks`（实例属性） |

### 召回（读取记忆）有两个时机

| 时机 | 方式 | 说明 |
|:--|:--|:--|
| **每次调 LLM** | `session.messages` 全量传入 | **隐式召回**：LLM 从上下文窗口中自行提取相关信息 |
| **需要任务状态** | LLM 调用 `todo("action":"list")` | **显式召回**：主动拉取结构化数据，拿到精确的任务列表 |

### 两种记忆的区别

| | Session（短时记忆） | Todo State（跨轮次状态） |
|:--|:--|:--|
| 存什么 | 对话原文 | 任务结构化数据 |
| 谁读写 | Loop 自动追加 | LLM 通过 Tool 读写 |
| 生命周期 | 跟随 Session 实例 | 跟随 TodoTool 实例 |
| 容量限制 | LLM 上下文窗口（DeepSeek 支持约 128K tokens） | 无限制 |
| 典型场景 | "刚才说过了" | "Day2 行程已取消" |

### 设计取舍

当前为最小实现，**不做**：
- ❌ Embedding 向量检索（对话量少，不需要语义搜索）
- ❌ 摘要压缩（128K 上下文足够日常对话）
- ❌ 外部持久化（进程重启即丢失，Demo 够用）

---

## 工具设计

### Calculator

```json
{
  "name": "calculator",
  "parameters": { "expression": "数学表达式，如 2+3*4 或 (15+27)*3" }
}
```

使用 `eval` 计算，通过 `{"__builtins__": {}}` 限制危险函数。

### Search（Mock）

```json
{
  "name": "search",
  "parameters": { "query": "搜索关键词" }
}
```

多关键词子串匹配策略：每个检索条目绑定多个关键词，query 命中任意一个即返回结果。

### Todo

```json
{
  "name": "todo",
  "parameters": {
    "action": "create / list / update",
    "title": "任务标题（create 时必填）",
    "task_id": "任务ID（update 时必填）",
    "status": "pending / doing / done / cancelled（update 时必填）"
  }
}
```

跨轮次状态持久化载体：任务存储在 `TodoTool.tasks` 字典中，进程内全局共享。
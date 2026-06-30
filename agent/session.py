import uuid
from datetime import datetime


# System Prompt 是 LLM 的最高优先级指令，不是对话内容
# 它告诉 LLM：你是谁、能用什么工具、行为准则是什么
SYSTEM_PROMPT = (
    "你是一个有用的 AI 助手，可以使用工具来完成用户的任务。"
    "规划任务时，请使用 todo 工具创建和跟踪任务。"
    "需要搜索信息时，请使用 search 工具。"
    "需要计算时，请使用 calculator 工具。"
    "【重要】调用工具完成任务后，最终回复中必须列出具体内容和关键信息，"
    "禁止仅用一句话总结（如'规划完成'、'操作完毕'）替代实际结果。"
)


class Session:
    """会话管理：维护多轮对话的消息历史和 session_id。

    Memory 的"放置"方式：
    - 短时记忆：每次对话通过 add_* 方法追加到 self.messages 列表
    - 状态记忆：Session.state 存储当前窗口私有的结构化业务状态

    Memory 的"召回"时机：
    - 隐式召回：每次调 LLM 时，ContextBuilder 选择摘要、状态和最近消息拼接
    - 显式召回：LLM 调用工具（如 todo.list()）主动读取结构化数据
    """

    def __init__(self, session_id: str = ""):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.state = {
            "summary": "",
            "todos": {},
            "todo_counter": 0,
        }
        self.created_at = datetime.now()

    def add_user_message(self, content: str):
        """写入用户消息，作为短期对话记忆。"""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, message: dict):
        """写入 assistant 消息，包含普通回复或 tool_calls 请求。"""
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, content: str):
        # 必须用 role="tool" 且带 tool_call_id
        # 这是 OpenAI Function Calling 协议要求，LLM 靠 tool_call_id 关联调用和结果
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def get_recent_messages(self, limit: int):
        """读取最近 N 条非 system 消息，用于 ContextBuilder 拼接上下文。"""
        history = [msg for msg in self.messages if msg.get("role") != "system"]
        return history[-limit:]

    def get_summary(self):
        """读取压缩后的长期摘要。"""
        return self.state.get("summary", "")

    def get_state_summary(self):
        """把结构化 session state 转成适合放入 prompt 的短文本。"""
        todos = self.state.get("todos", {})
        if not todos:
            return "当前 session 暂无 todo 任务。"

        lines = ["当前 session 的 todo 状态："]
        for task in todos.values():
            lines.append(f"- [{task['status']}] {task['id']}: {task['title']}")
        return "\n".join(lines)

    def compact_if_needed(self, max_messages: int = 12, keep_recent: int = 8):
        """当短期消息过长时，把旧消息压缩进 summary。

        这里用规则版摘要，不额外调用 LLM。这样代码保持最小，同时能展示
        message 拼接治理的关键思想：不是无脑把所有历史都塞进上下文。
        """
        system_messages = [msg for msg in self.messages if msg.get("role") == "system"]
        history = [msg for msg in self.messages if msg.get("role") != "system"]

        if len(history) <= max_messages:
            return False

        compacted = history[:-keep_recent]
        recent = history[-keep_recent:]
        summary_lines = [self.state.get("summary", "").strip()] if self.state.get("summary") else []
        summary_lines.append(self._summarize_messages(compacted))
        self.state["summary"] = "\n".join(line for line in summary_lines if line).strip()
        self.messages = system_messages + recent
        return True

    def _summarize_messages(self, messages):
        """把旧消息转成可读摘要，保留角色和关键内容片段。"""
        lines = ["历史压缩摘要："]
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            if msg.get("tool_calls"):
                content = "assistant 请求调用工具"
            if not content and role == "tool":
                content = "工具返回结果"
            lines.append(f"{role}: {str(content)[:120]}")
        return "\n".join(lines)

    def info(self):
        """返回 session 的轻量状态，用于 CLI 展示。"""
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "todo_count": len(self.state.get("todos", {})),
            "has_summary": bool(self.state.get("summary")),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

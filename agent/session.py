import uuid
from datetime import datetime


SYSTEM_PROMPT = (
    "你是一个有用的 AI 助手，可以使用工具来完成用户的任务。"
    "规划任务时，请使用 todo 工具创建和跟踪任务。"
    "需要搜索信息时，请使用 search 工具。"
    "需要计算时，请使用 calculator 工具。"
    "【重要】调用工具完成规划后，必须用自然语言向用户完整汇报最终结果，禁止仅用一句话总结替代实际结果。"
    "不要只说'已完成'，而要详细描述任务完成的情况。"
)


class Session:
    """会话管理：维护多轮对话的消息历史和 session_id。"""

    def __init__(self, session_id: str = ""):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.created_at = datetime.now()

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, message: dict):
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, content: str):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def info(self):
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
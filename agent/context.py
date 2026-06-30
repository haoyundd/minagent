from agent.session import SYSTEM_PROMPT, Session


class ContextBuilder:
    """Message 拼接治理：统一构造每次发给 LLM 的上下文。

    Runtime 不直接把 session.messages 全量传给模型，而是按固定顺序拼接：
    system prompt、压缩摘要、结构化状态摘要、最近消息、当前用户输入。
    """

    def __init__(self, recent_messages: int = 8):
        self.recent_messages = recent_messages

    def build(self, session: Session, user_input: str = ""):
        """根据当前 session 和本轮输入构造 LLM messages。"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        summary = session.get_summary()
        if summary:
            messages.append({
                "role": "system",
                "content": f"【会话摘要 memory】\n{summary}",
            })

        messages.append({
            "role": "system",
            "content": f"【结构化 session state】\n{session.get_state_summary()}",
        })

        messages.extend(session.get_recent_messages(self.recent_messages))

        if user_input:
            messages.append({"role": "user", "content": user_input})

        return messages

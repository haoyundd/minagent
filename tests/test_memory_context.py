import unittest

from agent.context import ContextBuilder
from agent.session import Session
from tools.base import ToolExecutor, ToolRegistry
from tools.todo import TodoTool


class MemoryContextTest(unittest.TestCase):
    """验证 session memory 隔离和 message 拼接治理。"""

    def test_todo_state_is_isolated_by_session(self):
        registry = ToolRegistry()
        registry.register(TodoTool())
        executor = ToolExecutor(registry)
        session_a = Session("a")
        session_b = Session("b")

        create_result = executor.execute("todo", {"action": "create", "title": "写周报"}, session=session_a)
        list_a = executor.execute("todo", {"action": "list"}, session=session_a)
        list_b = executor.execute("todo", {"action": "list"}, session=session_b)

        self.assertTrue(create_result["ok"])
        self.assertEqual(list_a["output"]["total"], 1)
        self.assertEqual(list_b["output"]["total"], 0)

    def test_context_builder_adds_summary_state_recent_and_current_input(self):
        session = Session("ctx")
        session.state["summary"] = "用户之前在讨论北京旅行。"
        session.state["todos"] = {"1": {"id": "1", "title": "订酒店", "status": "pending"}}
        session.add_user_message("上一轮问题")
        session.add_assistant_message({"role": "assistant", "content": "上一轮回答"})
        builder = ContextBuilder(recent_messages=2)

        messages = builder.build(session, "继续安排第二天")
        contents = "\n".join(str(msg.get("content", "")) for msg in messages)

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("会话摘要 memory", contents)
        self.assertIn("订酒店", contents)
        self.assertEqual(messages[-1], {"role": "user", "content": "继续安排第二天"})

    def test_session_compacts_old_messages_into_summary(self):
        session = Session("compact")
        for index in range(15):
            session.add_user_message(f"消息 {index}")

        compacted = session.compact_if_needed(max_messages=12, keep_recent=8)

        self.assertTrue(compacted)
        self.assertTrue(session.get_summary())
        self.assertLessEqual(len([m for m in session.messages if m["role"] != "system"]), 8)


if __name__ == "__main__":
    unittest.main()

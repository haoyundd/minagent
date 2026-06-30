import json
import unittest

from agent.loop import AgentLoop
from agent.session import Session
from tools.base import ToolRegistry
from tools.calculator import CalculatorTool


class FakeFunction:
    """模拟 OpenAI tool_call.function 对象。"""

    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    """模拟 OpenAI tool_call 对象。"""

    def __init__(self, name, arguments, call_id="call_1"):
        self.id = call_id
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    """模拟 OpenAI message 对象，提供 loop 需要的 model_dump。"""

    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self):
        data = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        return data


class FakeChoice:
    """模拟 OpenAI choice 对象。"""

    def __init__(self, finish_reason, message):
        self.finish_reason = finish_reason
        self.message = message


class FakeResponse:
    """模拟 OpenAI response 对象。"""

    def __init__(self, finish_reason, message):
        self.choices = [FakeChoice(finish_reason, message)]


class FakeLLM:
    """按顺序返回预设 response，并记录每次收到的 messages。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, messages, tools=None):
        self.requests.append({"messages": messages, "tools": tools})
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)


class AgentLoopTest(unittest.TestCase):
    """验证 AgentLoop 对直接回复、工具调用和最大步数的调度。"""

    def test_direct_final_answer(self):
        registry = ToolRegistry()
        llm = FakeLLM([FakeResponse("stop", FakeMessage("你好"))])
        agent = AgentLoop(llm, registry)
        session = Session("direct")

        result = agent.run(session, "打个招呼")

        self.assertEqual(result, "你好")
        self.assertEqual(len(llm.requests), 1)
        self.assertIn("打个招呼", llm.requests[0]["messages"][-1]["content"])

    def test_tool_call_then_final_answer(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        tool_call = FakeToolCall("calculator", json.dumps({"expression": "2+3"}))
        llm = FakeLLM([
            FakeResponse("tool_calls", FakeMessage(None, [tool_call])),
            FakeResponse("stop", FakeMessage("结果是 5")),
        ])
        agent = AgentLoop(llm, registry)
        session = Session("tool")

        result = agent.run(session, "算一下 2+3")

        self.assertEqual(result, "结果是 5")
        self.assertEqual(len(llm.requests), 2)
        self.assertTrue(any(msg.get("role") == "tool" for msg in session.messages))

    def test_max_steps_returns_limit_message(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        tool_call = FakeToolCall("calculator", json.dumps({"expression": "2+3"}))
        llm = FakeLLM([FakeResponse("tool_calls", FakeMessage(None, [tool_call]))])
        agent = AgentLoop(llm, registry, max_steps=1)
        session = Session("limit")

        result = agent.run(session, "一直调工具")

        self.assertIn("最大步数", result)


if __name__ == "__main__":
    unittest.main()

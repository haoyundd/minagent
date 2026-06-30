import unittest

from agent.session import Session
from tools.base import Tool, ToolExecutor, ToolRegistry
from tools.calculator import CalculatorTool
from tools.todo import TodoTool


class ExplodingTool(Tool):
    """测试用工具：模拟工具内部异常。"""

    name = "explode"
    description = "总是抛异常的测试工具"
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs):
        """故意抛异常，验证 ToolExecutor 会隔离失败。"""
        raise RuntimeError("boom")


class ToolGovernanceTest(unittest.TestCase):
    """验证工具治理层的存在性、参数和异常处理。"""

    def test_unknown_tool_returns_structured_error(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        result = executor.execute("missing", {}, session=Session())

        self.assertFalse(result["ok"])
        self.assertEqual(result["tool"], "missing")
        self.assertIn("不存在", result["error"])

    def test_missing_required_argument_returns_structured_error(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        executor = ToolExecutor(registry)

        result = executor.execute("calculator", {}, session=Session())

        self.assertFalse(result["ok"])
        self.assertIn("缺少必填参数", result["error"])

    def test_type_error_returns_structured_error(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        executor = ToolExecutor(registry)

        result = executor.execute("calculator", {"expression": 123}, session=Session())

        self.assertFalse(result["ok"])
        self.assertIn("类型错误", result["error"])

    def test_enum_error_returns_structured_error_before_tool_runs(self):
        registry = ToolRegistry()
        registry.register(TodoTool())
        executor = ToolExecutor(registry)

        result = executor.execute("todo", {"action": "delete"}, session=Session())

        self.assertFalse(result["ok"])
        self.assertIn("取值无效", result["error"])

    def test_tool_business_error_is_normalized(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        executor = ToolExecutor(registry)

        result = executor.execute("calculator", {"expression": "__import__('os')"}, session=Session())

        self.assertFalse(result["ok"])
        self.assertIn("计算失败", result["error"])
        self.assertIn("error", result["output"])

    def test_tool_exception_is_captured(self):
        registry = ToolRegistry()
        registry.register(ExplodingTool())
        executor = ToolExecutor(registry)

        result = executor.execute("explode", {}, session=Session())

        self.assertFalse(result["ok"])
        self.assertIn("工具执行失败", result["error"])

    def test_calculator_allows_math_and_rejects_code(self):
        calculator = CalculatorTool()

        ok_result = calculator.execute("(2+3)*4")
        bad_result = calculator.execute("__import__('os').system('echo bad')")

        self.assertEqual(ok_result["result"], 20)
        self.assertIn("计算失败", bad_result["error"])


if __name__ == "__main__":
    unittest.main()

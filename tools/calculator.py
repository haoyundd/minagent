from tools.base import Tool


class CalculatorTool(Tool):
    name = "calculator"
    description = "计算数学表达式。支持加减乘除和括号。例如: 2+3*4, (15+27)*3"
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 2+3*4 或 (15+27)*3",
            }
        },
        "required": ["expression"],
    }

#execute 是基类 Tool 定义的抽象方法，每个工具子类必须重写它来实现自己的逻辑。它只干两件事：
# 执行核心功能 + 不崩溃地返回结果。
# Agent Loop 会在 LLM 决定调用工具时统一调用 execute。
    def execute(self, expression: str):
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return {"result": result, "expression": expression}
        except ZeroDivisionError:
            return {"error": "除数不能为零", "expression": expression}
        except Exception as e:
            return {"error": f"计算失败: {e}", "expression": expression}
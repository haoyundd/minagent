import ast
import operator

from tools.base import Tool


class CalculatorTool(Tool):
    name = "calculator"
    description = "计算数学表达式。支持加减乘除和括号。例如: 2+3*4, (15+27)*3"
    risk_level = "safe"
    stateful = False
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

    def execute(self, expression: str):
        """执行数学计算，只允许 AST 白名单中的数学节点。

        不使用 eval，避免把 LLM 生成的字符串当成 Python 代码执行。
        当前只支持数字、括号、加减乘除和正负号，满足笔试 demo 的最小需求。
        """
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._eval_node(tree.body)
            return {"result": result, "expression": expression}
        except ZeroDivisionError:
            return {"error": "除数不能为零", "expression": expression}
        except Exception as e:
            return {"error": f"计算失败: {e}", "expression": expression}

    def _eval_node(self, node):
        """递归计算 AST 节点，拒绝任何非数学表达式。"""
        binary_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }
        unary_ops = {
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
        }

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value

        if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return binary_ops[type(node.op)](left, right)

        if isinstance(node, ast.UnaryOp) and type(node.op) in unary_ops:
            value = self._eval_node(node.operand)
            return unary_ops[type(node.op)](value)

        raise ValueError("只支持数字、括号、加减乘除和正负号")

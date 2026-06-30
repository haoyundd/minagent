class Tool:
    """工具基类，所有工具必须继承并重写 execute 方法。

    不用框架时，需要自己定义工具的 schema 规范。
    这里遵循 OpenAI Function Calling 的格式要求：
    - name: 工具名称（LLM 通过它识别要调哪个工具）
    - description: 工具用途（LLM 根据它判断是否该用这个工具）
    - parameters: JSON Schema 格式的参数定义（LLM 根据它生成参数）

    子类只需设置 name/description/parameters 三个属性，重写 execute 即可。
    """

    name = ''
    description = ''
    parameters = {}
    risk_level = "safe"
    stateful = False

    def get_schema(self):
        """生成符合 OpenAI Function Calling 格式的工具 schema。

        返回格式：
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}  # JSON Schema
            }
        }
        """
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': self.parameters,
            }
        }

    def execute(self, **kwargs):
        """执行工具，子类必须重写。

        AgentLoop 在 LLM 返回 tool_calls 时统一调用此方法。
        参数来自 LLM 生成的 JSON，通过 **kwargs 解包传入。
        """
        raise NotImplementedError


class ToolRegistry:
    """工具注册表：管理所有可用工具。

    用法：
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        registry.register(SearchTool())
        registry.get_all_schemas()  # 生成所有工具的 schema 列表，传给 LLM
    """

    def __init__(self):
        self._tools = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def get_all_schemas(self):
        """获取所有工具的 schema 列表，用于传给 LLM 的 tools 参数。"""
        return [tool.get_schema() for tool in self._tools.values()]

    def list_names(self):
        return list(self._tools.keys())


class ToolExecutor:
    """工具治理层：统一管理工具调用前后的安全边界。

    LLM 返回的 tool_call 不是可信输入，Runtime 必须先做工具存在性检查、
    required/type/enum 参数校验、异常隔离和 trace 记录，再决定是否真正执行工具。
    """

    def __init__(self, registry: ToolRegistry, trace_logger=None):
        self.registry = registry
        self.tracer = trace_logger

    def execute(self, tool_name: str, tool_args: dict, session=None, step_num: int = 0):
        """执行一次受治理的工具调用，并返回统一结构。

        返回结构固定包含 ok/tool/input/output/error，方便 LLM、测试和 trace
        用同一种方式理解成功与失败。
        """
        if not isinstance(tool_args, dict):
            return self._error(tool_name, {}, "工具参数必须是 JSON object", step_num)

        safe_args = tool_args
        self._log(step_num, "tool_call", f"{tool_name}: {safe_args}")

        tool = self.registry.get(tool_name)
        if tool is None:
            return self._error(tool_name, safe_args, f"工具 {tool_name} 不存在，可用: {self.registry.list_names()}", step_num)

        errors = self._validate_args(tool, safe_args)
        if errors:
            return self._error(tool_name, safe_args, "；".join(errors), step_num)

        try:
            # stateful 工具需要访问当前 Session 的私有状态；无状态工具只接收业务参数。
            if tool.stateful:
                output = tool.execute(session=session, **safe_args)
            else:
                output = tool.execute(**safe_args)
        except Exception as e:
            return self._error(tool_name, safe_args, f"工具执行失败: {e}", step_num)

        tool_error = self._extract_tool_error(output)
        result = {
            "ok": tool_error == "",
            "tool": tool_name,
            "input": safe_args,
            "output": output,
            "error": tool_error,
        }
        if tool_error:
            self._log(step_num, "error", tool_error)
        self._log(step_num, "tool_result", f"{tool_name}: {result}")
        return result

    def _validate_args(self, tool: Tool, tool_args: dict):
        """按工具 schema 做最小参数校验。

        只实现 Runtime 最需要的 required/type/enum，不追求完整 JSON Schema。
        这样能管住 LLM 常见错误，又不会为了 demo 引入额外依赖。
        """
        errors = []
        required = tool.parameters.get("required", [])
        missing = [name for name in required if name not in tool_args or tool_args.get(name) in (None, "")]
        if missing:
            errors.append(f"缺少必填参数: {missing}")

        properties = tool.parameters.get("properties", {})
        for name, value in tool_args.items():
            schema = properties.get(name)
            if not schema:
                continue

            expected_type = schema.get("type")
            if expected_type and not self._match_json_type(value, expected_type):
                errors.append(f"参数 {name} 类型错误: 期望 {expected_type}，实际 {type(value).__name__}")

            enum_values = schema.get("enum")
            if enum_values and value not in enum_values:
                errors.append(f"参数 {name} 取值无效: {value}，可选: {enum_values}")

        return errors

    def _match_json_type(self, value, expected_type: str):
        """把 JSON Schema 的基础类型映射到 Python 类型。"""
        type_map = {
            "string": str,
            "object": dict,
            "array": list,
            "boolean": bool,
        }
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])
        return True

    def _extract_tool_error(self, output):
        """识别工具内部用返回值表达的业务错误。"""
        if isinstance(output, dict) and output.get("error"):
            return str(output["error"])
        return ""

    def _error(self, tool_name: str, tool_args: dict, message: str, step_num: int):
        """把所有工具失败统一包装成结构化错误。"""
        result = {
            "ok": False,
            "tool": tool_name,
            "input": tool_args,
            "output": None,
            "error": message,
        }
        self._log(step_num, "error", message)
        self._log(step_num, "tool_result", f"{tool_name}: {result}")
        return result

    def _log(self, step_num: int, action: str, detail: str):
        """trace_logger 可选，方便单元测试直接使用 ToolExecutor。"""
        if self.tracer:
            self.tracer.log(step_num, action, detail)

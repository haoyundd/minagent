import json
from config import MAX_STEPS
from agent.llm_client import LLMClient
from agent.session import Session
from tools.base import ToolRegistry
from trace_logger import TraceLogger


class AgentLoop:
    """Agent 核心运行时：ReAct 循环。

    接收用户输入 → 调 LLM → 判断回答/调工具 → 执行工具 → 继续循环 → 最终回答
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        max_steps: int = MAX_STEPS,
        trace_logger: TraceLogger = None,
    ):
        self.llm = llm_client
        self.registry = tool_registry
        self.max_steps = max_steps
        self.tracer = trace_logger or TraceLogger()

    def run(self, session: Session, user_input: str):
        session.add_user_message(user_input)

        for step in range(1, self.max_steps + 1):
            try:
                response = self.llm.chat(
                    messages=session.messages,
                    tools=self.registry.get_all_schemas(),
                )
            except Exception as e:
                self.tracer.log(step, "error", f"LLM 调用失败: {e}")
                return f"抱歉，调用模型时出错: {e}"

            choice = response.choices[0]
            assistant_msg = choice.message.model_dump()

            if choice.finish_reason == "stop":
                session.add_assistant_message(assistant_msg)
                self.tracer.log(step, "final_answer", choice.message.content[:100])
                return choice.message.content

            if choice.finish_reason == "tool_calls":
                session.add_assistant_message(assistant_msg)
                tool_calls = choice.message.tool_calls

                for tc in tool_calls:
                    tool_name = tc.function.name
                    tool_args_str = tc.function.arguments
                    self.tracer.log(step, f"call {tool_name}", tool_args_str)

                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError:
                        error_msg = f"参数解析失败: {tool_args_str}"
                        self.tracer.log(step, "error", error_msg)
                        session.add_tool_result(tc.id, json.dumps({"error": error_msg}))
                        continue

                    tool = self.registry.get(tool_name)
                    if tool is None:
                        error_msg = f"工具 {tool_name} 不存在，可用: {self.registry.list_names()}"
                        self.tracer.log(step, "error", error_msg)
                        session.add_tool_result(tc.id, json.dumps({"error": error_msg}))
                        continue

                    try:
                        result = tool.execute(**tool_args)
                    except Exception as e:
                        result = {"error": f"工具执行失败: {e}"}

                    result_str = json.dumps(result, ensure_ascii=False)
                    self.tracer.log(step, f"result {tool_name}", result_str[:200])
                    session.add_tool_result(tc.id, result_str)

                continue

            self.tracer.log(step, "error", f"未知 finish_reason: {choice.finish_reason}")
            return f"未知状态: {choice.finish_reason}"

        return "已达到最大步数限制，以下是当前信息。请尝试换一种方式提问。"
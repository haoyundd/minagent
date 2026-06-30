import json
from config import MAX_STEPS
from agent.context import ContextBuilder
from agent.llm_client import LLMClient
from agent.session import Session
from tools.base import ToolExecutor, ToolRegistry
from trace_logger import TraceLogger


class AgentLoop:
    """Agent 核心运行时：ReAct（Reasoning + Acting）循环。

    不依赖任何 Agent 框架，纯手写实现。
    核心流程：接收用户输入 → 调 LLM → 判断 finish_reason →
    stop 则返回答案 / tool_calls 则执行工具 → 结果塞回 Session → 继续循环。

    关键设计：
    1. for 循环 + max_steps 防止死循环
    2. finish_reason 分支判断："stop" 直接返回，"tool_calls" 执行工具
    3. 三层异常处理：LLM 调用 / 参数解析（JSONDecodeError）/ 工具执行
    4. 工具执行结果以 role="tool" + tool_call_id 格式追加到 Session
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        max_steps: int = MAX_STEPS,
        trace_logger: TraceLogger = None,
        context_builder: ContextBuilder = None,
        tool_executor: ToolExecutor = None,
    ):
        self.llm = llm_client          # 大模型客户端（封装了 DeepSeek API）
        self.registry = tool_registry  # 工具注册表（管理所有可用工具）
        self.max_steps = max_steps     # 最大步数限制，防止无限循环
        self.tracer = trace_logger or TraceLogger()
        self.context_builder = context_builder or ContextBuilder()
        self.tool_executor = tool_executor or ToolExecutor(tool_registry, self.tracer)

    def run(self, session: Session, user_input: str):
        """运行一次 Agent 循环。

        session 跨轮次复用，同一进程内多次调用 run 共享同一个 Session。
        """
        user_recorded = False

        for step in range(1, self.max_steps + 1):
            # ---- 第 1 层异常：LLM 调用失败 ----
            try:
                messages = self.context_builder.build(
                    session=session,
                    user_input=user_input if not user_recorded else "",
                )
                self.tracer.log(step, "llm_request", f"messages={len(messages)}, tools={self.registry.list_names()}")
                response = self.llm.chat(
                    messages=messages,          # 由 ContextBuilder 治理后的上下文
                    tools=self.registry.get_all_schemas(),  # 所有可用工具
                )
            except Exception as e:
                self.tracer.log(step, "error", f"LLM 调用失败: {e}")
                return f"抱歉，调用模型时出错: {e}"

            if not user_recorded:
                session.add_user_message(user_input)
                user_recorded = True

            # LLM 返回的 choice，包含 finish_reason 和 message
            # finish_reason 有三种："stop" 直接回答、"tool_calls" 调工具、"length" 截断
            choice = response.choices[0]
            assistant_msg = choice.message.model_dump()
            self.tracer.log(step, "llm_response", f"finish_reason={choice.finish_reason}")

            # ---- 分支 1：LLM 直接回答 ----
            if choice.finish_reason == "stop":
                session.add_assistant_message(assistant_msg)
                self.tracer.log(step, "final_answer", choice.message.content[:100])
                self._compact_session(session, step)
                return choice.message.content

            # ---- 分支 2：LLM 要求调用工具 ----
            if choice.finish_reason == "tool_calls":
                session.add_assistant_message(assistant_msg)
                tool_calls = choice.message.tool_calls

                for tc in tool_calls:
                    tool_name = tc.function.name
                    tool_args_str = tc.function.arguments  # LLM 返回的 JSON 字符串
                    self.tracer.log(step, f"call {tool_name}", tool_args_str)

                    # ---- 第 2 层异常：参数解析失败（LLM 可能返回非法 JSON）----
                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError:
                        error_msg = f"参数解析失败: {tool_args_str}"
                        self.tracer.log(step, "error", error_msg)
                        session.add_tool_result(tc.id, json.dumps({
                            "ok": False,
                            "tool": tool_name,
                            "input": tool_args_str,
                            "output": None,
                            "error": error_msg,
                        }, ensure_ascii=False))
                        continue  # 不中断循环，让 LLM 下一轮修正

                    # ---- 第 3 层治理：工具存在性、参数、异常统一交给 ToolExecutor ----
                    result = self.tool_executor.execute(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        session=session,
                        step_num=step,
                    )

                    # 工具结果必须以 role="tool" + tool_call_id 格式追加
                    # 这是 OpenAI Function Calling 协议的硬性要求
                    result_str = json.dumps(result, ensure_ascii=False)
                    session.add_tool_result(tc.id, result_str)

                self._compact_session(session, step)
                continue  # 继续循环，LLM 下一轮会看到工具结果

            # 兜底：未知 finish_reason
            self.tracer.log(step, "error", f"未知 finish_reason: {choice.finish_reason}")
            return f"未知状态: {choice.finish_reason}"

        # 超步数兜底
        return "已达到最大步数限制，以下是当前信息。请尝试换一种方式提问。"

    def _compact_session(self, session: Session, step: int):
        """在每轮写入后尝试压缩上下文，并记录 trace。"""
        if session.compact_if_needed():
            self.tracer.log(step, "context_compact", "历史消息超过阈值，已写入 summary memory")

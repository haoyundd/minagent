from agent.llm_client import LLMClient
from agent.loop import AgentLoop
from agent.session import Session
from tools.base import ToolRegistry
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from tools.todo import TodoTool
from trace_logger import TraceLogger


def main():
    # 1. 初始化组件
    print("正在连接 DeepSeek...")
    llm = LLMClient()

    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(TodoTool())

    tracer = TraceLogger()
    agent = AgentLoop(llm, registry, trace_logger=tracer)

    # 2. 创建会话（跨轮次复用同一个 Session）
    session = Session()
    print(f"会话已创建 (ID: {session.session_id})")
    print(f"可用工具: {registry.list_names()}")
    print("输入 'exit' 退出，输入 'trace' 查看执行日志\n")

    # 3. 主循环
    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() == "exit":
            print("再见！")
            break

        if user_input.lower() == "trace":
            tracer.print_summary()
            continue

        print("Agent: ", end="", flush=True)
        response = agent.run(session, user_input)
        print(response)
        print()


if __name__ == "__main__":
    main()
from agent.llm_client import LLMClient
from agent.loop import AgentLoop
from agent.session import Session
from tools.base import ToolRegistry
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from tools.todo import TodoTool
from trace_logger import TraceLogger


def main():
    # 1. 初始化组件（依赖注入，不 hardcode）
    print("正在连接 DeepSeek...")
    llm = LLMClient()

    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(TodoTool())

    tracer = TraceLogger()
    agent = AgentLoop(llm, registry, trace_logger=tracer)

    # 2. 创建会话池：模拟同一用户打开多个独立窗口
    current_session = Session()
    sessions = {current_session.session_id: current_session}
    print(f"会话已创建 (ID: {current_session.session_id})")
    print(f"可用工具: {registry.list_names()}")
    print("输入 'exit' 退出，输入 'trace' 查看执行日志")
    print("输入 '/new' 开启新会话，输入 '/sessions' 查看会话，输入 '/use <id>' 切换会话\n")

    # 3. CLI 主循环：同一进程内多轮对话
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

        # 快捷命令：开启新会话（不退出进程）
        if user_input.lower() == "/new":
            current_session = Session()
            sessions[current_session.session_id] = current_session
            print(f"新会话已创建 (ID: {current_session.session_id})\n")
            continue

        # 快捷命令：列出所有会话，展示每个 session 的 memory 状态
        if user_input.lower() == "/sessions":
            print_sessions(sessions, current_session.session_id)
            continue

        # 快捷命令：切换到指定会话，模拟回到另一个聊天窗口
        if user_input.lower().startswith("/use "):
            target_id = user_input.split(maxsplit=1)[1].strip()
            if target_id not in sessions:
                print(f"会话 {target_id} 不存在，可用会话: {list(sessions.keys())}\n")
                continue
            current_session = sessions[target_id]
            print(f"已切换到会话 {current_session.session_id}\n")
            continue

        print(f"Agent[{current_session.session_id}]: ", end="", flush=True)
        response = agent.run(current_session, user_input)
        print(response)
        print()


def print_sessions(sessions, current_session_id: str):
    """打印当前进程内的 session 列表，辅助验证 session 隔离。"""
    print("\n会话列表:")
    for session_id, session in sessions.items():
        info = session.info()
        current_mark = "*" if session_id == current_session_id else " "
        print(
            f"{current_mark} {session_id} | messages={info['message_count']} "
            f"| todos={info['todo_count']} | summary={info['has_summary']} "
            f"| created_at={info['created_at']}"
        )
    print()


if __name__ == "__main__":
    main()

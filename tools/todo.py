from tools.base import Tool


class TodoTool(Tool):
    """任务管理工具，支持创建、查询、更新任务。

    跨轮次状态持久化的关键：任务存储在当前 Session.state 中，
    同一个 session 内多次调用 run() 可以继续读写任务，
    不同 session 的 todo 数据互相隔离。

    对比用框架（如 LangChain）：
    框架通常提供 BaseTool 基类和 @tool 装饰器，自动处理 schema 生成。
    不用框架需要自己写 Tool 基类、ToolRegistry、get_schema()。
    但核心逻辑（execute 方法）写法完全一样。
    """

    name = "todo"
    risk_level = "stateful"
    stateful = True
    description = (
        "任务管理工具，用于创建、查询、更新任务。"
        "操作类型（action）：create（创建任务）、list（查看所有任务）、"
        "update（更新任务状态，状态值：pending/doing/done/cancelled）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "update"],
                "description": "操作类型：create 创建任务, list 查看任务, update 更新状态",
            },
            "title": {
                "type": "string",
                "description": "任务标题（create 时必填）",
            },
            "task_id": {
                "type": "string",
                "description": "任务 ID（update 时必填）",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "doing", "done", "cancelled"],
                "description": "任务状态：pending 待办, doing 进行中, done 已完成, cancelled 已取消",
            },
        },
        "required": ["action"],
    }

    def execute(self, action: str, title: str = "", task_id: str = "", status: str = "", session=None):
        """执行 todo 操作，所有数据都写入当前 Session 的私有 state。"""
        if session is None:
            return {"error": "todo 工具需要 session 才能读写私有状态"}

        if action == "create":
            return self._create(session, title)
        elif action == "list":
            return self._list(session)
        elif action == "update":
            return self._update(session, task_id, status)
        else:
            return {"error": f"未知操作: {action}"}

    def _create(self, session, title: str):
        """在当前 session 中创建任务，避免不同窗口互相污染。"""
        if not title.strip():
            return {"error": "任务标题不能为空"}
        session.state["todo_counter"] = session.state.get("todo_counter", 0) + 1
        task_id = str(session.state["todo_counter"])
        session.state.setdefault("todos", {})[task_id] = {
            "id": task_id,
            "title": title.strip(),
            "status": "pending",
        }
        return {"action": "create", "task": session.state["todos"][task_id]}

    def _list(self, session):
        """列出当前 session 的任务。"""
        tasks = session.state.setdefault("todos", {})
        return {
            "action": "list",
            "tasks": list(tasks.values()),
            "total": len(tasks),
        }

    def _update(self, session, task_id: str, status: str):
        """更新当前 session 中的任务状态。"""
        tasks = session.state.setdefault("todos", {})
        if task_id not in tasks:
            return {"error": f"任务 {task_id} 不存在"}
        if status not in ("pending", "doing", "done", "cancelled"):
            return {"error": f"无效状态: {status}，可选: pending/doing/done/cancelled"}
        tasks[task_id]["status"] = status
        return {"action": "update", "task": tasks[task_id]}

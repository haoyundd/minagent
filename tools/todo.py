from tools.base import Tool


class TodoTool(Tool):
    name = "todo"
    description = (
        "任务管理工具，用于创建、查询、更新任务。"
        "操作类型（action）：create（创建任务）、list（查看所有任务）、"
        "update（更新任务状态，状态值：pending/doing/done）。"
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

    def __init__(self):
        self.tasks = {}  # 跨轮次持久化的任务字典
        self._counter = 0

    def execute(self, action: str, title: str = "", task_id: str = "", status: str = ""):
        if action == "create":
            return self._create(title)
        elif action == "list":
            return self._list()
        elif action == "update":
            return self._update(task_id, status)
        else:
            return {"error": f"未知操作: {action}"}

    def _create(self, title: str):
        if not title.strip():
            return {"error": "任务标题不能为空"}
        self._counter += 1
        task_id = str(self._counter)
        self.tasks[task_id] = {
            "id": task_id,
            "title": title.strip(),
            "status": "pending",
        }
        return {"action": "create", "task": self.tasks[task_id]}

    def _list(self):
        return {
            "action": "list",
            "tasks": list(self.tasks.values()),
            "total": len(self.tasks),
        }

    def _update(self, task_id: str, status: str):
        if task_id not in self.tasks:
            return {"error": f"任务 {task_id} 不存在"}
        if status not in ("pending", "doing", "done", "cancelled"):
            return {"error": f"无效状态: {status}，可选: pending/doing/done/cancelled"}
        self.tasks[task_id]["status"] = status
        return {"action": "update", "task": self.tasks[task_id]}
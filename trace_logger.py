import time
from datetime import datetime


class TraceLogger:
    """记录每一步的执行日志，用于面试展示。"""

    def __init__(self):
        self.steps = []

    def log(self, step_num: int, action: str, detail: str):
        entry = {
            "step": step_num,
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "detail": detail,
        }
        self.steps.append(entry)

    def dump(self):
        return self.steps

    def print_summary(self):
        print("\n" + "=" * 50)
        print("执行日志 (Trace)")
        print("=" * 50)
        for s in self.steps:
            print(f"  Step {s['step']} [{s['time']}] {s['action']}")
            print(f"    {s['detail']}")
        print("=" * 50)
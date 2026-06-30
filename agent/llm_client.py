import time
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class LLMClient:
    """LLM 客户端，封装 DeepSeek API 调用。

    使用 OpenAI SDK 连接 DeepSeek：
    DeepSeek 完全兼容 OpenAI API 格式，只需更换 base_url 和 api_key。
    换成其他兼容厂商（智谱/通义千问/Kimi）只需改这两个参数。

    重试策略：指数退避（exponential backoff），最多 3 次。
    第 1 次等 2 秒，第 2 次等 4 秒，第 3 次放弃。
    """

    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY 未配置，请检查 .env 文件")
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self.model = DEEPSEEK_MODEL
        self.max_retries = 3
        self.retry_delay = 2

    def chat(self, messages, tools=None):
        """调用 LLM，支持 Function Calling。

        messages: 完整对话历史（包含 system/user/assistant/tool 四种角色）
        tools: 可用工具 schema 列表，为 None 时 LLM 只能纯文本回答
        tool_choice="auto": 让 LLM 自行判断是否需要调工具
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)  # 指数退避：2s, 4s
                    print(f"[LLM 调用失败] {e}，{wait}秒后重试 ({attempt + 1}/{self.max_retries})")
                    time.sleep(wait)
                else:
                    print(f"[LLM 调用失败] 已重试{self.max_retries}次，放弃: {e}")

        raise RuntimeError(f"LLM 调用失败: {last_error}")
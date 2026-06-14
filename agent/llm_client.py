import time
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class LLMClient:
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
        """调用 LLM，支持工具调用。失败时重试。"""
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
                    wait = self.retry_delay * (2 ** attempt)
                    print(f"[LLM 调用失败] {e}，{wait}秒后重试 ({attempt + 1}/{self.max_retries})")
                    time.sleep(wait)
                else:
                    print(f"[LLM 调用失败] 已重试{self.max_retries}次，放弃: {e}")

        raise RuntimeError(f"LLM 调用失败: {last_error}")

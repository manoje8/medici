from cerebras.cloud.sdk import AsyncCerebras

from src.common.llm.base import BaseLLM, LLMResponse
from src.common.utils.config import config


class CerebrasAI(BaseLLM):
    def __init__(self, model: str = "gpt-oss-120b", max_tokens: int = 1024, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.client = AsyncCerebras(
            api_key=config.CEREBRAS_API_KEY,
        )

    async def _complete_impl(self, prompt: str, max_token: int, **kwargs) -> LLMResponse:
        response = await self.client.completions.create(
            model=self.model,
            prompt=prompt,
            max_tokens=max_token,
            top_p=kwargs.get("top_p", 0.95),
            temperature=kwargs.get("temperature", 0.1),
        )

        if not response or not response.choices[0].text:
            raise ValueError("Cerebras returned empty response")

        token_usage = {}

        if hasattr(response, "usage"):
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total": response.usage.total_tokens or 0,
            }

        return LLMResponse(response.choices[0].text, {"token_usage": token_usage})

    @property
    def model_name(self) -> str:
        return self.model

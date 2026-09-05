import os
from typing import Optional
from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: Optional[str] = None):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    def complete(self, system: str, prompt: str, json_mode: bool = False,
                 max_tokens: int = 1500, temperature: float = 0.4) -> str:
        sys_prompt = system
        if json_mode:
            sys_prompt += "\nRespond with ONLY valid JSON. No prose, no markdown fences."
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=sys_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

"""
Abstract LLM provider interface.

Every "brain" of the AI Teacher (lesson planning, explanation generation,
answer evaluation, misconception detection, translation) goes through this
interface. This makes the system model-agnostic: swap OpenAI / Anthropic /
Gemini / a local Ollama model / the built-in offline MockProvider without
touching any teaching logic.
"""
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, prompt: str, json_mode: bool = False,
                 max_tokens: int = 1500, temperature: float = 0.4) -> str:
        """Return raw text (or JSON string if json_mode=True) completion."""
        raise NotImplementedError

    def complete_json(self, system: str, prompt: str, max_tokens: int = 1500) -> dict:
        import json
        raw = self.complete(system, prompt, json_mode=True, max_tokens=max_tokens)
        raw = raw.strip()
        # Strip markdown code fences if the model added them anyway.
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Best-effort recovery: find the first {...} or [...] block.
            import re
            match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise


_PROVIDER_CACHE: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    """Factory: picks a provider based on environment configuration.

    Priority: ANTHROPIC_API_KEY > OPENAI_API_KEY > local Ollama > MockProvider.
    This means the project runs (and can be demoed / graded) with **zero
    API keys and zero internet dependency** out of the box, and instantly
    upgrades to a real frontier model the moment a key is supplied.
    """
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is not None:
        return _PROVIDER_CACHE

    import os
    if os.getenv("ANTHROPIC_API_KEY"):
        from .anthropic_provider import AnthropicProvider
        _PROVIDER_CACHE = AnthropicProvider()
    elif os.getenv("OPENAI_API_KEY"):
        from .openai_provider import OpenAIProvider
        _PROVIDER_CACHE = OpenAIProvider()
    elif os.getenv("OLLAMA_MODEL"):
        from .ollama_provider import OllamaProvider
        _PROVIDER_CACHE = OllamaProvider()
    else:
        from .mock_provider import MockProvider
        _PROVIDER_CACHE = MockProvider()
    return _PROVIDER_CACHE

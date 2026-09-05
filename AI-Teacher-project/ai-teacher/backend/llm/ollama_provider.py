import os
import json
import requests
from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """Local, offline, free model runner (https://ollama.com). Good fallback
    for teams without API budget who still want a real LLM instead of the mock."""
    name = "ollama"

    def __init__(self):
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1")
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def complete(self, system: str, prompt: str, json_mode: bool = False,
                 max_tokens: int = 1500, temperature: float = 0.4) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        r = requests.post(f"{self.host}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["response"]

"""AIProvider interface — swappable extraction backends."""

import json
import re
from abc import ABC, abstractmethod

import ollama
from django.conf import settings


class AIProvider(ABC):
    @abstractmethod
    def extract(self, prompt: str) -> tuple[dict | None, str | None]:
        """Returns (parsed_json, error_message)."""
        ...


class OllamaProvider(AIProvider):
    def __init__(self, model_name=None):
        self.model_name = model_name or getattr(settings, "OLLAMA_MODEL", "")

    def extract(self, prompt):
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0},
            )
        except Exception as exc:
            return None, f"Ollama request failed: {exc}"

        raw = response["message"]["content"].strip()
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
        try:
            return json.loads(raw), None
        except json.JSONDecodeError as exc:
            return None, f"Model did not return valid JSON: {exc}"


class CloudLLMProvider(AIProvider):
    """
    Placeholder for an API-based fallback (e.g. Anthropic/OpenAI).
    Not implemented yet — wire in only if the spike shows local extraction
    is insufficient. Kept here so the rest of the app never needs to change
    when/if this gets implemented.
    """

    def extract(self, prompt):
        raise NotImplementedError("CloudLLMProvider not configured. Add API key + client to use this.")


def get_provider() -> AIProvider:
    provider_name = settings.AI_PROVIDER
    if provider_name == "ollama":
        return OllamaProvider()
    if provider_name == "cloud":
        return CloudLLMProvider()
    raise ValueError(f"Unknown AI_PROVIDER setting: {provider_name}")
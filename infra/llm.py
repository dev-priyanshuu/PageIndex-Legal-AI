from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from infra.config import SETTINGS


@dataclass
class LlmMessage:
    role: str
    content: str


class BaseLlmClient:
    def generate(self, prompt: str, model: str | None = None) -> str:
        raise NotImplementedError


class MockLlmClient(BaseLlmClient):
    def generate(self, prompt: str, model: str | None = None) -> str:
        return (
            "Reasoned legal answer (mock): Based on retrieved clauses, the agreement includes "
            "core indemnity and termination terms; review compliance/data-protection carve-outs."
        )


class GeminiLlmClient(BaseLlmClient):
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    @staticmethod
    def _normalize(model: str) -> str:
        return model if model.startswith("models/") else f"models/{model}"

    @staticmethod
    def _dedupe(models: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for model in models:
            value = model.strip()
            if not value or value in seen:
                continue
            out.append(value)
            seen.add(value)
        return out

    def _candidate_models(self, requested_model: str | None) -> list[str]:
        configured = [m.strip() for m in SETTINGS.gemini_models.split(",") if m.strip()]
        ordered = [requested_model, SETTINGS.gemini_model, *configured]
        raw_candidates = self._dedupe([m for m in ordered if m])
        normalized_candidates = self._dedupe([self._normalize(m) for m in raw_candidates])
        return self._dedupe([*raw_candidates, *normalized_candidates])

    def generate(self, prompt: str, model: str | None = None) -> str:
        if not self.api_key:
            return "Gemini key missing; falling back to mock output."
        try:
            from google import genai  # type: ignore
        except Exception:
            return "Gemini SDK missing. Install dependency `google-genai`."

        # Lazy import so tracing module is only loaded when actually needed
        from infra.tracing import trace_llm_call

        client = genai.Client(api_key=self.api_key)
        last_error = ""
        for candidate_model in self._candidate_models(model):
            try:
                t0 = time.time()
                response = client.models.generate_content(
                    model=candidate_model,
                    contents=prompt,
                )
                latency_ms = (time.time() - t0) * 1000
                text = getattr(response, "text", None)
                if text and text.strip():
                    # ── LangSmith: log every successful LLM call ──────────────
                    trace_llm_call(
                        prompt=prompt,
                        response=text.strip(),
                        model=candidate_model,
                        provider="gemini",
                        latency_ms=latency_ms,
                    )
                    return text.strip()
                last_error = f"Empty response for model {candidate_model}"
            except Exception as exc:
                last_error = f"{candidate_model}: {exc}"
                continue
        return f"Gemini call failed across fallback models. Last error: {last_error}"


def get_llm_client(provider: str) -> BaseLlmClient:
    selected = provider.lower()
    if selected == "gemini":
        return GeminiLlmClient(SETTINGS.gemini_api_key)
    return MockLlmClient()

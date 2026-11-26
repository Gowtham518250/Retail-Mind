"""Regression tests for the Retail Mind agent provider fallback."""
import asyncio
from types import SimpleNamespace

from agentic import graph as graph_module


class _RateLimited(Exception):
    status_code = 429


def test_agent_retries_with_fallback_model_after_primary_429(monkeypatch):
    requested_models = []

    class _FakeAsyncGroq:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        async def _create(self, **kwargs):
            requested_models.append(kwargs["model"])
            if kwargs["model"] == "openai/gpt-oss-120b":
                raise _RateLimited("model rate limited")
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="Fallback response", tool_calls=[])
                    )
                ]
            )

        async def close(self):
            return None

    monkeypatch.setattr(graph_module, "AsyncGroq", _FakeAsyncGroq)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("RETAIL_MIND_AGENT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("RETAIL_MIND_AGENT_FALLBACK_MODEL", "openai/gpt-oss-20b")

    result = asyncio.run(
        graph_module._call_model(
            {
                "messages": [{"role": "user", "content": "Prepare a bill"}],
                "tool_definitions": [],
                "tool_rounds": 0,
                "tool_outputs": [],
                "context": {"language_code": "en"},
            }
        )
    )

    assert requested_models == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert result["final_answer"] == "Fallback response"
    assert result["tool_calls"] == []

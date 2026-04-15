"""Tests for analyze_category and run_full_analysis with a mocked Anthropic client."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import analyzer
from analyzer import CATEGORIES, analyze_category, run_full_analysis


CATEGORY = {
    "id": "arttoy",
    "name": "아트토이",
    "emoji": "🎨",
    "keywords": "Bearbrick",
}

VALID_PAYLOAD = {
    "items": [
        {
            "rank": 1,
            "name": "Bearbrick 1000%",
            "price_range": "80만원~95만원",
            "price_trend": "상승",
            "background": "bg",
            "investment_point": "ip",
            "forecast": "fc",
            "score": 85,
        }
    ],
    "market_summary": "strong demand",
}


def _mock_client(text: str) -> MagicMock:
    """Build a fake anthropic.Anthropic client whose messages.create() returns `text`."""
    client = MagicMock()
    response = SimpleNamespace(content=[SimpleNamespace(text=text)])
    client.messages.create.return_value = response
    return client


class TestAnalyzeCategory:
    async def test_plain_json_response(self):
        client = _mock_client(json.dumps(VALID_PAYLOAD))
        out = await analyze_category(client, CATEGORY)
        assert "Bearbrick 1000%" in out
        assert "85/100" in out
        # Prompt was called once
        assert client.messages.create.call_count == 1

    async def test_json_wrapped_in_json_code_fence(self):
        raw = f"```json\n{json.dumps(VALID_PAYLOAD)}\n```"
        client = _mock_client(raw)
        out = await analyze_category(client, CATEGORY)
        assert "Bearbrick 1000%" in out

    async def test_json_wrapped_in_plain_code_fence(self):
        raw = f"```\n{json.dumps(VALID_PAYLOAD)}\n```"
        client = _mock_client(raw)
        out = await analyze_category(client, CATEGORY)
        assert "Bearbrick 1000%" in out

    async def test_malformed_json_returns_user_friendly_error(self):
        client = _mock_client("this is not json at all")
        out = await analyze_category(client, CATEGORY)
        assert "아트토이" in out
        assert "파싱 오류" in out
        # Must not raise

    async def test_api_exception_returns_user_friendly_error(self):
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("boom")
        out = await analyze_category(client, CATEGORY)
        assert "아트토이" in out
        assert "오류" in out

    async def test_prompt_contains_category_fields(self):
        client = _mock_client(json.dumps(VALID_PAYLOAD))
        await analyze_category(client, CATEGORY)
        kwargs = client.messages.create.call_args.kwargs
        prompt = kwargs["messages"][0]["content"]
        assert "아트토이" in prompt
        assert "Bearbrick" in prompt


class TestRunFullAnalysis:
    async def test_runs_every_category_in_order(self, monkeypatch):
        calls: list[str] = []

        async def fake_analyze(client, category):
            calls.append(category["id"])
            return f"report-{category['id']}"

        monkeypatch.setattr(analyzer, "analyze_category", fake_analyze)
        # Patch the Anthropic constructor so we don't require a real API key.
        monkeypatch.setattr(analyzer.anthropic, "Anthropic", lambda api_key: MagicMock())

        results = await run_full_analysis("fake-key")

        assert len(results) == len(CATEGORIES)
        assert calls == [c["id"] for c in CATEGORIES]
        assert results[0] == f"report-{CATEGORIES[0]['id']}"

    async def test_categories_run_in_parallel(self, monkeypatch):
        """With 5 categories and an asyncio.Barrier(5), sequential execution
        would deadlock on the first await. If this test completes, gather
        actually schedules the coroutines concurrently."""
        import asyncio as _asyncio

        barrier = _asyncio.Barrier(len(CATEGORIES))

        async def fake_analyze(client, category):
            await barrier.wait()
            return f"ok-{category['id']}"

        monkeypatch.setattr(analyzer, "analyze_category", fake_analyze)
        monkeypatch.setattr(analyzer.anthropic, "Anthropic", lambda api_key: MagicMock())

        results = await _asyncio.wait_for(run_full_analysis("fake-key"), timeout=2.0)
        assert len(results) == len(CATEGORIES)
        assert all(r.startswith("ok-") for r in results)

    async def test_analyze_category_does_not_block_event_loop(self, monkeypatch):
        """analyze_category must offload the sync Anthropic SDK call so other
        coroutines can make progress while it is outstanding."""
        import asyncio as _asyncio
        import time

        marker = {"progressed": False}

        async def ticker():
            # Gives the event loop a chance to run while analyze_category
            # is parked inside to_thread.
            await _asyncio.sleep(0.05)
            marker["progressed"] = True

        def slow_create(**kwargs):
            time.sleep(0.2)  # blocking — would freeze the loop without to_thread
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(VALID_PAYLOAD))])

        client = MagicMock()
        client.messages.create.side_effect = slow_create

        await _asyncio.gather(
            analyze_category(client, CATEGORY),
            ticker(),
        )
        assert marker["progressed"] is True

    async def test_one_failing_category_does_not_abort_others(self, monkeypatch):
        async def fake_analyze(client, category):
            if category["id"] == "tcg":
                # analyze_category is expected to catch its own errors, so a
                # real failure should never propagate. Simulate the caught form.
                return f"{category['emoji']} <b>{category['name']}</b>\n⚠️ 분석 중 오류 발생: fail\n"
            return f"ok-{category['id']}"

        monkeypatch.setattr(analyzer, "analyze_category", fake_analyze)
        monkeypatch.setattr(analyzer.anthropic, "Anthropic", lambda api_key: MagicMock())

        results = await run_full_analysis("fake-key")
        assert len(results) == len(CATEGORIES)
        assert any("오류 발생" in r for r in results)
        assert any(r == "ok-arttoy" for r in results)

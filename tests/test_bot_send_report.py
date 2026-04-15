"""Tests for bot.send_report — ordering, rate limit, error path."""
from unittest.mock import AsyncMock, MagicMock, call

import pytest

import bot


@pytest.fixture
def mock_app():
    """An Application double whose bot.send_message is an AsyncMock."""
    app = MagicMock()
    app.bot = MagicMock()
    app.bot.send_message = AsyncMock()
    return app


@pytest.fixture(autouse=True)
def _patch_chat_id(monkeypatch):
    """send_report falls back to bot.CHAT_ID when no chat_id is passed."""
    monkeypatch.setattr(bot, "CHAT_ID", "42")
    monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", "sk-ant-test")


class TestSendReportHappyPath:
    async def test_sends_progress_then_header_then_categories_then_footer(
        self, mock_app, monkeypatch
    ):
        monkeypatch.setattr(bot, "build_header", lambda: "HEADER")
        monkeypatch.setattr(bot, "build_footer", lambda: "FOOTER")

        async def fake_run(api_key):
            assert api_key == "sk-ant-test"
            return ["CAT1", "CAT2", "CAT3"]

        monkeypatch.setattr(bot, "run_full_analysis", fake_run)
        # Skip the rate-limit sleeps to keep tests fast.
        monkeypatch.setattr(bot.asyncio, "sleep", AsyncMock())

        await bot.send_report(mock_app)

        texts = [c.kwargs["text"] for c in mock_app.bot.send_message.call_args_list]
        # Progress notice, header, 3 categories, footer = 6 messages total
        assert len(texts) == 6
        assert "분석 중" in texts[0]
        assert texts[1] == "HEADER"
        assert texts[2:5] == ["CAT1", "CAT2", "CAT3"]
        assert texts[5] == "FOOTER"

    async def test_all_messages_use_html_parse_mode(self, mock_app, monkeypatch):
        monkeypatch.setattr(bot, "build_header", lambda: "h")
        monkeypatch.setattr(bot, "build_footer", lambda: "f")
        monkeypatch.setattr(bot, "run_full_analysis", AsyncMock(return_value=["x"]))
        monkeypatch.setattr(bot.asyncio, "sleep", AsyncMock())

        await bot.send_report(mock_app)

        for c in mock_app.bot.send_message.call_args_list:
            assert c.kwargs.get("parse_mode") == "HTML"

    async def test_uses_explicit_chat_id_when_provided(self, mock_app, monkeypatch):
        monkeypatch.setattr(bot, "build_header", lambda: "h")
        monkeypatch.setattr(bot, "build_footer", lambda: "f")
        monkeypatch.setattr(bot, "run_full_analysis", AsyncMock(return_value=[]))
        monkeypatch.setattr(bot.asyncio, "sleep", AsyncMock())

        await bot.send_report(mock_app, chat_id="999")

        chat_ids = {c.kwargs["chat_id"] for c in mock_app.bot.send_message.call_args_list}
        assert chat_ids == {"999"}

    async def test_falls_back_to_default_chat_id(self, mock_app, monkeypatch):
        monkeypatch.setattr(bot, "build_header", lambda: "h")
        monkeypatch.setattr(bot, "build_footer", lambda: "f")
        monkeypatch.setattr(bot, "run_full_analysis", AsyncMock(return_value=[]))
        monkeypatch.setattr(bot.asyncio, "sleep", AsyncMock())

        await bot.send_report(mock_app)  # no chat_id

        for c in mock_app.bot.send_message.call_args_list:
            assert c.kwargs["chat_id"] == "42"

    async def test_sleeps_between_category_messages(self, mock_app, monkeypatch):
        monkeypatch.setattr(bot, "build_header", lambda: "h")
        monkeypatch.setattr(bot, "build_footer", lambda: "f")
        monkeypatch.setattr(
            bot, "run_full_analysis", AsyncMock(return_value=["a", "b", "c"])
        )
        sleep_mock = AsyncMock()
        monkeypatch.setattr(bot.asyncio, "sleep", sleep_mock)

        await bot.send_report(mock_app)

        # One sleep per category message for rate-limit protection
        assert sleep_mock.await_count == 3
        for c in sleep_mock.await_args_list:
            assert c.args[0] == 0.5


class TestSendReportErrorPath:
    async def test_exception_inside_analysis_is_caught_and_notified(
        self, mock_app, monkeypatch
    ):
        monkeypatch.setattr(bot, "build_header", lambda: "HEADER")

        async def blow_up(api_key):
            raise RuntimeError("claude down")

        monkeypatch.setattr(bot, "run_full_analysis", blow_up)
        monkeypatch.setattr(bot.asyncio, "sleep", AsyncMock())

        # Should NOT raise — send_report swallows and posts an error message
        await bot.send_report(mock_app)

        texts = [c.kwargs["text"] for c in mock_app.bot.send_message.call_args_list]
        # Final message is the error notice
        assert any("오류" in t and "claude down" in t for t in texts)
        # Still uses HTML parse mode for the error notice
        last = mock_app.bot.send_message.call_args_list[-1]
        assert last.kwargs["parse_mode"] == "HTML"

    async def test_exception_on_header_build_is_caught(self, mock_app, monkeypatch):
        def boom():
            raise ValueError("bad date")

        monkeypatch.setattr(bot, "build_header", boom)
        monkeypatch.setattr(bot, "run_full_analysis", AsyncMock(return_value=[]))
        monkeypatch.setattr(bot.asyncio, "sleep", AsyncMock())

        await bot.send_report(mock_app)  # must not raise
        texts = [c.kwargs["text"] for c in mock_app.bot.send_message.call_args_list]
        assert any("오류" in t for t in texts)

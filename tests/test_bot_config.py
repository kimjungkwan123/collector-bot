"""Tests for bot.validate_config."""
import pytest

import bot


class TestValidateConfig:
    def test_passes_when_all_set(self, monkeypatch):
        monkeypatch.setattr(bot, "BOT_TOKEN", "123:abc")
        monkeypatch.setattr(bot, "CHAT_ID", "42")
        monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", "sk-ant-xxx")
        # Should not raise
        bot.validate_config()

    def test_raises_when_bot_token_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(bot, "BOT_TOKEN", None)
        monkeypatch.setattr(bot, "CHAT_ID", "42")
        monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", "sk-ant-xxx")
        with pytest.raises(SystemExit) as exc:
            bot.validate_config()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "TELEGRAM_BOT_TOKEN" in out

    def test_raises_when_chat_id_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(bot, "BOT_TOKEN", "123:abc")
        monkeypatch.setattr(bot, "CHAT_ID", None)
        monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", "sk-ant-xxx")
        with pytest.raises(SystemExit):
            bot.validate_config()
        assert "TELEGRAM_CHAT_ID" in capsys.readouterr().out

    def test_raises_when_anthropic_key_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(bot, "BOT_TOKEN", "123:abc")
        monkeypatch.setattr(bot, "CHAT_ID", "42")
        monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", None)
        with pytest.raises(SystemExit):
            bot.validate_config()
        assert "ANTHROPIC_API_KEY" in capsys.readouterr().out

    def test_lists_all_missing_vars(self, monkeypatch, capsys):
        monkeypatch.setattr(bot, "BOT_TOKEN", None)
        monkeypatch.setattr(bot, "CHAT_ID", None)
        monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", None)
        with pytest.raises(SystemExit):
            bot.validate_config()
        out = capsys.readouterr().out
        assert "TELEGRAM_BOT_TOKEN" in out
        assert "TELEGRAM_CHAT_ID" in out
        assert "ANTHROPIC_API_KEY" in out

# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## Project Overview

`collector-bot` is a Korean-language Telegram bot that delivers a daily
reselling-market analysis report. Every day at a configured time it uses the
Anthropic Claude API to analyze 5 collectible categories (art toys, TCG /
Pokémon cards, collab goods, art prints, figures), picks the top investable
items under ₩1,000,000, and sends a formatted HTML report to a Telegram chat.

User-facing copy (prompts, command responses, logs, analysis output) is in
Korean. Keep it in Korean when editing — do not translate existing strings.

## Repository Layout

```
.
├── bot.py            # Telegram bot entry point + scheduler + command handlers
├── analyzer.py       # Claude-based analysis engine (categories, prompts, formatting)
├── setup.py          # Interactive first-run setup wizard (writes .env)
├── requirements.txt  # Pinned Python dependencies
├── Procfile          # `worker: python bot.py` (Heroku-style deploy)
├── railway.toml      # Railway deploy config (Nixpacks, python bot.py)
├── .env.example      # Template for required environment variables
└── .gitignore
```

There is no test suite, no package layout (flat modules), and no lint config.

## Architecture

Two-module design with a clear boundary:

- **`bot.py`** — Orchestration layer.
  - Loads env via `python-dotenv`, validates required keys in `validate_config()`.
  - Builds a `telegram.ext.Application`, registers 4 command handlers:
    `/start` (`cmd_start`), `/help` (`cmd_help`), `/status` (`cmd_status`),
    `/report` (`cmd_report`, triggers an immediate report).
  - Uses `AsyncIOScheduler` (timezone `Asia/Seoul`) to run `send_report` daily
    at `REPORT_HOUR:REPORT_MINUTE` via a cron trigger. The scheduler is started
    from `app.post_init` so it shares the bot's event loop.
  - `send_report(app, chat_id=None)` is the single code path used by both the
    scheduler and `/report`. It sends a "분석 중" notice, the header, one
    message per category (with `asyncio.sleep(0.5)` between sends to avoid
    Telegram rate limits), then the footer. All messages use `parse_mode="HTML"`.

- **`analyzer.py`** — Pure analysis + formatting, no Telegram coupling.
  - `CATEGORIES` — list of 5 category dicts (`id`, `name`, `emoji`, `keywords`).
    Adding/removing a category here automatically changes the report.
  - `ANALYSIS_PROMPT` — Korean prompt template that instructs Claude to return
    **strict JSON only** (`items[]` with `rank/name/price_range/price_trend/
    background/investment_point/forecast/score` plus `market_summary`).
  - `analyze_category()` — Calls `client.messages.create(model="claude-opus-4-5",
    max_tokens=2000, ...)`, strips ```` ```json ```` / ```` ``` ```` code
    fences if present, then `json.loads` the result. JSON or API errors are
    caught and returned as a user-visible `⚠️` fallback string (the bot never
    crashes on one bad category).
  - `run_full_analysis(api_key)` — Builds the Anthropic client and runs
    categories **sequentially** (not in parallel). Returns `list[str]` of
    pre-formatted HTML messages.
  - `format_category_report()`, `build_progress_bar()`, `format_trend_arrow()`,
    `build_header()`, `build_footer()` — all output uses Telegram-supported
    HTML tags only: `<b>`, `<i>`, `<code>`. Do **not** introduce Markdown or
    unsupported HTML tags.

- **`setup.py`** — Standalone interactive wizard. Prompts for bot token,
  Anthropic key, auto-detects Telegram `chat_id` via
  `https://api.telegram.org/bot{token}/getUpdates`, asks for schedule, writes
  `.env`, and sends a test message. Uses `aiohttp` directly rather than the
  `telegram` library. Not invoked by `bot.py`.

## Environment Variables

Required (validated at startup — bot exits with a Korean error if missing):

- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — target chat for scheduled reports
- `ANTHROPIC_API_KEY` — must start with `sk-ant-`

Optional (defaults shown):

- `REPORT_HOUR=9`
- `REPORT_MINUTE=0`

Timezone is hardcoded to `Asia/Seoul` in `bot.py:196`.

## Development Workflows

Local development:

```bash
pip install -r requirements.txt
python setup.py       # interactive first-run, creates .env (optional)
# or: cp .env.example .env   # then fill in manually
python bot.py         # starts long-polling + scheduler
```

Testing changes without waiting for the cron fire: send `/report` to the bot
in Telegram — it hits the same `send_report` code path as the scheduler.

Dependencies are pinned; keep them pinned when editing `requirements.txt`.

Deployment: Railway (`railway.toml`) or any Procfile-compatible host
(`worker: python bot.py`). `restartPolicyType = "ON_FAILURE"` with max 3
retries is configured on Railway.

## Conventions

- **Language.** Korean for all user-facing text (Telegram messages, prompt
  contents, console banners, logged `INFO` messages). Code identifiers and
  docstring summaries may be English or Korean — match the surrounding file.
- **Formatting.** Telegram HTML only. When adding new message blocks, reuse
  `build_header`/`build_footer`/`format_category_report` style (emoji prefix,
  `━━━━` divider lines, `<b>` for titles, `<i>` for quotes, `<code>` for
  monospace).
- **Claude model.** `analyzer.py` currently pins `model="claude-opus-4-5"`.
  If the user asks to upgrade models, update that string and keep
  `max_tokens=2000` unless they ask otherwise.
- **Prompt contract.** The JSON schema in `ANALYSIS_PROMPT` is load-bearing —
  `format_category_report` reads `rank / name / price_range / price_trend /
  background / investment_point / forecast / score / market_summary`. If you
  change field names in the prompt, update the formatter in the same commit.
- **Error handling.** Per-category failures must remain contained (return a
  `⚠️` string, don't raise) so one bad category doesn't abort the whole
  report. The top-level `send_report` also has a try/except that reports the
  error back to the chat.
- **Rate limiting.** Keep the `await asyncio.sleep(0.5)` between per-category
  sends in `bot.py:84`. Telegram will throttle aggressive bursts.
- **No parallel API calls.** `run_full_analysis` iterates sequentially. If you
  change this to `asyncio.gather`, note that `client.messages.create` is
  synchronous — you'd need `asyncio.to_thread` or the async Anthropic client.

## Things to Avoid

- Don't commit `.env` (already in `.gitignore`).
- Don't log `BOT_TOKEN` or `ANTHROPIC_API_KEY` values.
- Don't introduce Markdown parse mode — existing templates rely on HTML
  entities not being escaped.
- Don't add a test framework, lint config, or package layout unless asked;
  the project is intentionally flat.
- Don't translate existing Korean copy to English.

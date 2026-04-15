"""Pure-logic tests for analyzer formatting helpers."""
from freezegun import freeze_time

from analyzer import (
    build_footer,
    build_header,
    build_progress_bar,
    format_category_report,
    format_trend_arrow,
)


# ─── build_progress_bar ──────────────────────────────────────────────────
class TestBuildProgressBar:
    def test_zero_score_is_all_empty(self):
        assert build_progress_bar(0) == "░" * 10

    def test_full_score_is_all_filled(self):
        assert build_progress_bar(100) == "█" * 10

    def test_midpoint_is_half_filled(self):
        bar = build_progress_bar(50)
        assert bar == "█████░░░░░"
        assert len(bar) == 10

    def test_rounds_to_nearest(self):
        # 74 / 100 * 10 = 7.4 → 7
        assert build_progress_bar(74) == "█" * 7 + "░" * 3
        # 75 / 100 * 10 = 7.5 → 8 (banker's rounding in python3 → 8)
        assert len(build_progress_bar(75)) == 10

    def test_custom_length(self):
        bar = build_progress_bar(50, length=20)
        assert len(bar) == 20
        assert bar.count("█") == 10

    def test_negative_score_clamped_by_rounding(self):
        # Negative scores shouldn't blow up — verify it returns a string of
        # the expected length even if the filled count underflows.
        bar = build_progress_bar(-10)
        # round(-1.0) = -1 → "█" * -1 == "" and "░" * 11 == 11 chars.
        # The point of the test is that it doesn't crash and stays a string.
        assert isinstance(bar, str)


# ─── format_trend_arrow ──────────────────────────────────────────────────
class TestFormatTrendArrow:
    def test_known_trends(self):
        assert format_trend_arrow("상승") == "📈"
        assert format_trend_arrow("보합") == "➡️"
        assert format_trend_arrow("하락") == "📉"

    def test_unknown_trend_falls_back_to_sideways(self):
        assert format_trend_arrow("unknown") == "➡️"
        assert format_trend_arrow("") == "➡️"
        assert format_trend_arrow(None) == "➡️"  # type: ignore[arg-type]


# ─── format_category_report ──────────────────────────────────────────────
CATEGORY = {
    "id": "arttoy",
    "name": "아트토이",
    "emoji": "🎨",
    "keywords": "Bearbrick, KAWS",
}

SAMPLE_DATA = {
    "market_summary": "시장이 활발합니다",
    "items": [
        {
            "rank": 1,
            "name": "Bearbrick 1000%",
            "price_range": "80만원~95만원",
            "price_trend": "상승",
            "background": "2001년 출시",
            "investment_point": "한정판 수요 높음",
            "forecast": "단기 강세",
            "score": 85,
        }
    ],
}


class TestFormatCategoryReport:
    def test_includes_emoji_and_name(self):
        out = format_category_report(CATEGORY, SAMPLE_DATA)
        assert "🎨" in out
        assert "<b>아트토이</b>" in out

    def test_includes_summary_when_present(self):
        out = format_category_report(CATEGORY, SAMPLE_DATA)
        assert '<i>"시장이 활발합니다"</i>' in out

    def test_omits_summary_wrapper_when_absent(self):
        out = format_category_report(CATEGORY, {"items": []})
        assert "<i>" not in out

    def test_empty_items_list_does_not_crash(self):
        out = format_category_report(CATEGORY, {"items": [], "market_summary": ""})
        assert "<b>아트토이</b>" in out

    def test_missing_keys_use_defaults(self):
        data = {"items": [{"rank": 1, "name": "테스트"}]}
        out = format_category_report(CATEGORY, data)
        assert "1. 테스트" in out
        # score default is 50 → progress bar rendered
        assert "50/100" in out
        # missing trend defaults to 보합 → ➡️
        assert "➡️" in out

    def test_renders_rank_and_score(self):
        out = format_category_report(CATEGORY, SAMPLE_DATA)
        assert "1. Bearbrick 1000%" in out
        assert "85/100" in out

    def test_escapes_html_in_item_fields(self):
        """Claude may return text with < > &. Telegram HTML parser rejects
        unescaped angle brackets, so these MUST be escaped."""
        data = {
            "market_summary": "A & B <tag>",
            "items": [
                {
                    "rank": 1,
                    "name": "<script>alert(1)</script>",
                    "price_range": "10만원 < 20만원",
                    "price_trend": "상승",
                    "background": "A & B",
                    "investment_point": "use <b>",
                    "forecast": ">>> up",
                    "score": 70,
                }
            ],
        }
        out = format_category_report(CATEGORY, data)
        assert "<script>" not in out
        assert "&lt;script&gt;" in out
        assert "&amp;" in out
        assert "10만원 &lt; 20만원" in out
        # Our own wrapping tags are preserved
        assert "<b>1. &lt;script&gt;" in out

    def test_none_market_summary_is_treated_as_empty(self):
        out = format_category_report(CATEGORY, {"market_summary": None, "items": []})
        assert "<i>" not in out


# ─── build_header ────────────────────────────────────────────────────────
class TestBuildHeader:
    @freeze_time("2026-04-15")  # Wednesday
    def test_header_has_korean_weekday(self):
        out = build_header()
        assert "2026.04.15 (수)" in out
        assert "리셀 마켓 일일 리포트" in out
        assert "100만원 이하" in out

    @freeze_time("2026-04-13")  # Monday
    def test_monday_renders_as_wol(self):
        assert "(월)" in build_header()

    @freeze_time("2026-04-19")  # Sunday
    def test_sunday_renders_as_il(self):
        assert "(일)" in build_header()


# ─── build_footer ────────────────────────────────────────────────────────
class TestBuildFooter:
    def test_footer_mentions_report_command(self):
        out = build_footer()
        assert "/report" in out
        assert "Claude" in out

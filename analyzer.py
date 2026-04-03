"""
리셀 마켓 분석 엔진 — Claude AI를 사용해 카테고리별 Top 아이템 분석
"""
import anthropic
import os
from datetime import datetime

CATEGORIES = [
    {
        "id": "arttoy",
        "name": "아트토이",
        "emoji": "🎨",
        "keywords": "Bearbrick, KAWS, Medicom Toy, 스트리트 아트 피규어, 한정판 아트토이",
    },
    {
        "id": "tcg",
        "name": "TCG / 포켓몬 카드",
        "emoji": "🃏",
        "keywords": "포켓몬 카드, 유희왕, MTG, 한정판 카드팩, PSA 등급 카드",
    },
    {
        "id": "collab",
        "name": "콜라보 굿즈",
        "emoji": "🤝",
        "keywords": "브랜드 콜라보, 스트릿웨어, 슈프림, 나이키 콜라보, 한정판 굿즈",
    },
    {
        "id": "artprint",
        "name": "아트 프린트",
        "emoji": "🖼️",
        "keywords": "한정판 아트 프린트, 스크린 프린트, 뱅크시, 팝아트 포스터, 아트 에디션",
    },
    {
        "id": "figure",
        "name": "피규어",
        "emoji": "🗿",
        "keywords": "1/6 피규어, 핫토이, 굿스마일, 넨도로이드, 한정판 피규어",
    },
]

ANALYSIS_PROMPT = """당신은 한국 리셀 마켓 전문 애널리스트입니다.
오늘 날짜: {date}
분석 카테고리: {category_name} ({keywords})

다음 작업을 수행해주세요:

1. 현재 한국 리셀 시장에서 **{category_name}** 카테고리의 최신 트렌드를 분석합니다.
2. 100만원 이하 가격대에서 투자 가치가 높은 아이템을 **정확히 3개** 선정합니다.
3. 각 아이템에 대해 다음 형식으로 출력해주세요:

각 아이템은 다음 JSON 형식으로 출력:
{{
  "items": [
    {{
      "rank": 1,
      "name": "아이템 전체 이름",
      "price_range": "XX만원~XX만원",
      "price_trend": "상승" | "보합" | "하락",
      "background": "이 아이템의 역사/배경 2-3문장",
      "investment_point": "리셀 투자 포인트 2-3문장",
      "forecast": "단기(1-3개월) 및 장기(6개월+) 전망 2문장",
      "score": 75  // 0-100 투자 매력도 점수
    }}
  ],
  "market_summary": "이번 주 {category_name} 시장 전반 동향 1-2문장"
}}

중요:
- 실제로 존재하는 아이템만 선정하세요
- 가격은 한국 리셀 시장 기준 (크림, 번개장터, 솔드아웃 등)
- 반드시 JSON 형식으로만 출력하세요 (다른 텍스트 없이)
"""

def build_progress_bar(score: int, length: int = 10) -> str:
    """점수를 진행바로 변환 (0-100 → ████░░░░░░)"""
    filled = round(score / 100 * length)
    return "█" * filled + "░" * (length - filled)

def format_trend_arrow(trend: str) -> str:
    arrows = {"상승": "📈", "보합": "➡️", "하락": "📉"}
    return arrows.get(trend, "➡️")

def format_category_report(category: dict, analysis_data: dict) -> str:
    """카테고리 분석 결과를 텔레그램 메시지 형식으로 변환"""
    emoji = category["emoji"]
    name = category["name"]
    summary = analysis_data.get("market_summary", "")
    items = analysis_data.get("items", [])

    lines = []
    lines.append(f"{emoji} <b>{name}</b>")
    if summary:
        lines.append(f'<i>"{summary}"</i>')
    lines.append("")

    for item in items:
        rank = item.get("rank", "")
        item_name = item.get("name", "")
        price = item.get("price_range", "")
        trend = item.get("price_trend", "보합")
        background = item.get("background", "")
        invest = item.get("investment_point", "")
        forecast = item.get("forecast", "")
        score = item.get("score", 50)
        bar = build_progress_bar(score)
        arrow = format_trend_arrow(trend)

        lines.append(f"<b>{rank}. {item_name}</b>  ✅")
        lines.append(f"   💴 {price}  {arrow}")
        lines.append(f"   📖 {background}")
        lines.append(f"   💡 {invest}")
        lines.append(f"   🔮 {forecast}")
        lines.append(f"   전망 [{bar}] {score}/100")
        lines.append("")

    return "\n".join(lines)

async def analyze_category(client: anthropic.Anthropic, category: dict) -> str:
    """단일 카테고리 분석 수행"""
    import json

    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = ANALYSIS_PROMPT.format(
        date=today,
        category_name=category["name"],
        keywords=category["keywords"],
    )

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()

        # JSON 파싱
        # 코드블록이 있으면 제거
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        data = json.loads(raw)
        return format_category_report(category, data)

    except json.JSONDecodeError as e:
        return f"{category['emoji']} <b>{category['name']}</b>\n⚠️ 분석 데이터 파싱 오류: {e}\n"
    except Exception as e:
        return f"{category['emoji']} <b>{category['name']}</b>\n⚠️ 분석 중 오류 발생: {e}\n"

async def run_full_analysis(api_key: str) -> list[str]:
    """전체 카테고리 분석 실행 — 카테고리별 메시지 리스트 반환"""
    client = anthropic.Anthropic(api_key=api_key)
    results = []

    for category in CATEGORIES:
        print(f"  분석 중: {category['emoji']} {category['name']}...")
        report = await analyze_category(client, category)
        results.append(report)

    return results

def build_header() -> str:
    today = datetime.now().strftime("%Y.%m.%d (%a)")
    weekday_map = {
        "Mon": "월", "Tue": "화", "Wed": "수",
        "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"
    }
    for eng, kor in weekday_map.items():
        today = today.replace(eng, kor)

    return (
        f"📊 <b>리셀 마켓 일일 리포트</b>\n"
        f"<code>{today}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 기준: 100만원 이하 | 투자가치 상위 아이템\n"
    )

def build_footer() -> str:
    return (
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Powered by Claude AI\n"
        "/report 로 즉시 새 리포트 요청 가능"
    )

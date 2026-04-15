"""
캐주얼 스포츠 대회 수집 엔진 — Claude AI로 하이록스/마라톤/펀런 등
재미있는 스포츠 이벤트를 카테고리별로 모아줍니다.
"""
import anthropic
import json
from datetime import datetime


SPORTS_CATEGORIES = [
    {
        "id": "hyrox",
        "name": "하이록스 & 피트니스 레이스",
        "emoji": "🏋️",
        "keywords": "Hyrox, DEKA, CrossFit 오픈, 피트니스 챌린지, 기능성 스포츠 대회",
    },
    {
        "id": "marathon",
        "name": "마라톤 & 러닝",
        "emoji": "🏃",
        "keywords": "서울 마라톤, 하프 마라톤, 10K, 풀코스, 트레일 러닝",
    },
    {
        "id": "funrun",
        "name": "펀런 & 테마런",
        "emoji": "🎉",
        "keywords": "포켓몬 런, 컬러런, 좀비런, 야간 런, 코스프레 런, 디즈니 런",
    },
    {
        "id": "obstacle",
        "name": "장애물 & 익스트림",
        "emoji": "🧗",
        "keywords": "스파르탄 레이스, 터프 머더, OCR, 장애물 경주, 익스트림 챌린지",
    },
    {
        "id": "cycle_swim",
        "name": "자전거 & 수영 & 철인",
        "emoji": "🚴",
        "keywords": "그란폰도, 한강 라이딩, 오픈워터 스윔, 트라이애슬론, 아쿠아슬론",
    },
]


EVENTS_PROMPT = """당신은 한국 아마추어 스포츠 이벤트 큐레이터입니다.
오늘 날짜: {date}
카테고리: {category_name} ({keywords})

다음 작업을 수행해주세요:

1. 한국에서 열리는 (또는 한국인이 쉽게 참가할 수 있는) **{category_name}** 카테고리의
   다가오는 캐주얼/아마추어 대회를 **정확히 3개** 선정합니다.
2. 가능한 한 최근 개최/예정인 실제 대회를 선정해주세요. 확실하지 않다면
   매년 정기적으로 열리는 시리즈 대회를 소개해도 좋습니다.
3. 초보자~중급자도 부담 없이 참가할 수 있는 이벤트를 우선합니다.

출력 형식 (JSON만, 다른 텍스트 금지):
{{
  "events": [
    {{
      "rank": 1,
      "name": "대회 정식 이름",
      "date": "YYYY.MM.DD 또는 YYYY년 MM월 (예정)",
      "location": "도시 / 구체 장소",
      "distance": "코스 / 거리 / 종목 요약",
      "level": "입문" | "중급" | "고급",
      "highlight": "이 대회만의 매력 포인트 2문장",
      "vibe": "분위기 한 줄 요약 (예: '친구랑 가기 좋음', '코스튬 필수')",
      "registration": "신청 방법/사이트 힌트 (예: '공식 홈페이지', '굿러닝')",
      "fun_score": 80  // 0-100 재미 지수
    }}
  ],
  "category_tip": "이 카테고리 입문자를 위한 팁 1-2문장"
}}

중요:
- 반드시 JSON으로만 출력
- 실제로 존재하거나 정기적으로 열리는 대회 위주
- 상업 광고가 아닌 참가자 관점에서 서술
"""


def build_fun_bar(score: int, length: int = 10) -> str:
    filled = round(score / 100 * length)
    return "★" * filled + "☆" * (length - filled)


def level_badge(level: str) -> str:
    return {"입문": "🟢 입문", "중급": "🟡 중급", "고급": "🔴 고급"}.get(level, "⚪ 누구나")


def format_events_report(category: dict, data: dict) -> str:
    emoji = category["emoji"]
    name = category["name"]
    tip = data.get("category_tip", "")
    events = data.get("events", [])

    lines = [f"{emoji} <b>{name}</b>"]
    if tip:
        lines.append(f"<i>💬 {tip}</i>")
    lines.append("")

    for ev in events:
        rank = ev.get("rank", "")
        ev_name = ev.get("name", "")
        date = ev.get("date", "")
        location = ev.get("location", "")
        distance = ev.get("distance", "")
        level = level_badge(ev.get("level", ""))
        highlight = ev.get("highlight", "")
        vibe = ev.get("vibe", "")
        reg = ev.get("registration", "")
        score = ev.get("fun_score", 50)
        bar = build_fun_bar(score)

        lines.append(f"<b>{rank}. {ev_name}</b>")
        lines.append(f"   📅 {date}")
        lines.append(f"   📍 {location}")
        lines.append(f"   🏁 {distance}  |  {level}")
        if highlight:
            lines.append(f"   ✨ {highlight}")
        if vibe:
            lines.append(f"   🎈 {vibe}")
        if reg:
            lines.append(f"   📝 {reg}")
        lines.append(f"   재미 [{bar}] {score}/100")
        lines.append("")

    return "\n".join(lines)


async def fetch_category_events(client: anthropic.Anthropic, category: dict) -> str:
    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = EVENTS_PROMPT.format(
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

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        data = json.loads(raw)
        return format_events_report(category, data)

    except json.JSONDecodeError as e:
        return f"{category['emoji']} <b>{category['name']}</b>\n⚠️ 데이터 파싱 오류: {e}\n"
    except Exception as e:
        return f"{category['emoji']} <b>{category['name']}</b>\n⚠️ 수집 중 오류: {e}\n"


async def run_sports_events_collection(api_key: str) -> list[str]:
    """전체 스포츠 대회 카테고리 수집 — 카테고리별 메시지 리스트 반환"""
    client = anthropic.Anthropic(api_key=api_key)
    results = []

    for category in SPORTS_CATEGORIES:
        print(f"  수집 중: {category['emoji']} {category['name']}...")
        report = await fetch_category_events(client, category)
        results.append(report)

    return results


def build_sports_header() -> str:
    today = datetime.now().strftime("%Y.%m.%d (%a)")
    weekday_map = {
        "Mon": "월", "Tue": "화", "Wed": "수",
        "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일",
    }
    for eng, kor in weekday_map.items():
        today = today.replace(eng, kor)

    return (
        f"🏆 <b>캐주얼 스포츠 대회 모음</b>\n"
        f"<code>{today}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏃 하이록스 · 마라톤 · 펀런 · 장애물 · 철인까지\n"
        f"🎯 초보~중급자 눈높이로 큐레이션\n"
    )


def build_sports_footer() -> str:
    return (
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Powered by Claude AI\n"
        "/sports 로 최신 대회 목록 다시 받기"
    )

#!/usr/bin/env python3
"""
리셀 마켓 텔레그램 봇 초기 설정 스크립트
"""
import os
import asyncio
import sys

def print_banner():
    print("\n" + "="*55)
    print("  📦 리셀 마켓 분석 봇 — 초기 설정")
    print("="*55 + "\n")

def check_env_file():
    if os.path.exists(".env"):
        print("⚠️  .env 파일이 이미 존재합니다.")
        overwrite = input("   덮어쓰시겠어요? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("   설정을 취소했습니다.")
            sys.exit(0)

def get_telegram_token():
    print("━"*55)
    print("① 텔레그램 봇 토큰 설정")
    print("━"*55)
    print("""
  아직 봇이 없으신가요?
  1. 텔레그램에서 @BotFather 검색 & 시작
  2. /newbot 입력
  3. 봇 이름 입력 (예: 내리셀봇)
  4. 봇 username 입력 (예: myresell_bot) — 반드시 '_bot'으로 끝나야 함
  5. 발급된 토큰 복사 (예: 1234567890:ABCdef...)
""")
    while True:
        token = input("  봇 토큰을 붙여넣으세요: ").strip()
        if ':' in token and len(token) > 20:
            print(f"  ✅ 토큰 확인: {token[:10]}...{token[-5:]}")
            return token
        print("  ❌ 올바른 형식이 아닙니다. 다시 입력해주세요.")

def get_anthropic_key():
    print("\n━"*55)
    print("② Anthropic API 키 설정")
    print("━"*55)
    print("""
  API 키 발급 방법:
  https://console.anthropic.com → API Keys → Create Key
""")
    while True:
        key = input("  Anthropic API 키를 붙여넣으세요: ").strip()
        if key.startswith("sk-ant-"):
            print(f"  ✅ API 키 확인: {key[:12]}...{key[-4:]}")
            return key
        print("  ❌ 'sk-ant-'로 시작하는 키를 입력해주세요.")

async def get_chat_id(token):
    print("\n━"*55)
    print("③ Chat ID 자동 감지")
    print("━"*55)
    print("""
  Chat ID를 가져오는 법:
  1. 텔레그램에서 방금 만든 봇을 찾아 /start 메시지 전송
  2. 아래 [Enter] 키를 누르면 자동으로 Chat ID를 가져옵니다
""")
    input("  봇에 /start 보내셨으면 Enter 누르세요...")

    try:
        import aiohttp
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()

        if data.get("ok") and data.get("result"):
            updates = data["result"]
            if updates:
                chat_id = updates[-1]["message"]["chat"]["id"]
                chat_name = updates[-1]["message"]["chat"].get("first_name", "사용자")
                print(f"  ✅ Chat ID 감지: {chat_id} ({chat_name}님)")
                return str(chat_id)
            else:
                print("  ⚠️  메시지를 찾을 수 없습니다.")
        else:
            print("  ⚠️  업데이트를 가져올 수 없습니다.")
    except Exception as e:
        print(f"  ⚠️  자동 감지 실패: {e}")

    print("\n  수동으로 Chat ID를 입력해주세요.")
    print("  (텔레그램에서 @userinfobot 에 /start 를 보내면 확인 가능)")
    return input("  Chat ID: ").strip()

def get_schedule():
    print("\n━"*55)
    print("④ 리포트 발송 시간 설정")
    print("━"*55)
    print("  기본값: 매일 오전 09:00\n")
    custom = input("  변경하시겠어요? (y/N): ").strip().lower()
    if custom == 'y':
        while True:
            try:
                time_str = input("  발송 시간 입력 (HH:MM, 예: 08:30): ").strip()
                h, m = map(int, time_str.split(":"))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    print(f"  ✅ 매일 {h:02d}:{m:02d}에 발송됩니다.")
                    return h, m
            except:
                pass
            print("  ❌ 올바른 시간 형식이 입력해주세요 (HH:MM)")
    return 9, 0

def save_env(token, api_key, chat_id, hour, minute):
    content = f"""# 리셀 마켓 분석 봇 설정
TELEGRAM_BOT_TOKEN={token}
TELEGRAM_CHAT_ID={chat_id}
ANTHROPIC_API_KEY={api_key}
REPORT_HOUR={hour}
REPORT_MINUTE={minute}
"""
    with open(".env", "w") as f:
        f.write(content)
    print("\n  ✅ .env 파일 저장 완료!")

async def send_test_message(token, chat_id):
    print("\n━"*55)
    print("⑤ 테스트 메시지 발송")
    print("━"*55)
    try:
        import aiohttp
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "✅ 리셀 마켓 분석 봇 설정 완료!\n\n매일 리포트가 이 채팅으로 발송됩니다.\n\n/report — 즉시 리포트 받기\n/help — 도움말",
            "parse_mode": "HTML"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    print("  ✅ 테스트 메시지 발송 성공!")
                    return True
    except Exception as e:
        print(f"  ⚠️  테스트 메시지 실패: {e}")
    return False

async def main():
    print_banner()
    check_env_file()

    token = get_telegram_token()
    api_key = get_anthropic_key()
    chat_id = await get_chat_id(token)
    hour, minute = get_schedule()

    save_env(token, api_key, chat_id, hour, minute)
    await send_test_message(token, chat_id)

    print("\n" + "="*55)
    print("  🎉 설정완료!")
    print("="*55)
    print(f"""
  이제 �햄시구 봇을 실행하세요:

    python bot.py

  봇이 실행되면:
  • 매일 {hour:02d}:{minute:02d}에 리포트 자동 발송
  • /report 명령으로 즉시 리포트 요청 가능
  • /help 로 전체 명령어 확인
""")

if __name__ == "__main__":
    asyncio.run(main())

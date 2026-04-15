#!/usr/bin/env python3
"""
리셀 마켓 분석 텔레그램 봇
매일 지정된 시간에 Claude AI 기반 리셀 마켓 리포트를 텔레그램으로 발송합니다.

실행: python bot.py
"""
import asyncio
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from analyzer import run_full_analysis, build_header, build_footer
from sports_events import (
    run_sports_events_collection,
    build_sports_header,
    build_sports_footer,
)

# ─── 환경 변수 로드 ────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
REPORT_HOUR = int(os.getenv("REPORT_HOUR", "9"))
REPORT_MINUTE = int(os.getenv("REPORT_MINUTE", "0"))

# ─── 로깅 설정 ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── 설정 검증 ─────────────────────────────────────────────────
def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"\n❌ .env 파일에 다음 항목이 없습니다: {', '.join(missing)}")
        print("   먼저 python setup.py 를 실행해주세요.\n")
        raise SystemExit(1)


# ─── 리포트 발송 핵심 함수 ────────────────────────────────────
async def send_report(app: Application, chat_id: str = None):
    """리포트 생성 & 텔레그램 발송"""
    target = chat_id or CHAT_ID
    logger.info("리포트 생성 시작...")

    # 시작 알림
    await app.bot.send_message(
        chat_id=target,
        text="⏳ 리셀 마켓 분석 중입니다... (약 1~2분 소요)",
        parse_mode="HTML",
    )

    try:
        # 헤더 발송
        header = build_header()
        await app.bot.send_message(chat_id=target, text=header, parse_mode="HTML")

        # 카테고리별 분석 실행 & 순차 발송
        category_reports = await run_full_analysis(ANTHROPIC_API_KEY)

        for report in category_reports:
            await app.bot.send_message(
                chat_id=target,
                text=report,
                parse_mode="HTML",
            )
            await asyncio.sleep(0.5)  # 텔레그램 rate limit 방지

        # 푸터 발송
        footer = build_footer()
        await app.bot.send_message(chat_id=target, text=footer, parse_mode="HTML")

        logger.info("리포트 발송 완료!")

    except Exception as e:
        logger.error(f"리포트 생성 오류: {e}")
        await app.bot.send_message(
            chat_id=target,
            text=f"⚠️ 리포트 생성 중 오류가 발생했습니다.\n<code>{e}</code>",
            parse_mode="HTML",
        )


# ─── 텔레그램 커맨드 핸들러 ──────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/start' 커맨드"""
    user = update.effective_user
    text = (
        f"안녕하세요, {user.first_name}님! 👋\n\n"
        f"📊 <b>리셀 마켓 분석 봇</b>입니다.\n\n"
        f"매일 <b>{REPORT_HOUR:02d}:{REPORT_MINUTE:02d}</b>에 5개 카테고리 리포트를 자동 발송합니다.\n\n"
        f"<b>커맨드 목록:</b>\n"
        f"/report — 즉시 리셀 리포트 받기\n"
        f"/sports — 캐주얼 스포츠 대회 모음 (하이록스·마라톤·펀런 등)\n"
        f"/status — 봇 상태 확인\n"
        f"/help — 도움말\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/help' 커맨드"""
    text = (
        "📖 <b>컬렉터 봇 도움말</b>\n\n"
        "<b>커맨드:</b>\n"
        "/start — 봇 시작\n"
        "/report — 리셀 마켓 리포트 즉시 요청\n"
        "/sports — 캐주얼 스포츠 대회 모음 요청\n"
        "/status — 봇 상태 & 다음 발송 시간\n"
        "/help — 이 도움말\n\n"
        "<b>💰 리셀 분석 카테고리:</b>\n"
        "🎨 아트토이\n"
        "🃏 TCG / 포켓몬 카드\n"
        "🤝 콜라보 굿즈\n"
        "🖼️ 아트 프린트\n"
        "🗿 피규어\n\n"
        "<b>🏆 스포츠 대회 카테고리:</b>\n"
        "🏋️ 하이록스 & 피트니스 레이스\n"
        "🏃 마라톤 & 러닝\n"
        "🎉 펀런 & 테마런 (포켓몬 런, 컬러런 등)\n"
        "🧗 장애물 & 익스트림\n"
        "🚴 자전거 · 수영 · 철인\n\n"
        "<b>기준:</b> 리셀은 100만원 이하 / 스포츠는 입문~중급자"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/status' 커맨드 — 봇 상태 & 다음 발송 시간"""
    now = datetime.now()
    next_run_str = f"매일 {REPORT_HOUR:02d}:{REPORT_MINUTE:02d}"

    text = (
        "✅ <b>봇 정상 작동 중</b>\n\n"
        f"🕐 현재 시각: <code>{now.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        f"⏰ 자동 발송: <code>{next_run_str}</code>\n"
        f"🤖 AI 모델: Claude Opus\n"
        f"📦 분석 카테고리: 5개"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/report' 커맨드 — 즉시 리포트 생성"""
    logger.info(f"/report 요청: {update.effective_user.username}")
    await send_report(context.application, chat_id=str(update.effective_chat.id))


async def send_sports_events(app: Application, chat_id: str):
    """캐주얼 스포츠 대회 목록 생성 & 발송"""
    logger.info("스포츠 대회 수집 시작...")

    await app.bot.send_message(
        chat_id=chat_id,
        text="⏳ 캐주얼 스포츠 대회를 수집 중입니다... (약 1~2분 소요)",
        parse_mode="HTML",
    )

    try:
        header = build_sports_header()
        await app.bot.send_message(chat_id=chat_id, text=header, parse_mode="HTML")

        category_reports = await run_sports_events_collection(ANTHROPIC_API_KEY)

        for report in category_reports:
            await app.bot.send_message(
                chat_id=chat_id,
                text=report,
                parse_mode="HTML",
            )
            await asyncio.sleep(0.5)

        footer = build_sports_footer()
        await app.bot.send_message(chat_id=chat_id, text=footer, parse_mode="HTML")

        logger.info("스포츠 대회 목록 발송 완료!")

    except Exception as e:
        logger.error(f"스포츠 대회 수집 오류: {e}")
        await app.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ 대회 수집 중 오류가 발생했습니다.\n<code>{e}</code>",
            parse_mode="HTML",
        )


async def cmd_sports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/sports' 커맨드 — 캐주얼 스포츠 대회 목록 받기"""
    logger.info(f"/sports 요청: {update.effective_user.username}")
    await send_sports_events(
        context.application,
        chat_id=str(update.effective_chat.id),
    )


# ─── 스케줄러 작업 ────────────────────────────────────────────
def schedule_daily_report(app: Application, scheduler: AsyncIOScheduler):
    """매일 지정 시간에 리포트 발송 스케줄 등록"""
    scheduler.add_job(
        send_report,
        trigger="cron",
        hour=REPORT_HOUR,
        minute=REPORT_MINUTE,
        kwargs={"app": app},
        id="daily_report",
        replace_existing=True,
    )
    logger.info(f"스케줄 등록: 매일 {REPORT_HOUR:02d}:{REPORT_MINUTE:02d}")


# ─── 메인 ─────────────────────────────────────────────────────
def main():
    validate_config()

    print("\n" + "="*50)
    print("  📊 리셀 마켓 분석 봇 시작")
    print("="*50)
    print(f"  ⏰ 자동 발송: 매일 {REPORT_HOUR:02d}:{REPORT_MINUTE:02d}")
    print(f"  📱 Chat ID: {CHAT_ID}")
    print(f"  🤖 AI: Claude Opus")
    print("="*50)
    print("  종료: Ctrl+C\n")

    # 앱 빌드
    app = Application.builder().token(BOT_TOKEN).build()

    # 커맨드 핸들러 등록
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("sports", cmd_sports))

    # 스케줄러 설정
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    schedule_daily_report(app, scheduler)

    # 봇 실행 (post_init으로 스케줄러 시작)
    async def post_init(application: Application):
        scheduler.start()
        logger.info("스케줄러 시작됨")

    app.post_init = post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

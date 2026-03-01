"""
run_pipeline.py — US Market Agent 전체 파이프라인 진입점

실행 순서:
  1. 시장 데이터 수집
  2. 에이전트 초기화 (TechMo / MacroFed / SectorRot / ValueFund)
  3. Phase 1+2 토론 실행 (DebateEngine)
  4. Phase 3 종합 판단 (Moderator)
  5. 백테스트 (전일 예측 vs 실제 S&P500 등락 비교)
  6. 보고서 저장 (docs/data/daily_report.json + data/history/)
  7. Telegram 알림 (선택)
"""
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

import anthropic

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents import (
    TechMomentumAgent,
    MacroFedAgent,
    SectorRotationAgent,
    ValueFundamentalAgent,
)
from orchestrator.debate_engine import DebateEngine
from orchestrator.moderator     import Moderator
from orchestrator.backtester    import Backtester
from scripts.collect_data       import collect_market_data

# ─── 설정 ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO,
    format  = "%(asctime)s %(levelname)-8s %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODEL        = "claude-opus-4-5-20251101"
PAGES_URL    = "https://jinhae8971.github.io/us-market-agent/"
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


# ─── Telegram 알림 ────────────────────────────────────────────────────────────

def send_telegram(verdict: dict, date_str: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram 설정 없음 — 알림 건너뜀")
        return
    import requests
    stance_emoji = {
        "BUY":  "🟢",
        "HOLD": "🟡",
        "SELL": "🔴",
    }.get(verdict.get("final_stance", "HOLD"), "⚪")
    weather_icon = verdict.get("market_weather_icon", "⛅")
    votes = verdict.get("stance_votes", {})
    votes_str = "  ".join(f"{name}: {s}" for name, s in votes.items())

    risk_str  = "\n".join(f"  • {r}" for r in verdict.get("risk_factors", [])[:2])
    insight_str = "\n".join(f"  • {i}" for i in verdict.get("key_insights", [])[:2])

    msg = (
        f"🇺🇸 <b>US Market Agent — {date_str}</b>\n\n"
        f"{weather_icon} {verdict.get('market_weather_en', '')}\n"
        f"{stance_emoji} 최종 판단: <b>{verdict.get('final_stance', 'HOLD')}</b> "
        f"(확신도 {verdict.get('confidence_score', 50)}%)\n\n"
        f"📊 에이전트 투표\n  {votes_str}\n\n"
        f"📌 <b>핵심 인사이트</b>\n{insight_str}\n\n"
        f"⚠️ <b>리스크</b>\n{risk_str}\n\n"
        f"📋 <b>요약</b>\n{verdict.get('summary', '')[:250]}"
    )
    if PAGES_URL:
        msg += f"\n\n📎 <a href='{PAGES_URL}'>대시보드 보기</a>"

    try:
        import requests
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "text":       msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        resp.raise_for_status()
        logger.info("Telegram 알림 전송 완료")
    except Exception as e:
        logger.warning(f"Telegram 전송 실패: {e}")


# ─── 메인 파이프라인 ──────────────────────────────────────────────────────────

def main() -> dict:
    logger.info("=" * 60)
    logger.info("US Market Agent 파이프라인 시작")
    logger.info("=" * 60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

    client    = anthropic.Anthropic(api_key=api_key)
    today_str = date.today().strftime("%Y-%m-%d")

    # ── Step 1: 데이터 수집 ────────────────────────────────────────────────────
    logger.info("Step 1: 시장 데이터 수집")
    market_data = collect_market_data()

    # ── Step 2: 에이전트 초기화 ────────────────────────────────────────────────
    logger.info("Step 2: 에이전트 초기화")
    agents = [
        TechMomentumAgent(client, MODEL),    # idx 0 — 기술적 모멘텀
        MacroFedAgent(client, MODEL),         # idx 1 — Fed·거시경제
        SectorRotationAgent(client, MODEL),   # idx 2 — 섹터 로테이션
        ValueFundamentalAgent(client, MODEL), # idx 3 — 가치·펀더멘털
    ]
    logger.info(f"  에이전트: {[a.name for a in agents]}")

    # ── Step 3: 토론 (Phase 1+2) ───────────────────────────────────────────────
    logger.info("Step 3: 토론 실행 (Phase 1 독립 분석 + Phase 2 교차 반론)")
    engine       = DebateEngine(agents)
    debate_result = engine.run(market_data)
    logger.info(f"  Phase 1 분석 {len(debate_result['phase1_reports'])}건, "
                f"Phase 2 반론 {len(debate_result['phase2_critiques'])}건 완료")

    # ── Step 4: Moderator (Phase 3) ────────────────────────────────────────────
    logger.info("Step 4: Moderator 종합 판단 (Phase 3)")
    moderator = Moderator(client, MODEL)
    verdict   = moderator.synthesize(
        reports     = debate_result["phase1_reports"],
        critiques   = debate_result["phase2_critiques"],
        market_data = market_data,
    )
    logger.info(
        f"  최종 판단: {verdict['final_stance']} "
        f"(확신도 {verdict['confidence_score']}%) "
        f"— {verdict.get('market_weather_icon','')} {verdict.get('market_weather_en','')}"
    )

    # ── Step 5: 백테스트 ───────────────────────────────────────────────────────
    logger.info("Step 5: 백테스트 (전일 예측 vs 실제 S&P500)")
    data_dir  = ROOT / "data"
    backtester = Backtester(data_dir=str(data_dir))

    sp500_change = (
        market_data.get("indices", {})
        .get("SP500", {})
        .get("change_pct", 0.0)
    )
    backtest_result = backtester.run(sp500_change)
    today_moderator = backtest_result.get("today_moderator", "Moderator")
    logger.info(f"  오늘의 Moderator: {today_moderator}")
    if backtest_result.get("yesterday_comparison"):
        yc = backtest_result["yesterday_comparison"]
        logger.info(f"  전일 실제 방향: {yc['actual_movement']}")

    # ── Step 6: 보고서 조립 ────────────────────────────────────────────────────
    report = {
        "date":         today_str,
        "generated_at": market_data.get("collected_at", today_str),
        "market_data":  market_data,
        "debate":       debate_result,
        "verdict":      verdict,
        "backtest":     backtest_result,
    }

    # ── Step 7: 저장 ──────────────────────────────────────────────────────────
    logger.info("Step 7: 보고서 저장")
    docs_dir = ROOT / "docs" / "data"
    docs_dir.mkdir(parents=True, exist_ok=True)

    report_path = docs_dir / "daily_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"  저장: {report_path}")

    # history 아카이브 (backtester.archive_report 활용)
    backtester.archive_report(report, today_str)

    # ── Step 8: Telegram 알림 ────────────────────────────────────────────────
    logger.info("Step 8: Telegram 알림")
    send_telegram(verdict, today_str)

    logger.info("=" * 60)
    logger.info(
        f"파이프라인 완료 ✅ | {verdict['final_stance']} | "
        f"확신도 {verdict['confidence_score']}%"
    )
    logger.info("=" * 60)
    return report


if __name__ == "__main__":
    main()

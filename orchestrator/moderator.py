"""
moderator.py — Phase 3 종합 판단 (하이브리드: 규칙 기반 집계 + LLM 품질 평가)
"""
import json
import logging
import re
from typing import List, Dict, Tuple

import anthropic

logger = logging.getLogger(__name__)

# stance → 수치 매핑
STANCE_SCORE = {"BUY": 1, "HOLD": 0, "SELL": -1}

# 시장 날씨 매핑 (US Market 버전)
WEATHER_MAP = {
    "BUY":  ("sunny",        "☀️",  "Strong Buy — Clear Sky"),
    "HOLD": ("partly_cloudy","⛅",  "Hold — Mixed Signals"),
    "SELL": ("stormy",       "🌧️", "Caution — Headwinds Ahead"),
}


class Moderator:
    def __init__(self, client: anthropic.Anthropic, model: str):
        self.client = client
        self.model  = model

    def synthesize(
        self,
        reports:     List[Dict],
        critiques:   List[Dict],
        market_data: Dict,
    ) -> dict:
        # ── Step 1: 규칙 기반 집계 ─────────────────────────────────────────
        weighted_score, avg_confidence = self._weighted_vote(reports)
        rule_stance = self._score_to_stance(weighted_score)
        logger.info(f"규칙 기반 집계: {rule_stance} (score={weighted_score:.3f}, avg_conf={avg_confidence:.1f})")

        # ── Step 2: LLM 종합 판단 ──────────────────────────────────────────
        debate_text = self._format_debate(reports, critiques)
        sp500_close = market_data.get("sp500", {}).get("close", "N/A")
        sp500_chg   = market_data.get("sp500", {}).get("change_pct", 0)
        ndx_close   = market_data.get("nasdaq", {}).get("close", "N/A")
        us10y       = market_data.get("rates", {}).get("us10y", "N/A")
        vix_close   = market_data.get("vix",   {}).get("close", "N/A")

        prompt = f"""아래 4인 에이전트의 미국 시장 토론을 종합해 최종 투자 판단을 내려주세요.

[오늘 시장 요약]
S&P500: {sp500_close} ({sp500_chg:+.2f}%)  |  Nasdaq: {ndx_close}
미 10년물 금리: {us10y}%  |  VIX: {vix_close}

{debate_text}

규칙 기반 선행 판단: {rule_stance} (가중 평균 점수: {weighted_score:.2f})

[종합 시 고려 사항]
- 어느 에이전트의 논리가 가장 데이터로 잘 뒷받침되는가?
- 교차 반론 후에도 유효한 핵심 주장은 무엇인가?
- 규칙 기반 결과와 다른 판단을 내린다면 명확한 근거를 제시하라

반드시 아래 JSON으로만 응답:
{{
  "final_stance": "BUY",
  "confidence_score": 68,
  "summary": "종합 근거 (200자 이상, 구체적 시장 데이터 포함)",
  "key_insights": ["인사이트1", "인사이트2", "인사이트3"],
  "risk_factors": ["리스크1", "리스크2"],
  "action_items": ["행동1", "행동2", "행동3"]
}}"""

        result = {}
        try:
            resp = self.client.messages.create(
                model       = self.model,
                max_tokens  = 2048,
                system      = "당신은 미국 주식 시장 토론 중재자입니다. 에이전트들의 논리와 데이터 품질을 평가해 최종 판단을 내립니다. JSON만 반환하세요.",
                messages    = [{"role": "user", "content": prompt}],
            )
            text  = re.sub(r"```(?:json)?\s*|```\s*", "", resp.content[0].text).strip()
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                result = json.loads(match.group())
        except Exception as e:
            logger.error(f"Moderator LLM 실패: {e}")
            result = {
                "final_stance":    rule_stance,
                "confidence_score": int(avg_confidence),
                "summary":         "에이전트 토론을 집계한 결과입니다.",
            }

        final_stance = result.get("final_stance", rule_stance).upper()
        weather = WEATHER_MAP.get(final_stance, WEATHER_MAP["HOLD"])

        return {
            "final_stance":        final_stance,
            "confidence_score":    result.get("confidence_score", int(avg_confidence)),
            "summary":             result.get("summary", ""),
            "key_insights":        result.get("key_insights", []),
            "risk_factors":        result.get("risk_factors", []),
            "action_items":        result.get("action_items", []),
            "stance_votes":        {r["agent_name"]: r["stance"] for r in reports},
            "market_weather":      weather[0],
            "market_weather_icon": weather[1],
            "market_weather_en":   weather[2],
        }

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────

    def _weighted_vote(self, reports: List[Dict]) -> Tuple[float, float]:
        total_w, weighted_sum, conf_sum = 0, 0.0, 0.0
        for r in reports:
            w = r.get("confidence_score", 50)
            s = STANCE_SCORE.get(r.get("stance", "HOLD"), 0)
            weighted_sum += s * w
            total_w      += w
            conf_sum     += w
        if total_w == 0:
            return 0.0, 50.0
        return weighted_sum / total_w, conf_sum / len(reports)

    def _score_to_stance(self, score: float) -> str:
        if score > 0.35:  return "BUY"
        if score < -0.35: return "SELL"
        return "HOLD"

    def _format_debate(self, reports: List[Dict], critiques: List[Dict]) -> str:
        lines = ["=== Phase 1: 에이전트 분석 ==="]
        for r in reports:
            lines.append(
                f"\n[{r['avatar']} {r['agent_name']} — {r['role']}]\n"
                f"판단: {r['stance']} (확신도 {r['confidence_score']}%)\n"
                f"분석: {r['analysis'][:350]}\n"
                f"핵심: {' / '.join(r.get('key_points', [])[:2])}"
            )
        lines.append("\n=== Phase 2: 교차 반론 ===")
        for c in critiques:
            lines.append(
                f"\n[{c['from_agent']} → {c['to_agent']}]\n{c['critique']}"
            )
        return "\n".join(lines)

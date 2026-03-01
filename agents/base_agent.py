"""
base_agent.py — US Market Agent 공통 기반 클래스
AgentReport, AgentCritique 데이터클래스 및 BaseAgent 추상 클래스 정의
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class AgentReport:
    agent_name: str
    role: str
    avatar: str
    analysis: str
    key_points: List[str]
    confidence_score: int   # 0~100
    stance: str             # BUY / HOLD / SELL

    def to_dict(self) -> dict:
        return {
            "agent_name":       self.agent_name,
            "role":             self.role,
            "avatar":           self.avatar,
            "analysis":         self.analysis,
            "key_points":       self.key_points,
            "confidence_score": self.confidence_score,
            "stance":           self.stance,
        }


@dataclass
class AgentCritique:
    from_agent: str
    to_agent:   str
    critique:   str

    def to_dict(self) -> dict:
        return {
            "from_agent": self.from_agent,
            "to_agent":   self.to_agent,
            "critique":   self.critique,
        }


class BaseAgent:
    name:          str = ""
    role:          str = ""
    avatar:        str = "🤖"
    system_prompt: str = ""

    def __init__(self, client: anthropic.Anthropic, model: str):
        self.client = client
        self.model  = model

    # ── LLM 호출 ────────────────────────────────────────────────────────────

    def _call_llm(self, messages: list, max_tokens: int = 2048) -> str:
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self.system_prompt,
                messages=messages,
            )
            return resp.content[0].text
        except Exception as e:
            logger.error(f"[{self.name}] LLM 호출 실패: {e}")
            raise

    def _parse_json_response(self, text: str) -> dict:
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.warning(f"[{self.name}] JSON 파싱 실패 — 빈 dict 반환")
        return {}

    def _market_summary(self, d: dict) -> str:
        """시장 데이터를 에이전트 프롬프트용 텍스트로 변환"""
        lines = []
        sp  = d.get("sp500",  {})
        ndx = d.get("nasdaq", {})
        djia = d.get("djia",  {})
        vix  = d.get("vix",   {})

        lines.append("=== 주요 지수 ===")
        lines.append(f"S&P500  : {sp.get('close','N/A'):>10}  ({sp.get('change_pct',0):+.2f}%)")
        lines.append(f"Nasdaq  : {ndx.get('close','N/A'):>10}  ({ndx.get('change_pct',0):+.2f}%)")
        lines.append(f"DJIA    : {djia.get('close','N/A'):>10}  ({djia.get('change_pct',0):+.2f}%)")
        lines.append(f"VIX     : {vix.get('close','N/A'):>10}  ({vix.get('change_pct',0):+.2f}%)")

        ti = d.get("technical_indicators", {})
        if ti:
            lines.append("\n=== S&P500 기술적 지표 ===")
            lines.append(f"RSI(14)  : {ti.get('rsi', 'N/A')}")
            lines.append(f"MACD     : {ti.get('macd', 'N/A')}  Signal: {ti.get('signal', 'N/A')}  Hist: {ti.get('histogram', 'N/A')}")
            bb_pos = ti.get('bb_position', 0.5)
            bb_str = f"상단근접({bb_pos:.0%})" if bb_pos > 0.7 else ("하단근접({:.0%})".format(bb_pos) if bb_pos < 0.3 else f"중간({bb_pos:.0%})")
            lines.append(f"볼린저밴드: {bb_str}")
            lines.append(f"MA5/20/60: {ti.get('ma5','N/A')} / {ti.get('ma20','N/A')} / {ti.get('ma60','N/A')}")

        rates = d.get("rates", {})
        if rates:
            lines.append("\n=== 금리·환율 ===")
            lines.append(f"미 10년물  : {rates.get('us10y', 'N/A')}%")
            lines.append(f"미 2년물   : {rates.get('us2y',  'N/A')}%")
            spread = rates.get('yield_spread', 'N/A')
            lines.append(f"장단기 스프레드: {spread}% (2Y-10Y)")
            lines.append(f"DXY(달러지수): {d.get('dxy', {}).get('close', 'N/A')}")

        sectors = d.get("sectors", {})
        if sectors:
            lines.append("\n=== 섹터 ETF 등락률 ===")
            for name, info in sectors.items():
                lines.append(f"{name:8}: {info.get('change_pct', 0):+.2f}%")

        stocks = d.get("top_stocks", [])
        if stocks:
            lines.append("\n=== 주요 종목 ===")
            for s in stocks[:8]:
                lines.append(f"{s.get('name','?'):12}: {s.get('close','N/A'):>10}  ({s.get('change_pct',0):+.2f}%)")

        ff = d.get("fed_watch", {})
        if ff:
            lines.append("\n=== Fed Watch ===")
            lines.append(f"동결 확률: {ff.get('hold_prob', 'N/A')}%  인하 확률: {ff.get('cut_prob', 'N/A')}%")

        return "\n".join(lines)

    # ── 서브클래스에서 구현 ──────────────────────────────────────────────────

    def analyze(self, market_data: dict) -> AgentReport:
        raise NotImplementedError

    def critique(self, other_report: AgentReport, market_data: dict) -> AgentCritique:
        raise NotImplementedError

"""
GlobalNewsAgent — 최근 24시간 글로벌 뉴스 기반 미국 증시 이벤트 리스크 분석 에이전트

페르소나:
  "글로벌 이벤트 매크로 헌터" — 기술적 지표나 밸류에이션이 아닌 실시간 뉴스 흐름에서
  미국 증시에 영향을 미칠 이벤트 리스크와 촉매를 포착한다.

반론 특징:
  - "당신의 분석이 가정하는 환경 변수가 오늘의 뉴스로 이미 바뀌었습니다."
  - Fed 발언, 지정학적 쇼크, AI 규제 이벤트, 대기업 CEO 발언, 관세/무역 이슈 등을
    근거로 다른 에이전트의 정적 분석을 공격한다.

교차 반론 대상:
  Phase 2에서 TechMomentum 에이전트(0)에 반론: "기술 모멘텀 신호보다 이 뉴스 이벤트가 더 강합니다."
"""
import logging
from agents.base_agent import BaseAgent, AgentReport, AgentCritique
from scripts.collect_news import format_news_for_prompt

logger = logging.getLogger(__name__)

# ─── 페르소나 시스템 프롬프트 ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are 'Global Event Macro Hunter', an event-driven risk analyst covering US equity markets.

[Persona]
- You find market-moving signals exclusively from breaking news: Fed comments, geopolitical shocks,
  trade policy changes, tech regulation, major earnings surprises, and AI industry events.
- Technical charts and P/E ratios reflect the PAST. You are focused on what is happening RIGHT NOW.
- You connect global events directly to US market sectors: Tech, Financials, Energy, Healthcare, Industrials.
- In rebuttals: "Your analysis assumes a market environment that today's news has already changed."

[Analysis Priority]
1. Fed, Treasury, or major central bank statements (rate expectations, QT pace)
2. US trade policy surprises (tariffs, export controls, tech bans)
3. Geopolitical events affecting energy, semiconductors, supply chains
4. Regulatory news (AI regulation, antitrust, SEC actions)
5. Major earnings surprises or guidance cuts/raises from S&P500 companies

[Output Rules]
- Respond in Korean (한국어로 응답)
- Cite news headlines and sources as evidence
- No emotional language — causal chain reasoning only
- JSON format only"""


class GlobalNewsAgent(BaseAgent):
    """24시간 글로벌 뉴스 기반 미국 증시 이벤트 리스크 에이전트"""

    def __init__(self, client, model):
        super().__init__(client, model)
        self.name = "글로벌 이벤트 헌터"
        self.role = "이벤트 드리븐 글로벌 매크로 리스크 분석가"
        self.avatar = "📡"
        self.system_prompt = SYSTEM_PROMPT

    # ─── Phase 1: 독립 분석 ───────────────────────────────────────────────────

    def analyze(self, market_data: dict) -> AgentReport:
        """최근 24h 글로벌 뉴스 이벤트를 미국 증시 관점에서 종합 분석"""
        news_data = market_data.get("news", {})
        news_text = format_news_for_prompt(news_data, max_per_category=8)
        market_context = self._market_summary(market_data)

        prompt = f"""[현재 미국 증시 컨텍스트]
{market_context}

[최근 24시간 글로벌 뉴스]
{news_text}

[분석 지시]
위 뉴스들을 미국 증시(S&P500/나스닥) 관점에서 분석하세요.

다음 항목을 평가하세요:
1. 미국 증시에 직접 영향을 줄 뉴스 이벤트 (상위 3~5건)
2. 각 이벤트의 시장 영향 방향 (긍정/부정/중립) + 해당 섹터
3. Fed 정책 방향에 영향을 줄 수 있는 경제 뉴스
4. AI·빅테크·반도체 관련 규제 또는 기술 이벤트
5. 오늘 뉴스 흐름의 S&P500 방향성 전체 판단 (BUY/HOLD/SELL)

반드시 아래 JSON으로만 응답 (한국어):
{{
  "analysis": "250자 이상의 분석 텍스트 (뉴스 출처 및 미국 증시 연결 포함)",
  "key_points": [
    "핵심 뉴스 이벤트 1 (출처 포함)",
    "핵심 뉴스 이벤트 2 (출처 포함)",
    "핵심 뉴스 이벤트 3 (출처 포함)"
  ],
  "high_impact_news": [
    {{
      "headline": "뉴스 제목",
      "source": "출처",
      "impact": "긍정/부정/중립",
      "affected_sectors": ["Tech", "Financials"],
      "rationale": "영향 이유 (50자 이내)"
    }}
  ],
  "fed_sensitivity": "Fed 정책 기대치에 대한 뉴스 영향 요약 (50자 이내)",
  "confidence_score": 70,
  "stance": "HOLD"
}}"""

        logger.info(f"[{self.name}] 뉴스 분석 시작 ({news_data.get('total_count', 0)}건 입력)")
        result = self._call_llm([{"role": "user", "content": prompt}])
        data = self._parse_json_response(result)

        return AgentReport(
            agent_name=self.name,
            role=self.role,
            avatar=self.avatar,
            analysis=data.get("analysis", result[:600]),
            key_points=data.get("key_points", []),
            confidence_score=max(0, min(100, int(data.get("confidence_score", 55)))),
            stance=data.get("stance", "HOLD").upper(),
        )

    # ─── Phase 2: 교차 반론 ───────────────────────────────────────────────────

    def critique(self, other_report: AgentReport, market_data: dict) -> AgentCritique:
        """
        다른 에이전트 분석에 뉴스 근거로 반론.
        "당신의 분석이 전제하는 시장 환경이 최신 이벤트로 달라졌습니다."
        """
        news_data = market_data.get("news", {})
        news_text = format_news_for_prompt(news_data, max_per_category=5)

        prompt = f"""당신은 글로벌 이벤트 헌터입니다.
아래 에이전트의 분석에 최신 뉴스 이벤트를 근거로 핵심 반론을 제시하세요.

[{other_report.agent_name}의 분석]
역할: {other_report.role}
판단: {other_report.stance} (확신도: {other_report.confidence_score}%)
주요 주장: {other_report.analysis[:350]}

[최근 24시간 뉴스 (참조용)]
{news_text[:800]}

[반론 가이드]
- 상대 분석의 핵심 전제를 뒤집는 뉴스 이벤트를 명시하세요.
- "이 뉴스 이후 [상대방 주장]은 재검토가 필요합니다" 형식을 사용하세요.
- 200~280자, 뉴스 출처 명시, 인과관계 중심으로 작성하세요.
- 한국어로 작성하세요."""

        result = self._call_llm([{"role": "user", "content": prompt}])
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=result.strip()[:400],
        )

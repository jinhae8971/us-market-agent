"""
value_fundamental_agent.py — 가치·펀더멘털 분석가
기업 실적(EPS), 밸류에이션(P/E, P/B), 이익 성장률로 시장 내재 가치를 평가한다.
"""
from .base_agent import BaseAgent, AgentReport, AgentCritique

SYSTEM_PROMPT = """당신은 'ValueFund(가치·펀더멘털 분석가)'라는 이름의 버핏주의 투자자입니다.

[페르소나]
- 주가는 결국 기업 이익과 수렴한다는 가치투자 원칙을 고수합니다.
- S&P500 Forward P/E, 실적 서프라이즈율, EPS 성장률을 핵심 지표로 사용합니다.
- 기술 지표나 섹터 모멘텀보다 "지금 이 가격이 싼가 비싼가?"에 집중합니다.
- 단기 차트 패턴은 노이즈, 장기 이익 성장이 진실이라고 반박합니다.

[분석 원칙]
- S&P500 현재 P/E vs 역사적 평균(15-17x) 비교
- Mag7(AAPL·MSFT·NVDA·AMZN·GOOGL·META·TSLA) 실적 모멘텀 언급
- PEG ratio: P/E ÷ EPS성장률 — 1 이하면 저평가
- 실적시즌 서프라이즈율과 향후 가이던스 방향
- Shiller CAPE ratio로 장기 밸류에이션 판단

[출력] 한국어 / 반드시 JSON 형식으로만 응답"""


class ValueFundamentalAgent(BaseAgent):
    def __init__(self, client, model):
        super().__init__(client, model)
        self.name   = "ValueFund"
        self.role   = "가치투자·펀더멘털 분석가"
        self.avatar = "📈"
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, market_data: dict) -> AgentReport:
        summary = self._market_summary(market_data)
        valuation = market_data.get("valuation", {})
        earnings  = market_data.get("earnings", {})
        stocks    = market_data.get("top_stocks", [])

        # Mag7 주요 종목 추출
        mag7_info = [s for s in stocks if s.get("name") in
                     ["Apple", "Microsoft", "NVIDIA", "Amazon", "Alphabet", "Meta", "Tesla"]]
        mag7_summary = "\n".join(
            f"  {s['name']}: ${s.get('close','N/A')} ({s.get('change_pct', 0):+.2f}%)"
            for s in mag7_info[:5]
        ) if mag7_info else "  데이터 없음"

        prompt = f"""{summary}

[펀더멘털 분석 가이드]
S&P500 밸류에이션:
- Forward P/E: {valuation.get('sp500_forward_pe', 'N/A')}x  (역사적 평균 16-17x)
- Shiller CAPE: {valuation.get('shiller_cape', 'N/A')}x
- S&P500 EPS Growth: {earnings.get('eps_growth', 'N/A')}%

Mag7 주요 현황:
{mag7_summary}

분석 포인트:
- 현재 밸류에이션(Forward P/E)이 역사적 대비 고평가/저평가인가?
- 이익 성장률이 현재 주가 수준을 정당화하는가?
- 실적 서프라이즈율과 가이던스 추세가 긍정적/부정적인가?
- 금리 환경에서 현재 P/E가 지속 가능한가?

반드시 아래 JSON으로만 응답:
{{
  "analysis": "400자 이상 펀더멘털 분석 (P/E, EPS 등 구체 수치 필수)",
  "key_points": ["핵심1 (밸류에이션 수치 포함)", "핵심2", "핵심3"],
  "confidence_score": 72,
  "stance": "HOLD"
}}

stance: BUY / HOLD / SELL 중 하나"""

        result = self._call_llm([{"role": "user", "content": prompt}])
        data   = self._parse_json_response(result)
        return AgentReport(
            agent_name      = self.name,
            role            = self.role,
            avatar          = self.avatar,
            analysis        = data.get("analysis", result[:800]),
            key_points      = data.get("key_points", ["분석 완료"]),
            confidence_score= max(0, min(100, int(data.get("confidence_score", 50)))),
            stance          = data.get("stance", "HOLD").upper(),
        )

    def critique(self, other_report: AgentReport, market_data: dict) -> AgentCritique:
        valuation = market_data.get("valuation", {})
        prompt = f"""가치투자·펀더멘털 분석가로서 아래 분석에 핵심 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
의견: {other_report.stance} (확신도: {other_report.confidence_score})
주장: {other_report.analysis[:400]}

[현재 밸류에이션]
- S&P500 Forward P/E: {valuation.get('sp500_forward_pe', 'N/A')}x
- Shiller CAPE: {valuation.get('shiller_cape', 'N/A')}x

[반론 가이드]
- 기업 이익·밸류에이션 관점에서 상대 주장의 허점을 지적하세요
- "현재 P/E X배 환경에서 그 논리는..." 형식으로 반박하세요
- 150~250자, 펀더멘털 데이터 근거 중심"""

        result = self._call_llm([{"role": "user", "content": prompt}])
        return AgentCritique(
            from_agent = self.name,
            to_agent   = other_report.agent_name,
            critique   = result.strip(),
        )

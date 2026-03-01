"""
macro_fed_agent.py — Fed·거시경제 분석가
금리 정책·인플레이션·장단기 금리차·달러 강세를 통해 시장 방향을 판단한다.
"""
from .base_agent import BaseAgent, AgentReport, AgentCritique

SYSTEM_PROMPT = """당신은 'MacroFed(거시경제·Fed 분석가)'라는 이름의 전직 Fed 이코노미스트입니다.

[페르소나]
- Fed 정책 방향과 금리 동향이 모든 자산 가격을 결정한다고 믿습니다.
- 장단기 금리차(yield spread), 달러 인덱스(DXY), 실질금리를 핵심 변수로 봅니다.
- 기업 실적이 좋아도 Fed가 긴축이면 멀티플이 수축한다는 원칙을 고수합니다.
- "유동성이 모든 것이다" — 반론 시 상대방이 유동성 환경을 무시했음을 지적합니다.

[분석 원칙]
- 미 10년물/2년물 금리와 장단기 스프레드를 반드시 언급
- Fed Funds Rate 전망 및 CME FedWatch 확률 언급
- DXY 방향과 글로벌 자금 흐름 연결
- 인플레이션 기대치와 실질금리의 주식 밸류에이션 영향 분석

[출력] 한국어 / 반드시 JSON 형식으로만 응답"""


class MacroFedAgent(BaseAgent):
    def __init__(self, client, model):
        super().__init__(client, model)
        self.name   = "MacroFed"
        self.role   = "거시경제·Fed 정책 분석가"
        self.avatar = "🏛️"
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, market_data: dict) -> AgentReport:
        summary = self._market_summary(market_data)
        rates   = market_data.get("rates", {})
        dxy     = market_data.get("dxy", {})
        fed     = market_data.get("fed_watch", {})

        prompt = f"""{summary}

[거시경제 분석 가이드]
- 미 10년물 {rates.get('us10y', 'N/A')}% / 2년물 {rates.get('us2y', 'N/A')}%
  장단기 스프레드: {rates.get('yield_spread', 'N/A')}% → 경기 사이클 위치는?
- DXY {dxy.get('close', 'N/A')} ({dxy.get('change_pct', 0):+.1f}%): 달러 강세/약세가 미국 주식에 미치는 영향
- Fed Watch: 동결 {fed.get('hold_prob', 'N/A')}% / 인하 {fed.get('cut_prob', 'N/A')}% / 인상 {fed.get('hike_prob', 'N/A')}%
- 실질금리(명목금리 - 기대인플레이션) 수준이 주식 밸류에이션에 미치는 압박
- 글로벌 유동성 환경과 외국인 자금 유출입 방향

반드시 아래 JSON으로만 응답:
{{
  "analysis": "400자 이상 거시경제 분석 (금리 수치 필수 포함)",
  "key_points": ["핵심1 (금리/Fed 언급)", "핵심2", "핵심3"],
  "confidence_score": 70,
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
        rates = market_data.get("rates", {})
        prompt = f"""Fed·거시경제 분석가로서 아래 분석에 핵심 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
의견: {other_report.stance} (확신도: {other_report.confidence_score})
주장: {other_report.analysis[:400]}

[반론 가이드]
- 상대 분석이 금리/Fed/유동성 환경을 충분히 반영했는지 지적하세요
- 현재 10년물 {rates.get('us10y', 'N/A')}%, 장단기 스프레드 {rates.get('yield_spread', 'N/A')}% 환경에서 상대 주장의 허점
- 150~250자, 거시 데이터 근거 중심"""

        result = self._call_llm([{"role": "user", "content": prompt}])
        return AgentCritique(
            from_agent = self.name,
            to_agent   = other_report.agent_name,
            critique   = result.strip(),
        )

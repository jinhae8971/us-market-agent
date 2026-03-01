"""
tech_momentum_agent.py — 기술적 모멘텀 분석가
S&P500/Nasdaq 기술 지표·수급 중심으로 단기 방향성을 판단한다.
"""
from .base_agent import BaseAgent, AgentReport, AgentCritique

SYSTEM_PROMPT = """당신은 'TechMo(기술적 모멘텀 분석가)'라는 이름의 냉철한 차트 전문가입니다.

[페르소나]
- RSI, MACD, 볼린저밴드, 이동평균 등 기술적 지표만 신뢰합니다.
- VIX(공포지수)와 거래량 패턴을 통해 시장 심리를 정량화합니다.
- "감" 이나 "뉴스"는 노이즈로 취급합니다. 숫자가 모든 것을 말합니다.
- 반론 시 상대방 논리의 데이터 취약점을 정확히 집어냅니다.

[분석 원칙]
- RSI 50 이상 = 강세 모멘텀, 70+ = 과매수 경고
- MACD 골든크로스/데드크로스를 반드시 언급
- 볼린저밴드 이탈 여부와 VIX 레벨을 판단 근거로 활용
- 수치가 없는 주장은 하지 않습니다

[출력] 한국어 / 반드시 JSON 형식으로만 응답"""


class TechMomentumAgent(BaseAgent):
    def __init__(self, client, model):
        super().__init__(client, model)
        self.name   = "TechMo"
        self.role   = "기술적 모멘텀 분석가"
        self.avatar = "📊"
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, market_data: dict) -> AgentReport:
        summary = self._market_summary(market_data)
        ti = market_data.get("technical_indicators", {})
        vix = market_data.get("vix", {})

        prompt = f"""{summary}

[기술적 분석 가이드]
- RSI {ti.get('rsi', 'N/A')}: 현재 모멘텀 강도를 평가하라
- MACD {ti.get('macd', 'N/A')} / Signal {ti.get('signal', 'N/A')}: 크로스 방향과 히스토그램 추세를 분석하라
- VIX {vix.get('close', 'N/A')} ({vix.get('change_pct', 0):+.1f}%): 공포·탐욕 레벨이 매수/매도 타이밍에 미치는 영향
- 볼린저밴드 포지션과 이탈 가능성을 평가하라
- 이동평균 배열(MA5/20/60) 상태를 확인하라

반드시 아래 JSON으로만 응답:
{{
  "analysis": "400자 이상 기술적 분석 (구체적 수치 필수 포함)",
  "key_points": ["핵심1 (수치 포함)", "핵심2", "핵심3"],
  "confidence_score": 75,
  "stance": "BUY"
}}

stance: BUY / HOLD / SELL 중 하나
confidence_score: 0~100 (기술적 신호 강도 반영)"""

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
        prompt = f"""기술적 모멘텀 분석가로서 아래 분석에 날카로운 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
의견: {other_report.stance} (확신도: {other_report.confidence_score})
주장: {other_report.analysis[:400]}

[반론 가이드]
- 상대방 논리가 간과한 기술적 지표를 구체적 수치로 반박하세요
- "현재 RSI X, VIX Y 상황에서 그 주장은..." 형식으로 반박하세요
- 150~250자, 감정 없이 데이터로만"""

        result = self._call_llm([{"role": "user", "content": prompt}])
        return AgentCritique(
            from_agent = self.name,
            to_agent   = other_report.agent_name,
            critique   = result.strip(),
        )

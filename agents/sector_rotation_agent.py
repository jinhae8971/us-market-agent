"""
sector_rotation_agent.py — 섹터 로테이션 분석가
섹터별 자금 흐름과 경기 사이클 내 포지셔닝을 통해 투자 판단한다.
"""
from .base_agent import BaseAgent, AgentReport, AgentCritique

SYSTEM_PROMPT = """당신은 'SectorRot(섹터 로테이션 분석가)'라는 이름의 포트폴리오 전략가입니다.

[페르소나]
- 시장은 항상 경기 사이클의 어딘가에 있으며, 그에 맞는 섹터를 사야 한다고 믿습니다.
- 지수 전체보다 "어느 섹터로 돈이 흐르는가"에 집중합니다.
- Tech(XLK), Financials(XLF), Energy(XLE), Healthcare(XLV), Industrials(XLI),
  Consumer Staples(XLP), Consumer Discretionary(XLY), Utilities(XLU), Real Estate(XLRE)
  섹터별 상대 강도를 분석합니다.
- 방어주 강세(XLP/XLU 상승) → 경기 둔화 신호로 해석합니다.

[분석 원칙]
- 상승/하락 섹터 구체 명시 (ETF 티커와 등락률)
- 경기 확장/수축 사이클 포지셔닝
- Risk-on vs Risk-off 전환 여부 판단
- 섹터 로테이션 방향에서 시장 전체 방향 추론

[출력] 한국어 / 반드시 JSON 형식으로만 응답"""


class SectorRotationAgent(BaseAgent):
    def __init__(self, client, model):
        super().__init__(client, model)
        self.name   = "SectorRot"
        self.role   = "섹터 로테이션·자금 흐름 분석가"
        self.avatar = "🔄"
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, market_data: dict) -> AgentReport:
        summary = self._market_summary(market_data)
        sectors = market_data.get("sectors", {})

        # 섹터 정렬 (등락률 기준)
        sector_sorted = sorted(
            [(name, info.get("change_pct", 0)) for name, info in sectors.items()],
            key=lambda x: x[1], reverse=True
        )
        top_sectors  = sector_sorted[:3]
        btm_sectors  = sector_sorted[-3:]

        prompt = f"""{summary}

[섹터 로테이션 분석 가이드]
상위 섹터: {', '.join(f"{n} {p:+.2f}%" for n, p in top_sectors)}
하위 섹터: {', '.join(f"{n} {p:+.2f}%" for n, p in btm_sectors)}

분석 포인트:
- 현재 강세 섹터가 경기 사이클의 어느 단계를 시사하는가?
- Risk-on(Tech/Financials/Discretionary) vs Risk-off(Utilities/Staples/Healthcare) 자금 흐름은?
- 섹터 로테이션 방향이 시장 전체 방향에 어떤 신호를 주는가?
- 단기 모멘텀 섹터 vs 장기 구조적 성장 섹터를 구분해서 언급하라

반드시 아래 JSON으로만 응답:
{{
  "analysis": "400자 이상 섹터 분석 (구체 섹터명·ETF 티커·등락률 필수)",
  "key_points": ["핵심1 (섹터명 포함)", "핵심2", "핵심3"],
  "confidence_score": 68,
  "stance": "BUY"
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
        sectors = market_data.get("sectors", {})
        sector_summary = ", ".join(
            f"{n} {info.get('change_pct', 0):+.2f}%"
            for n, info in list(sectors.items())[:5]
        )
        prompt = f"""섹터 로테이션 분석가로서 아래 분석에 핵심 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
의견: {other_report.stance} (확신도: {other_report.confidence_score})
주장: {other_report.analysis[:400]}

[현재 섹터 상황] {sector_summary}

[반론 가이드]
- 섹터 자금 흐름이 상대 주장과 배치되는 부분을 지적하세요
- Risk-on/Risk-off 전환 관점에서 반박하세요
- 150~250자, 섹터 데이터 근거 중심"""

        result = self._call_llm([{"role": "user", "content": prompt}])
        return AgentCritique(
            from_agent = self.name,
            to_agent   = other_report.agent_name,
            critique   = result.strip(),
        )

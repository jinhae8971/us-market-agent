"""
debate_engine.py — 5인 에이전트 Phase 1 (독립 분석) + Phase 2 (교차 반론) 오케스트레이터

에이전트 구성 (인덱스 순서):
  TechMomentum(0)   — 기술적 모멘텀 단기 분석
  MacroFed(1)       — Fed·거시경제 하향식 분석
  SectorRotation(2) — 섹터 로테이션 상향식 분석
  ValueFundamental(3) — 가치·펀더멘털 장기 분석
  GlobalNews(4)     — 최근 24h 글로벌 뉴스 이벤트 드리븐 분석 [NEW]

Phase 2 교차 반론 (5방향 체인):
  TechMomentum(0)   → ValueFundamental(3) : 모멘텀 신호 vs 펀더멘털 가정
  MacroFed(1)       → GlobalNews(4)       : 거시 흐름 vs 뉴스 노이즈
  SectorRotation(2) → TechMomentum(0)     : 섹터 수급 vs 기술적 패턴
  ValueFundamental(3) → MacroFed(1)       : 내재가치 vs 매크로 환경
  GlobalNews(4)     → SectorRotation(2)   : 뉴스 촉매 vs 섹터 내러티브
"""
import logging
from typing import List

from agents.base_agent import AgentReport, AgentCritique, BaseAgent

logger = logging.getLogger(__name__)

# 5인 체인 반론 구조: 0→3→1→4→2→0
CRITIQUE_PAIRS = [
    (0, 3),   # TechMomentum   → ValueFundamental : 모멘텀 vs 펀더멘털
    (1, 4),   # MacroFed       → GlobalNews       : 거시 vs 이벤트
    (2, 0),   # SectorRotation → TechMomentum     : 섹터 수급 vs 기술 패턴
    (3, 1),   # ValueFund      → MacroFed         : 내재가치 vs 매크로
    (4, 2),   # GlobalNews     → SectorRotation   : 뉴스 촉매 vs 섹터 내러티브
]


class DebateEngine:
    def __init__(self, agents: List[BaseAgent]):
        self.agents = agents

    def run(self, market_data: dict) -> dict:
        # ── Phase 1: 독립 분석 ──────────────────────────────────────────────
        logger.info("Phase 1 시작: 독립 분석")
        reports: List[AgentReport] = []
        for agent in self.agents:
            try:
                logger.info(f"  [{agent.name}] 분석 중...")
                report = agent.analyze(market_data)
                reports.append(report)
                logger.info(f"  [{agent.name}] 완료: {report.stance} ({report.confidence_score}%)")
            except Exception as e:
                logger.error(f"  [{agent.name}] 분석 실패: {e}")
                reports.append(AgentReport(
                    agent_name       = agent.name,
                    role             = agent.role,
                    avatar           = agent.avatar,
                    analysis         = f"분석 중 오류 발생: {str(e)[:100]}",
                    key_points       = ["분석 불가"],
                    confidence_score = 0,
                    stance           = "HOLD",
                ))

        # ── Phase 2: 교차 반론 ──────────────────────────────────────────────
        logger.info("Phase 2 시작: 교차 반론")
        critiques: List[AgentCritique] = []
        for from_idx, to_idx in CRITIQUE_PAIRS:
            if from_idx >= len(self.agents) or to_idx >= len(reports):
                continue
            agent  = self.agents[from_idx]
            target = reports[to_idx]
            try:
                logger.info(f"  [{agent.name}] → [{target.agent_name}] 반론 중...")
                critique = agent.critique(target, market_data)
                critiques.append(critique)
                logger.info(f"  [{agent.name}] 반론 완료")
            except Exception as e:
                logger.error(f"  [{agent.name}] 반론 실패: {e}")
                critiques.append(AgentCritique(
                    from_agent = agent.name,
                    to_agent   = target.agent_name,
                    critique   = f"반론 생성 중 오류: {str(e)[:80]}",
                ))

        logger.info("Phase 1 + Phase 2 완료")
        return {
            "phase1_reports":   [r.to_dict() for r in reports],
            "phase2_critiques": [c.to_dict() for c in critiques],
        }

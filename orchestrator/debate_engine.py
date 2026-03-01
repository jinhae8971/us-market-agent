"""
debate_engine.py — Phase 1 (독립 분석) + Phase 2 (교차 반론) 오케스트레이터

에이전트 페어링:
  TechMomentum(0) ↔ ValueFundamental(3) : 단기 기술 vs 장기 가치
  MacroFed(1)     ↔ SectorRotation(2)   : 하향식 거시 vs 상향식 섹터
"""
import logging
from typing import List

from agents.base_agent import AgentReport, AgentCritique, BaseAgent

logger = logging.getLogger(__name__)

# TechMo(0)→ValueFund(3), MacroFed(1)→SectorRot(2),
# SectorRot(2)→MacroFed(1), ValueFund(3)→TechMo(0)
CRITIQUE_PAIRS = [(0, 3), (1, 2), (2, 1), (3, 0)]


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

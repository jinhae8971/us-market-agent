# 🇺🇸 US Market Agent

미국 주식 시장 멀티에이전트 분석 시스템 — 매 평일 4인의 AI 전문가가 3-Phase 토론으로 S&P500 BUY/HOLD/SELL 판단을 자동 생성합니다.

## 에이전트 구성

| 에이전트 | 역할 | 분석 관점 |
|---------|------|---------|
| 📈 TechMomentum | 기술적 분석가 | RSI, MACD, VIX, 볼린저밴드 |
| 🏛️ MacroFed | 매크로·연준 전문가 | 금리, 수익률곡선, DXY, FedWatch |
| 🔄 SectorRotation | 섹터 로테이션 분석가 | XLK/XLF/XLE/XLV/XLI/XLP/XLY/XLU/XLRE |
| 💎 ValueFundamental | 가치·펀더멘털 투자자 | Forward P/E, EPS, Mag7 밸류에이션 |

## 3-Phase 토론 프로토콜

```
Phase 1: 독립 분석  →  4명 각자 보고서 작성
Phase 2: 교차 반론  →  TechMo↔ValueFund, MacroFed↔SectorRot
Phase 3: Moderator  →  규칙 기반 집계 + LLM 종합 판단
```

## 실행 일정

매 평일 KST 08:00 (UTC 23:00 전날) 자동 실행

## 대시보드

👉 [GitHub Pages Dashboard](https://jinhae8971.github.io/us-market-agent/)

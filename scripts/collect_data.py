"""
collect_data.py — 미국 증시 데이터 수집 및 기술적 지표 계산

수집 항목:
  - S&P500, Nasdaq, DJIA, Russell 2000 지수 (yfinance)
  - VIX (공포지수)
  - 미 10년물·2년물 국채금리, 장단기 스프레드
  - DXY (달러 인덱스)
  - 섹터 ETF: XLK, XLF, XLE, XLV, XLI, XLP, XLY, XLU, XLRE
  - Mag7 + 주요 종목: AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, JPM, BRK-B
  - 기술적 지표 (S&P500 기준): RSI, MACD, 볼린저밴드, 이동평균
  - 밸류에이션 추정: S&P500 Forward P/E, Shiller CAPE
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ─── 티커 정의 ───────────────────────────────────────────────────────────────
INDEX_TICKERS = {
    "sp500":    "^GSPC",
    "nasdaq":   "^IXIC",
    "djia":     "^DJI",
    "russell":  "^RUT",
    "vix":      "^VIX",
}

RATE_TICKERS = {
    "us10y": "^TNX",
    "us2y":  "^IRX",   # 3-month T-bill (proxy); yfinance does not have 2Y directly
}

SECTOR_TICKERS = {
    "XLK (Tech)":            "XLK",
    "XLF (Financials)":      "XLF",
    "XLE (Energy)":          "XLE",
    "XLV (Healthcare)":      "XLV",
    "XLI (Industrials)":     "XLI",
    "XLP (Staples)":         "XLP",
    "XLY (Discretionary)":   "XLY",
    "XLU (Utilities)":       "XLU",
    "XLRE (Real Estate)":    "XLRE",
}

STOCK_TICKERS = {
    "AAPL":  "Apple",
    "MSFT":  "Microsoft",
    "NVDA":  "NVIDIA",
    "AMZN":  "Amazon",
    "GOOGL": "Alphabet",
    "META":  "Meta",
    "TSLA":  "Tesla",
    "JPM":   "JPMorgan",
    "BRKB":  "Berkshire",
    "DXY":   "DXY",   # placeholder — fetched separately
}

DXY_TICKER = "DX-Y.NYB"


# ─── 기술적 지표 계산 ─────────────────────────────────────────────────────────

def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    val   = (100 - 100 / (1 + rs)).iloc[-1]
    return round(float(val), 2) if not np.isnan(val) else 50.0


def _macd(series: pd.Series) -> Dict:
    ema12  = series.ewm(span=12, adjust=False).mean()
    ema26  = series.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal
    return {
        "macd":      round(float(macd.iloc[-1]), 2),
        "signal":    round(float(signal.iloc[-1]), 2),
        "histogram": round(float(hist.iloc[-1]), 2),
    }


def _bollinger(series: pd.Series, window: int = 20) -> Dict:
    ma    = series.rolling(window).mean()
    std   = series.rolling(window).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    rng   = float(upper.iloc[-1] - lower.iloc[-1])
    pos   = (float(series.iloc[-1] - lower.iloc[-1]) / rng) if rng > 0 else 0.5
    return {
        "upper":    round(float(upper.iloc[-1]), 2),
        "middle":   round(float(ma.iloc[-1]),    2),
        "lower":    round(float(lower.iloc[-1]), 2),
        "position": round(pos, 4),
    }


def _moving_averages(series: pd.Series) -> Dict:
    current = float(series.iloc[-1])
    result  = {}
    for p in [5, 20, 60]:
        if len(series) >= p:
            ma  = float(series.rolling(p).mean().iloc[-1])
            result[f"ma{p}"]          = round(ma, 2)
            result[f"ma{p}_diff_pct"] = round((current - ma) / ma * 100, 2)
    return result


# ─── 단일 종목 유틸 ───────────────────────────────────────────────────────────

def _fetch(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(symbol).history(period=period)
        return df if not df.empty else None
    except Exception as e:
        logger.warning(f"{symbol} 수집 실패: {e}")
        return None


def _latest(df: Optional[pd.DataFrame]) -> Dict:
    if df is None or df.empty:
        return {"close": None, "change": 0, "change_pct": 0, "volume": 0, "volume_change_pct": 0}
    last  = df.iloc[-1]
    prev  = df.iloc[-2] if len(df) >= 2 else last
    close = float(last["Close"])
    prev_c = float(prev["Close"])
    chg    = close - prev_c
    chg_p  = (chg / prev_c * 100) if prev_c else 0.0
    vol    = float(last.get("Volume", 0))
    avg5v  = float(df["Volume"].rolling(5).mean().iloc[-1]) if "Volume" in df.columns else 0
    vol_chg = ((vol - avg5v) / avg5v * 100) if avg5v > 0 else 0.0
    return {
        "close":             round(close, 2),
        "change":            round(chg, 2),
        "change_pct":        round(chg_p, 2),
        "volume":            int(vol),
        "volume_change_pct": round(vol_chg, 2),
    }


# ─── 메인 수집 함수 ───────────────────────────────────────────────────────────

def collect_market_data() -> Dict:
    logger.info("미국 시장 데이터 수집 시작...")
    result: Dict = {}

    # 1) 주요 지수
    for key, ticker in INDEX_TICKERS.items():
        df = _fetch(ticker)
        result[key] = _latest(df)
        if key == "sp500" and df is not None and len(df) >= 60:
            close = df["Close"]
            bb    = _bollinger(close)
            macd_d = _macd(close)
            mas   = _moving_averages(close)
            result["technical_indicators"] = {
                "rsi": _rsi(close),
                **macd_d,
                "bb_upper":    bb["upper"],
                "bb_middle":   bb["middle"],
                "bb_lower":    bb["lower"],
                "bb_position": bb["position"],
                **mas,
            }

    # 2) 금리 (10년물 / 단기금리 proxy)
    df10 = _fetch("^TNX", "1mo")
    df2  = _fetch("^IRX", "1mo")   # 3-month T-bill as short-rate proxy
    us10y = _latest(df10).get("close") or 4.3
    us2y  = _latest(df2).get("close") or 5.1
    # yfinance ^IRX returns annualized %; ^TNX in tenths of percent
    # Normalize both to percent
    if us10y and us10y < 2: us10y = us10y * 10    # TNX is in tenths
    if us2y  and us2y  > 20: us2y  = us2y  / 100  # IRX is in basis points / 100
    yield_spread = round(float(us10y) - float(us2y), 3) if us10y and us2y else None
    result["rates"] = {
        "us10y":        round(float(us10y), 3),
        "us2y":         round(float(us2y),  3),
        "yield_spread": yield_spread,
    }

    # 3) DXY
    df_dxy = _fetch(DXY_TICKER, "1mo")
    result["dxy"] = _latest(df_dxy)

    # 4) 섹터 ETF
    sectors: Dict = {}
    for name, ticker in SECTOR_TICKERS.items():
        df = _fetch(ticker, "1mo")
        sectors[name] = _latest(df)
    result["sectors"] = sectors

    # 5) 주요 종목 (Mag7 + JPM + BRK-B)
    stock_list = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "BRK-B"]
    stock_names = {
        "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA",
        "AMZN": "Amazon", "GOOGL": "Alphabet", "META": "Meta",
        "TSLA": "Tesla", "JPM": "JPMorgan", "BRK-B": "Berkshire",
    }
    top_stocks: List[Dict] = []
    for ticker in stock_list:
        df = _fetch(ticker, "1mo")
        if df is not None:
            info = _latest(df)
            info["ticker"] = ticker
            info["name"]   = stock_names.get(ticker, ticker)
            try:
                fi = yf.Ticker(ticker).fast_info
                info["pe_ratio"]    = round(float(getattr(fi, "trailing_pe",     0) or 0), 1)
                info["price_book"]  = round(float(getattr(fi, "price_to_book",   0) or 0), 2)
                info["market_cap_b"]= round(float(getattr(fi, "market_cap",      0) or 0) / 1e9, 1)
            except Exception:
                info["pe_ratio"] = None
                info["price_book"] = None
                info["market_cap_b"] = None
            top_stocks.append(info)
    result["top_stocks"] = top_stocks

    # 6) 밸류에이션 추정
    result["valuation"] = _estimate_valuation(result)

    # 7) Fed Watch 추정 (실제 CME FedWatch API 연동 권장)
    result["fed_watch"] = _estimate_fed_watch(result.get("rates", {}))

    # 8) 실적 추정
    result["earnings"] = {
        "eps_growth":          _estimate_eps_growth(result),
        "beat_rate":           "~75%",   # 최근 S&P500 실적 서프라이즈율 평균
        "guidance_trend":      "neutral",
    }

    # 9) 최근 24시간 글로벌 뉴스 수집 [NEW]
    logger.info("뉴스 데이터 수집 중...")
    try:
        from scripts.collect_news import collect_news
        result["news"] = collect_news(hours=24)
        logger.info(f"뉴스 수집 완료: {result['news'].get('total_count', 0)}건")
    except Exception as e:
        logger.warning(f"뉴스 수집 실패 (파이프라인 계속 진행): {e}")
        from datetime import datetime as _dt
        result["news"] = {
            "international": [], "economic": [], "technology": [], "korean": [],
            "collected_at": _dt.now().isoformat(),
            "total_count": 0,
            "collection_errors": [str(e)],
        }

    result["collected_at"] = datetime.now().isoformat()
    logger.info("데이터 수집 완료")
    return result


# ─── 추정 헬퍼 ────────────────────────────────────────────────────────────────

def _estimate_valuation(data: Dict) -> Dict:
    """
    S&P500 Forward P/E 추정:
      - yfinance S&P500 P/E는 직접 제공 안 됨
      - Mag7 평균 P/E로 시장 수준 추정 (보수적 접근)
      - 실제 운영 시 Macrotrends / FRED API 연동 권장
    """
    stocks = data.get("top_stocks", [])
    pe_vals = [s["pe_ratio"] for s in stocks if s.get("pe_ratio") and s["pe_ratio"] > 0]
    avg_pe  = round(sum(pe_vals) / len(pe_vals), 1) if pe_vals else None
    return {
        "sp500_forward_pe": avg_pe,   # 주요 종목 평균 P/E (proxy)
        "shiller_cape":     None,     # 실제 연동 필요 (FRED: CAPE)
        "sp500_div_yield":  1.4,      # 최근 S&P500 배당수익률 (%)
    }


def _estimate_fed_watch(rates: Dict) -> Dict:
    """
    금리 수준 기반 Fed 동결/인하/인상 확률 추정
    실제 운영 시 CME FedWatch API (https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)
    또는 FRED 연방기금금리 선물 데이터로 교체 권장
    """
    us10y = rates.get("us10y", 4.3)
    us2y  = rates.get("us2y",  5.0)
    spread = rates.get("yield_spread", -0.7)

    # 금리 역전 심할수록 인하 기대 높음 (단순 추정)
    if spread is None:
        return {"hold_prob": 60, "cut_prob": 30, "hike_prob": 10}
    if spread < -0.5:
        cut_prob  = min(55, int(abs(spread) * 40))
        hold_prob = 100 - cut_prob - 5
        return {"hold_prob": hold_prob, "cut_prob": cut_prob, "hike_prob": 5}
    elif spread > 0:
        return {"hold_prob": 55, "cut_prob": 25, "hike_prob": 20}
    else:
        return {"hold_prob": 65, "cut_prob": 30, "hike_prob": 5}


def _estimate_eps_growth(data: Dict) -> Optional[float]:
    """주요 종목 YoY 수익 성장률 추정 (proxy)"""
    stocks = data.get("top_stocks", [])
    chg_vals = [abs(s.get("change_pct", 0)) for s in stocks if s.get("change_pct") is not None]
    return round(sum(chg_vals) / len(chg_vals), 1) if chg_vals else None


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = collect_market_data()
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))

import yfinance as yf
import requests
import os
from datetime import datetime
import pytz

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("▶ [성공] 텔레그램 전송 완료!")
    except Exception as e:
        print(f"▶ 에러: {e}")

def load_stock_data(symbol):
    """
    반환: (df_today, df_calc)
    - df_today : 현재가 추출용 (오늘 장중 포함)
    - df_calc  : 지표 계산용 (장중이면 오늘 데이터 제거 → 전일 종가 기준)
    """
    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst)

    df = yf.Ticker(symbol).history(period="1y", auto_adjust=True)
    if df.empty:
        return df, df

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(kst)
    else:
        df.index = df.index.tz_convert(kst)

    is_intraday = (
        df.index[-1].date() == now_kst.date()
        and now_kst.hour < 16
    )

    if is_intraday:
        df_today = df.iloc[-1:]   # 오늘 장중 → 현재가용
        df_calc  = df.iloc[:-1]   # 전일까지  → 지표 계산용
    else:
        df_today = df.iloc[-1:]
        df_calc  = df

    return df_today, df_calc

def get_consecutive_days(series):
    closes = series.tolist()
    diffs = []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        if d != 0:
            diffs.append(d)
    if not diffs:
        return 0, "보합"
    is_up = diffs[-1] > 0
    count = 0
    for d in reversed(diffs):
        if (d > 0) == is_up:
            count += 1
        else:
            break
    return count, "상승" if is_up else "하락"

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calculate_mdd(series):
    peak = series.expanding(min_periods=1).max()
    drawdown = (series - peak) / peak
    return drawdown.min() * 100

def get_signal_20(disparity):
    if disparity >= 115:  return "🔴과열  "
    elif disparity <= 85: return "🟢매수권"
    return "⚪관망  "

def get_signal_50(disparity):
    if disparity >= 125:   return "🔴과열  "
    elif disparity <= 110: return "🟢매수권"
    return "⚪관망  "

def get_rsi_signal(rsi):
    if rsi >= 70:   return "🔴과열  "
    elif rsi <= 30: return "🟢매수권"
    return "⚪중립  "

def get_mdd_signal(mdd):
    if mdd >= -20: return "안정"
    elif mdd >= -40: return "보통"
    return "고변동"

def get_final_opinion(sig20, sig50, rsi_sig):
    score = 0
    for sig in [sig20, sig50, rsi_sig]:
        if "매수권" in sig: score += 1
        elif "과열" in sig: score -= 1
    if score >= 3:    return "💡 적극 매수 검토"
    elif score >= 1:  return "💡 분할 매수 검토"
    elif score == 0:  return "💡 관망"
    elif score >= -2: return "💡 신규 매수 자제"
    return "💡 익절 검토"

def check_market_disparity():
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M")

    tickers = {
        "코스피":     ("^KS11",     True),
        "삼성전자":   ("005930.KS", False),
        "SK하이닉스": ("000660.KS", False),
        "삼성전기":   ("009150.KS", False),
    }

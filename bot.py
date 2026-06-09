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

# 연속 상승/하락 계산 함수
def get_consecutive_days(series):
    diff = series.diff()
    # 상승(True), 하락(False)만 필터링 (보합 제외)
    valid_diff = diff[diff != 0]
    if valid_diff.empty:
        return 0, "보합"
    
    last_val = valid_diff.iloc[-1]
    is_up = last_val > 0
    
    count = 0
    for val in reversed(valid_diff):
        if (val > 0) == is_up:
            count += 1
        else:
            break
            
    direction = "상승" if is_up else "하락"
    return count, direction

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

def get_signal_20(disparity, is_index=False):
    if is_index:
        if disparity >= 105: return "🔴과열  "
        elif disparity <= 95: return "🟢매수권"
        return "⚪중립  "
    else:
        if disparity >= 115: return "🔴과열  "
        elif disparity <= 85: return "🟢매수권"
        return "⚪중립  "

def get_signal_50(disparity, is_index=False):
    if is_index:
        if disparity >= 105: return "🔴과열  "
        elif disparity <= 95: return "🟢매수권"
        return "⚪중립  "
    else:
        if disparity >= 125: return "🔴과열  "
        elif disparity <= 110: return "🟢매수권"
        return "⚪중립  "

def get_rsi_signal(rsi):
    if rsi >= 70: return "🔴과열  "
    elif rsi <= 30: return "🟢매수권"
    return "⚪중립  "

def get_mdd_signal(mdd):
    if mdd >= -20: return "안정"
    elif mdd >= -40: return "보통"
    return "고변동"

def get_final_opinion(sig20, sig50, rsi_sig):
    score = 0
    for sig in [sig20, sig50, rsi_sig]:
        if "저평가" in sig: score += 1
        elif "고평가" in sig: score -= 1
    if score >= 3: return "💡 적극 매수 검토"
    elif score >= 1: return "💡 분할 매수 검토"
    elif score == 0: return "💡 관망"
    elif score >= -2: return "💡 신규 매수 자제"
    return "💡 익절 검토"

def check_market_disparity():
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M")
    tickers = {
        "코스피": ("^KS11", True),
        "삼성전자": ("005930.KS", False),
        "SK하이닉스": ("000660.KS", False),
        "삼성전기": ("009150.KS", False),
    }

    lines = ["🔔 <b>주요 기술적지표 브리핑</b>", f"🕐 {now}"]

    for name, (symbol, is_index) in tickers.items():
        stock = yf.Ticker(symbol)
        df = stock.history(period="1y")
        if df.empty: continue

        price = df["Close"].iloc[-1]
        prev_price = df["Close"].iloc[-2]
        change_rate = ((price - prev_price) / prev_

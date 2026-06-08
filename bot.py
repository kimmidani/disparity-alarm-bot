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
        if disparity >= 105: return "🔴고평가"
        elif disparity <= 95: return "🟢저평가"
        return "⚪중립  "
    else:
        if disparity >= 115: return "🔴고평가"
        elif disparity <= 85: return "🟢저평가"
        return "⚪중립  "

def get_signal_50(disparity, is_index=False):
    if is_index:
        if disparity >= 105: return "🔴고평가"
        elif disparity <= 95: return "🟢저평가"
        return "⚪중립  "
    else:
        if disparity >= 125: return "🔴고평가"
        elif disparity <= 110: return "🟢저평가"
        return "⚪중립  "

def get_rsi_signal(rsi):
    if rsi >= 70: return "🔴고평가"
    elif rsi <= 30: return "🟢저평가"
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
        d20 = (price / df["Close"].rolling(window=20).mean().iloc[-1]) * 100
        d50 = (price / df["Close"].rolling(window=50).mean().iloc[-1]) * 100
        rsi = calc_rsi(df["Close"]).iloc[-1]
        mdd = calculate_mdd(df["Close"])
        drop52 = ((price - df["Close"].max()) / df["Close"].max()) * 100

        sig20, sig50, rsi_sig = get_signal_20(d20, is_index), get_signal_50(d50, is_index), get_rsi_signal(rsi)
        opinion = get_final_opinion(sig20, sig50, rsi_sig)
        mdd_str = get_mdd_signal(mdd)
        unit = "pt" if is_index else "원"

        lines.append("─────────────────")
        lines.append(f"<b>📊 {name}</b>  {price:,.0f}{unit}")
        lines.append(f"<code>20일선      {int(d20):>3}%  {sig20}</code>")
        lines.append(f"<code>50일선      {int(d50):>3}%  {sig50}</code>")
        lines.append(f"<code>RSI         {int(rsi):>3}  {rsi_sig}</code>")
        lines.append(f"<code>52주낙폭 {drop52:>6.1f}%</code>")
        lines.append(f"<code>MDD    {mdd:>6.1f}% ({mdd_str})</code>")
        lines.append(f"\n{opinion}")

    lines.append("─────────────────")
    send_telegram_message("\n".join(lines))

if __name__ == "__main__":
    check_market_disparity()

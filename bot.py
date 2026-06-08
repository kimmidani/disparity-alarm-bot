import yfinance as yf
import pandas as pd
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
        else:
            print(f"▶ [실패] 에러 코드: {response.status_code}")
    except Exception as e:
        print(f"▶ 네트워크 에러: {e}")

def make_bar(disparity, min_val=80, max_val=150, length=10):
    ratio = (disparity - min_val) / (max_val - min_val)
    filled = max(0, min(length, round(ratio * length)))
    return "█" * filled + "░" * (length - filled)

def get_signal(disparity, is_index=False):
    if is_index:
        if disparity >= 105: return "🔴 과열"
        elif disparity <= 95: return "🟢 매수권"
        else: return "⚪ 관망"
    else:
        if disparity >= 115: return "🔴 과열"
        elif disparity <= 85: return "🟢 매수권"
        else: return "⚪ 관망"

def get_comment(sig20, sig50):
    if "과열" in sig20 and "과열" in sig50:
        return "💬 20·50일선 모두 과열.\n   강한 익절 / 추가매수 금지."
    elif "과열" in sig50:
        return "💬 50일선 과열 구간.\n   신규매수 자제 / 익절 검토."
    elif "매수권" in sig20 and "매수권" in sig50:
        return "💬 20·50일선 모두 매수권.\n   분할매수 적극 검토."
    elif "매수권" in sig20:
        return "💬 20일선 매수권 진입.\n   50일선은 아직 관망 구간."
    elif "매수권" in sig50:
        return "💬 50일선 매수권 진입.\n   분할매수 검토."
    else:
        return "💬 관망 유지."

def check_market_disparity():
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M")

    tickers = {
        "코스피":   ("^KS11",     True),
        "삼성전자": ("005930.KS", False),
        "SK하이닉스": ("000660.KS", False),
        "삼성전기": ("009150.KS", False),
    }

    lines = []
    lines.append(f"🔔 <b>이격도 브리핑</b>")
    lines.append(f"{now} KST")

    for name, (symbol, is_index) in tickers.items():
        stock = yf.Ticker(symbol)
        df = stock.history(period="100d")
        if df.empty:
            continue

        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['D20']  = (df['Close'] / df['MA20']) * 100
        df['D50']  = (df['Close'] / df['MA50']) * 100

        today     = df.iloc[-1]
        yesterday = df.iloc[-2]

        price = today['Close']
        d20   = today['D20']
        d50   = today['D50']
        diff20 = d20 - yesterday['D20']
        diff50 = d50 - yesterday['D50']

        sig20 = get_signal(d20, is_index)
        sig50 = get_signal(d50, is_index)
        bar20 = make_bar(d20)
        bar50 = make_bar(d50)

        unit = "pt" if is_index else "원"

        lines.append("━━━━━━━━━━━━━━━━")
        lines.append(f"<b>📊 {name}</b>  {price:,.0f}{unit}")
        lines.append(f"20일  {int(d20):>3}%  {bar20}  {sig20}")
        lines.append(f"          전일比 {diff20:+.1f}%p")
        lines.append(f"50일  {int(d50):>3}%  {bar50}  {sig50}")
        lines.append(f"          전일比 {diff50:+.1f}%p")
        lines.append(get_comment(sig20, sig50))

    lines.append("━━━━━━━━━━━━━━━━")
    send_telegram_message("\n".join(lines))

if __name__ == "__main__":
    check_market_disparity()

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

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

# MDD 계산 함수 (1년치 기준)
def calculate_mdd(series):
    peak = series.expanding(min_periods=1).max()
    drawdown = (series - peak) / peak
    return drawdown.min() * 100

def get_signal_20(disparity, is_index=False):
    if is_index:
        if disparity >= 105:  return "🔴 과열"
        elif disparity <= 95: return "🟢 매수권"
        else:                 return "⚪ 관망"
    else:
        if disparity >= 115:  return "🔴 과열"
        elif disparity <= 85: return "🟢 매수권"
        else:                 return "⚪ 관망"

def get_signal_50(disparity, is_index=False):
    if is_index:
        if disparity >= 105:  return "🔴 과열"
        elif disparity <= 95: return "🟢 매수권"
        else:                 return "⚪ 관망"
    else:
        if disparity >= 125:   return "🔴 과열"
        elif disparity <= 110: return "🟢 매수권"
        else:                  return "⚪ 관망"

def get_rsi_signal(rsi):
    if rsi >= 70:   return "🔴 과열"
    elif rsi <= 30: return "🟢 침체"
    else:           return "⚪ 중립"

def get_final_opinion(sig20, sig50, rsi_sig):
    if "매수권" in sig50 and "침체" in rsi_sig:
        return "💡 [적극 매수 검토] 50일선·RSI 동시 매수권"
    elif "매수권" in sig50:
        return "💡 [분할매수 검토] 50일선 매수권 진입"
    elif "매수권" in sig20 and "과열" not in sig50:
        return "💡 [분할매수 검토] 20일선 매수권 진입"
    elif "과열" in sig50 and "과열" in rsi_sig:
        return "💡 [익절 검토] 50일선·RSI 동시 과열"
    elif "과열" in sig20 and "과열" in sig50:
        return "💡 [신규매수 자제] 20·50일선 모두 과열"
    elif "과열" in sig50:
        return "💡 [신규매수 자제] 50일선 과열 구간"
    else:
        return "💡 [관망 유지]"

def check_market_disparity():
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M")

    tickers = {
        "코스피":     ("^KS11",     True),
        "삼성전자":   ("005930.KS", False),
        "SK하이닉스": ("000660.KS", False),
        "삼성전기":   ("009150.KS", False),
    }

    lines = []
    lines.append("🔔 <b>이격도 &amp; RSI 브리핑</b>")
    lines.append(f"🕐 {now} KST")

    for name, (symbol, is_index) in tickers.items():
        # period를 1y로 변경하여 1년치 데이터 확보
        stock = yf.Ticker(symbol)
        df = stock.history(period="1y") 
        if df.empty:
            continue

        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['D20']  = (df['Close'] / df['MA20']) * 100
        df['D50']  = (df['Close'] / df['MA50']) * 100
        df['RSI']  = calc_rsi(df['Close'])

        today     = df.iloc[-1]
        yesterday = df.iloc[-2]

        price  = today['Close']
        d20    = today['D20']
        d50    = today['D50']
        rsi    = today['RSI']
        diff20 = d20 - yesterday['D20']
        diff50 = d50 - yesterday['D50']
        
        # MDD 계산 및 경고 표시 로직
        mdd = calculate_mdd(df['Close'])
        warning = "⚠️" if mdd <= -30 else ""

        sig20    = get_signal_20(d20, is_index)
        sig50    = get_signal_50(d50, is_index)
        rsi_sig  = get_rsi_signal(rsi)
        opinion  = get_final_opinion(sig20, sig50, rsi_sig)
        unit     = "pt" if is_index else "원"

        lines.append("─────────────────")
        lines.append(f"<b>📊 {name}</b>  {price:,.0f}{unit}")
        lines.append(f"• 20일 이격: {int(d20)}% {sig20} ({diff20:+.1f}%p)")
        lines.append(f"• 50일 이격: {int(d50)}% {sig50} ({diff50:+.1f}%p)")
        lines.append(f"• RSI 지수: {rsi:.0f} {rsi_sig}")
        lines.append(f"• MDD(1년): {mdd:.1f}% {warning}")
        lines.append(opinion)

    lines.append("─────────────────")
    send_telegram_message("\n".join(lines))

if __name__ == "__main__":
    check_market_disparity()

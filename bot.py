import os
from datetime import datetime
import pandas as pd
import pytz
import requests
import yfinance as yf

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


def get_disparity_signal(disparity, days, is_index=False):
    """20일/50일 및 지수/종목별 기준 분리 (강세장 최적화 기준)"""
    if is_index:
        if days == 20:
            if disparity >= 103:
                return "🔴 과열"
            elif disparity <= 97:
                return "🟢 매수권"
            else:
                return "⚪ 관망"
        else:  # 50일
            if disparity >= 110:
                return "🔴 과열"
            elif disparity <= 100:
                return "🟢 매수권"
            else:
                return "⚪ 관망"
    else:  # 개별 종목
        if days == 20:
            if disparity >= 110:
                return "🔴 과열"
            elif disparity <= 95:
                return "🟢 매수권"
            else:
                return "⚪ 관망"
        else:  # 50일
            if disparity >= 125:
                return "🔴 과열"
            elif disparity <= 110:
                return "🟢 매수권"
            else:
                return "⚪ 관망"


def get_rsi_signal(rsi):
    if rsi >= 75:
        return "🔴 과열"
    elif rsi <= 40:
        return "🟢 침체"
    else:
        return "⚪ 중립"


def get_final_opinion(sig20, sig50, rsi_sig):
    if "매수권" in sig50 and "침체" in rsi_sig:
        return "💡 [적극 매수 검토] 50일선·RSI 동시 매수권 (🔥)"
    elif "매수권" in sig50:
        return "💡 [분할매수 검토] 50일선 매수권 진입"
    elif "매수권" in sig20 and "과열" not in sig50:
        return "💡 [분할매수 검토] 20일선 매수권 진입"
    elif "과열" in sig50 and "과열" in rsi_sig:
        return "💡 [익절 / 추가매수 금지] 50일선·RSI 동시 과열 (⚠️)"
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
        "코스피": ("^KS11", True),
        "삼성전자": ("005930.KS", False),
        "SK하이닉스": ("000660.KS", False),
        "삼성전기": ("009150.KS", False),
    }

    strong_buys = []
    strong_sells = []
    ticker_data = []

    for name, (symbol, is_index) in tickers.items():
        stock = yf.Ticker(symbol)
        df = stock.history(period="120d")
        if df.empty:
            continue

        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["D20"] = (df["Close"] / df["MA20"]) * 100
        df["D50"] = (df["Close"] / df["MA50"]) * 100
        df["RSI"] = calc_rsi(df["Close"])

        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        price = today["Close"]
        ma50_val = today["MA50"]
        d20 = today["D20"]
        d50 = today["D50"]
        rsi = today["RSI"]
        diff20 = d20 - yesterday["D20"]
        diff50 = d50 - yesterday["D50"]

        sig20 = get_disparity_signal(d20, 20, is_index)
        sig50 = get_disparity_signal(d50, 50, is_index)
        rsi_sig = get_rsi_signal(rsi)
        opinion = get_final_opinion(sig20, sig50, rsi_sig)

        if is_index:
            target_buy_price = ma50_val * 1.00
            target_heat_price = ma50_val * 1.10
        else:
            target_buy_price = ma50_val * 1.10
            target_heat_price = ma50_val * 1.25

        if "적극 매수" in opinion:
            strong_buys.append(name)
        elif "익절" in opinion:
            strong_sells.append(name)

        ticker_data.append(
            {
                "name": name,
                "price": price,
                "is_index": is_index,
                "d20": d20,
                "d50": d50,
                "rsi": rsi,
                "diff20": diff20,
                "diff50": diff50,
                "sig20": sig20,
                "sig50": sig50,
                "rsi_sig": rsi_sig,
                "opinion": opinion,
                "buy_price": target_buy_price,
                "heat_price": target_heat_price,
            }
        )

    lines = []

    if strong_buys:
        lines.append("🔥 <b>[역대급 매수 기회 자산 포착]</b>")
        lines.append(
            f"👉 이격도 침체 + RSI 강세장 과매도 동시 충족: {', '.join(strong_buys)}"
        )
        lines.append("─────────────────")
    if strong_sells:
        lines.append("⚠️ <b>[극단적 과열 매도 신호 포착]</b>")
        lines.append(
            f"👉 이격도 과열 + RSI 과열 동시 충족: {', '.join(strong_sells)}"
        )
        lines.append("─────────────────")

    lines.append("🔔 <b>이격도 &amp; RSI 브리핑 (강세장 기준)</b>")
    lines.append(f"🕐 {now} KST")
    lines.append("ℹ️ 지수 기준: 50일 과열 110% / 매수 100%")
    lines.append("ℹ️ 종목 기준: 50일 과열 125% / 매수 110% (RSI 매수 40이하)")

    for t in ticker_data:
        unit = "pt" if t["is_index"] else "원"
        lines.append("─────────────────")
        lines.append(f"<b>📊 {t['name']}</b>  {t['price']:,.0f}{unit}")
        lines.append(
            f"<code>20일  {int(t['d20']):>3}%  </code>{t['sig20']}<code>  ({t['diff20']:+.1f}%p)</code>"
        )
        lines.append(
            f"<code>50일  {int(t['d50']):>3}%  </code>{t['sig50']}<code>  ({t['diff50']:+.1f}%p)</code>"
        )
        lines.append(
            f"<code>RSI   {t['rsi']:.0f}     </code>{t['rsi_sig']}"
        )
        # 줄바꿈 위험 최소화를 위해 문구를 '🎯 50일 목표:'로 간결하게 수정
        lines.append(
            f"🎯 50일 목표: 🟢매수 <code>{t['buy_price']:,.0f}{unit}</code> | 🔴과열 <code>{t['heat_price']:,.0f}{unit}</code>"
        )
        lines.append(t["opinion"])

    lines.append("─────────────────")

    send_telegram_message("\n".join(lines))


if __name__ == "__main__":
    check_market_disparity()

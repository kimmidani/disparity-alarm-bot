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
    if is_index:
        if days == 20:
            return "🔴 과열" if disparity >= 103 else "🟢 매수권" if disparity <= 97 else "⚪ 관망"
        else:
            return "🔴 과열" if disparity >= 110 else "🟢 매수권" if disparity <= 100 else "⚪ 관망"
    else:
        if days == 20:
            return "🔴 과열" if disparity >= 110 else "🟢 매수권" if disparity <= 95 else "⚪ 관망"
        else:
            return "🔴 과열" if disparity >= 125 else "🟢 매수권" if disparity <= 110 else "⚪ 관망"


# RSI 50 이하 기준 변경 및 명칭을 '매수권'으로 수정
def get_rsi_signal(rsi):
    if rsi >= 75:
        return "🔴 과열"
    elif rsi <= 50:
        return "🟢 매수권"
    else:
        return "⚪ 중립"


# RSI 명칭 변경에 따른 종합의견 로직 수정
def get_final_opinion(sig20, sig50, rsi_sig):
    if "매수권" in sig50 and "매수권" in rsi_sig:
        return "💡 종합의견: [적극 매수 검토] 50일선과 RSI가 동시에 매수권(🔥)에 진입한 상태입니다. 주간 고정 매수 타점 이하에서는 분할 매수 접근이 매우 유효합니다."
    elif "매수권" in sig50:
        return "💡 종합의견: [분할매수 검토] 중장기 50일선 매수권 진입 구간입니다."
    elif "매수권" in sig20 and "과열" not in sig50:
        return "💡 종합의견: [분할매수 검토] 단기 20일선 매수 타점에 도달했습니다."
    elif "과열" in sig50 and "과열" in rsi_sig:
        return "💡 종합의견: [익절 / 추가매수 금지] 50일선과 RSI가 동시에 과열(⚠️) 상태이므로 리스크 관리가 필요합니다."
    elif "과열" in sig20 and "과열" in sig50:
        return "💡 종합의견: [신규매수 자제] 20일 및 50일 이격도가 모두 과열되어 추격 매수를 금지합니다."
    elif "과열" in sig50:
        return "💡 종합의견: [신규매수 자제] 중장기 50일선 과열 구간에 머물러 있습니다."
    else:
        return "💡 종합의견: [관망 유지] 현재 뚜렷한 매수/매도 시그널이 없는 안정적인 관망 구간입니다."


def check_market_disparity():
    kst = pytz.timezone("Asia/Seoul")
    now_dt = datetime.now(kst)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

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
        d20 = today["D20"]
        d50 = today["D50"]
        rsi = today["RSI"]
        diff20 = d20 - yesterday["D20"]
        diff50 = d50 - yesterday["D50"]

        # 주간 첫 거래일의 50일선 고정 가격 기능
        current_year, current_week, _ = today.name.isocalendar()
        this_week_mask = [
            x.isocalendar()[0] == current_year and x.isocalendar()[1] == current_week 
            for x in df.index
        ]
        this_week_df = df[this_week_mask]
        
        if not this_week_df.empty:
            ma50_anchor = this_week_df.iloc[0]["MA50"]
        else:
            ma50_anchor = today["MA50"]

        if is_index:
            target_buy = ma50_anchor * 1.00
            target_heat = ma50_anchor * 1.10
            target_buy = round(target_buy / 5) * 5
            target_heat = round(target_heat / 5) * 5
        else:
            target_buy = ma50_anchor * 1.10
            target_heat = ma50_anchor * 1.25
            target_buy = round(target_buy / 1000) * 1000
            target_heat = round(target_heat / 1000) * 1000

        buy_gap = ((target_buy - price) / price) * 100
        heat_gap = ((target_heat - price) / price) * 100

        sig20 = get_disparity_signal(d20, 20, is_index)
        sig50 = get_disparity_signal

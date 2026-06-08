import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import yfinance as yf


def send_telegram_message(message):
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHAT_ID = os.environ.get("CHAT_ID")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


def calculate_rsi(df, window=14):
    """표준 웰레스 와일더(Welles Wilder) 방식의 RSI 계산"""
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=window - 1, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def check_market_disparity():
    tickers = {
        "코스피 지수": "^KS11",
        "삼성전자": "005930.KS",
        "SK하이닉스": "000660.KS",
        "삼성전기": "009150.KS",
    }

    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M")

    stored_results = []
    strong_buys = []
    strong_sells = []

    # 1. 데이터 수집 및 신호 판정
    for name, symbol in tickers.items():
        stock = yf.Ticker(symbol)
        df = stock.history(period="120d")

        if df.empty or len(df) < 50:
            continue

        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["Disp20"] = (df["Close"] / df["MA20"]) * 100
        df["Disp50"] = (df["Close"] / df["MA50"]) * 100
        df["RSI"] = calculate_rsi(df)

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        data = {
            "name": name,
            "current_price": latest["Close"],
            "ma20_price": latest["MA20"],
            "ma50_price": latest["MA50"],
            "disp20": latest["Disp20"],
            "disp50": latest["Disp50"],
            "rsi": latest["RSI"],
            "disp20_change": latest["Disp20"] - prev["Disp20"],
            "disp50_change": latest["Disp50"] - prev["Disp50"],
            "rsi_change": latest["RSI"] - prev["RSI"],
        }
        stored_results.append(data)

        # 자산 타입별 기준점 설정
        if name == "코스피 지수":
            overheat_limit, oversold_limit = 105, 95
        else:
            overheat_limit, oversold_limit = 115, 90

        # 이격도와 RSI 동시 충족 여부 검사
        if data["disp50"] < oversold_limit and data["rsi"] < 30:
            strong_buys.append(name)
        elif data["disp50"] > overheat_limit and data["rsi"] > 70:
            strong_sells.append(name)

    # 2. 메시지 조립
    report_msg = ""

    # [수정 반영] 최상단 특별 강력 시그널 헤드라인 배치
    if strong_buys:
        report_msg += f"🔥 *[역대급 매수 기회 종목 포착]*\n"
        report_msg += (
            f"👉 이격도 침체와 RSI 과매도가 동시 발생한 자산: {', '.join(strong_buys)}\n"
        )
        report_msg += f"----------------------------------------\n\n"
    if strong_sells:
        report_msg += f"⚠️ *[극단적 과열 매도 신호 포착]*\n"
        report_msg += (
            f"👉 이격도 과열과 RSI 과열이 동시 발생한 자산: {', '.join(strong_sells)}\n"
        )
        report_msg += f"----------------------------------------\n\n"

    # 기본 브리핑 정보
    report_msg += f"🔔 *[시장 자산 이격도 & RSI 브리핑]*\n"
    report_msg += f"📅 데이터 기준 시각: {now_kst} (KST)\n\n"
    report_msg += "ℹ️ *[50일 이격도 판단 기준]*\n"
    report_msg += " - 지수: 과열 >105% / 과매도 <95%\n"
    report_msg += " - 종목: 과열 >115% / 과매도 <90%\n"
    report_msg += "ℹ️ *[RSI 판단 기준]*\n"
    report_msg += " - 과열 >70 / 침체 <30\n"
    report_msg += "----------------------------------------\n\n"

    # 자산별 상세 데이터 출력
    for data in stored_results:
        name = data["name"]
        current_price = data["current_price"]
        ma20_price = data["ma20_price"]
        ma50_price = data["ma50_price"]
        disp20 = data["disp20"]
        disp50 = data["disp50"]
        rsi = data["rsi"]

        d20_sign = (
            f"+{data['disp20_change']:.2f}"
            if data["disp20_change"] >= 0
            else f"{data['disp20_change']:.2f}"
        )
        d50_sign = (
            f"+{data['disp50_change']:.2f}"
            if data["disp50_change"] >= 0
            else f"{data['disp50_change']:.2f}"
        )
        rsi_sign = (
            f"+{data['rsi_change']:.2f}"
            if data["rsi_change"] >= 0
            else f"{data['rsi_change']:.2f}"
        )

        report_msg += f"■ *{name}*\n"
        if name == "코스피 지수":
            report_msg += f"- 현재가: {current_price:,.2f}pt\n"
            report_msg += f"- 20일 평균: {ma20_price:,.2f}pt / 50일 평균: {ma50_price:,.2f}pt\n"
            overheat_limit, oversold_limit = 105, 95
        else:
            report_msg += f"- 현재가: {current_price:,.0f}원\n"
            report_msg += f"- 20일 평균: {ma20_price:,.0f}원 / 50일 평균: {ma50_price:,.0f}원\n"
            overheat_limit, oversold_limit = 115, 90

        report_msg += f"- 20일 이격도: {disp20:.2f}% ({d20_sign}%p)\n"
        report_msg += f"- 50일 이격도: *{disp50:.2f}%* ({d50_sign}%p)\n"
        report_msg += f"- RSI (14): {rsi:.2f} ({rsi_sign})\n"

        # 하단 개별 시그널 문구 명시
        if disp50 > overheat_limit:
            signal_text = (
                "📈 *[과열]* 50일선 기준 과열 구간입니다. 분할 익절을 준비하세요."
            )
            if rsi > 70:
                signal_text += " (RSI 과열 동시 진입)"
            report_msg += f"{signal_text}\n"
        elif disp50 < oversold_limit:
            signal_text = "🚨 *[과매도]* 매력적인 진입 구간입니다. 분할 매수를 가동하세요."
            if rsi < 30:
                signal_text += " (RSI 침체 동시 진입! 신뢰도 높음)"
            report_msg += f"{signal_text}\n"
        else:
            report_msg += "⏳ *[안정]* 현재 안정적인 대기 구간입니다.\n"

        report_msg += "\n"

    send_telegram_message(report_msg)


if __name__ == "__main__":
    check_market_disparity()

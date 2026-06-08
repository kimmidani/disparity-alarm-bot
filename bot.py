import os
import pandas as pd
import requests
import yfinance as yf

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


def check_market_disparity():
    tickers = {
        "코스피 지수": "^KS11",
        "삼성전자": "005930.KS",
        "SK하이닉스": "000660.KS",
        "삼성전기": "009150.KS",
    }

    report_msg = "🔔 *[AI 반도체 및 주요 자산 이격도 브리핑]*\n\n"

    for name, symbol in tickers.items():
        stock = yf.Ticker(symbol)
        df = stock.history(period="120d")

        if df.empty:
            continue

        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()

        df["Disp20"] = (df["Close"] / df["MA20"]) * 100
        df["Disp50"] = (df["Close"] / df["MA50"]) * 100

        latest = df.iloc[-1]
        current_price = latest["Close"]
        disp20 = latest["Disp20"]
        disp50 = latest["Disp50"]

        report_msg += f"■ *{name}*\n"
        if name == "코스피 지수":
            report_msg += f"- 현재가: {current_price:,.2f}pt\n"
        else:
            report_msg += f"- 현재가: {current_price:,.0f}원\n"
        report_msg += f"- 20일 이격도: *{disp20:.2f}%*\n"
        report_msg += f"- 50일 이격도: *{disp50:.2f}%*\n"

        if disp20 <= 85:
            report_msg += "🚨 [매수 시그널] 20일선 기준 극단적 과매도! 분할 매수 가동\n"
        elif disp20 >= 115:
            report_msg += "📈 [매도 시그널] 20일선 기준 과열 구간! 분할 익절 준비\n"
        else:
            report_msg += "⏳ 현재 안정적인 관망 대기 구간입니다.\n"
        report_msg += "\n"

    send_telegram_message(report_msg)


if __name__ == "__main__":
    check_market_disparity()

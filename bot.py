```python
import yfinance as yf
import requests
import os
from datetime import datetime
import pytz

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

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


def calculate_mdd(series):
    peak = series.expanding(min_periods=1).max()
    drawdown = (series - peak) / peak
    return drawdown.min() * 100


def get_signal_20(disparity, is_index=False):

    if is_index:
        if disparity >= 105:
            return "🔴 과열"
        elif disparity <= 95:
            return "🟢 매수권"
        else:
            return "⚪ 관망"

    else:
        if disparity >= 115:
            return "🔴 과열"
        elif disparity <= 85:
            return "🟢 매수권"
        else:
            return "⚪ 관망"


def get_signal_50(disparity, is_index=False):

    if is_index:
        if disparity >= 105:
            return "🔴 과열"
        elif disparity <= 95:
            return "🟢 매수권"
        else:
            return "⚪ 관망"

    else:
        if disparity >= 125:
            return "🔴 과열"
        elif disparity <= 110:
            return "🟢 매수권"
        else:
            return "⚪ 관망"


def get_rsi_signal(rsi):

    if rsi >= 70:
        return "🔴 과열"
    elif rsi <= 30:
        return "🟢 침체"
    else:
        return "⚪ 중립"


def get_mdd_signal(mdd):

    if mdd >= -15:
        return "🟢 안정"
    elif mdd >= -25:
        return "⚪ 양호"
    elif mdd >= -35:
        return "🟡 주의"
    elif mdd >= -50:
        return "🟠 위험"
    else:
        return "🔴 고위험"


def get_final_opinion(sig20, sig50, rsi_sig, mdd):

    # 큰 낙폭 경험 종목 우선 체크
    if mdd <= -40:

        if "매수권" in sig50:
            return "💡 [고위험 반등매수] 낙폭과대 구간"

        elif "과열" in sig50:
            return "💡 [익절 검토] 과열 상태이나 변동성 주의"

        else:
            return "💡 [변동성 주의] 과거 큰 손실 이력"

    # 적극 매수
    if "매수권" in sig50 and "침체" in rsi_sig:
        return "💡 [적극 매수 검토] 50일선·RSI 동시 매수권"

    # 분할 매수
    elif "매수권" in sig50:
        return "💡 [분할매수 검토] 50일선 매수권 진입"

    elif "매수권" in sig20 and "과열" not in sig50:
        return "💡 [분할매수 검토] 20일선 매수권 진입"

    # 매도/관망
    elif "과열" in sig50 and "과열" in rsi_sig:
        return "💡 [익절 검토] 50일선·RSI 동시 과열"

    elif "과열" in sig20 and "과열" in sig50:
        return "💡 [신규매수 자제] 20·50일선 모두 과열"

    elif "과열" in sig50:
        return "💡 [신규매수 자제] 50일선 과열 구간"

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

    lines = []

    lines.append("🔔 <b>이격도 &amp; RSI &amp; MDD 브리핑</b>")
    lines.append(f"🕐 {now} KST")

    for name, (symbol, is_index) in tickers.items():

        stock = yf.Ticker(symbol)

        # MDD 계산을 위해 1년 데이터 사용
        df = stock.history(period="1y")

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

        mdd = calculate_mdd(df["Close"])

        sig20 = get_signal_20(d20, is_index)
        sig50 = get_signal_50(d50, is_index)

        rsi_sig = get_rsi_signal(rsi)
        mdd_sig = get_mdd_signal(mdd)

        opinion = get_final_opinion(
            sig20,
            sig50,
            rsi_sig,
            mdd
        )

        unit = "pt" if is_index else "원"

        lines.append("─────────────────")

        lines.append(
            f"<b>📊 {name}</b>  {price:,.0f}{unit}"
        )

        lines.append(
            f"<code>20일  {int(d20):>3}%  </code>{sig20}"
            f"<code>  ({diff20:+.1f}%p)</code>"
        )

        lines.append(
            f"<code>50일  {int(d50):>3}%  </code>{sig50}"
            f"<code>  ({diff50:+.1f}%p)</code>"
        )

        lines.append(
            f"<code>RSI  {rsi:>3.0f}   </code>{rsi_sig}"
        )

        lines.append(
            f"<code>MDD {mdd:>6.1f}% </code>{mdd_sig}"
        )

        lines.append(opinion)

    lines.append("─────────────────")

    send_telegram_message("\n".join(lines))


if __name__ == "__main__":
    check_market_disparity()
```

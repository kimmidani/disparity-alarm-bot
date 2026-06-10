import yfinance as yf
import requests
import os
from datetime import datetime
import pytz

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "여기에_토큰_입력")
CHAT_ID = os.environ.get("CHAT_ID", "여기에_챗ID_입력")

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
    # 시간대 변환의 부작용을 막기 위해 raw 데이터만 추출
    df = yf.Ticker(symbol).history(period="1y", auto_adjust=True)
    return df

def get_consecutive_days(series):
    closes = series.tolist()
    if len(closes) < 2:
        return 0, "보합"

    diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    latest_diff = diffs[-1]

    if latest_diff == 0:
        return 0, "보합"

    is_up = latest_diff > 0
    count = 0
    for d in reversed(diffs):
        if (d > 0) == is_up and d != 0:
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
    now = datetime.now(kst)
    now_str = now.strftime("%Y-%m-%d %H:%M")

    tickers = {
        "코스피":     ("^KS11",     True),
        "삼성전자":   ("005930.KS", False),
        "SK하이닉스": ("000660.KS", False),
        "삼성전기":   ("009150.KS", False),
    }

    lines = ["🔔 <b>주요 기술적지표 브리핑</b>", f"🕐 {now_str}"]

    # 현재 한국 시간 기준으로 장중(09:00 ~ 15:30)인지 확인
    is_market_open = (9 <= now.hour < 15) or (now.hour == 15 and now.minute < 30)

    for name, (symbol, is_index) in tickers.items():
        df = load_stock_data(symbol)
        if df.empty or len(df) < 50:
            continue

        closes_all = df["Close"]

        # 장중일 때는 보조지표(MA, RSI 등) 계산 시 오늘 변동성을 제외하기 위해 전일까지만 사용
        if is_market_open:
            closes_calc = closes_all.iloc[:-1]
        else:
            closes_calc = closes_all

        # 등락률 및 연속 상승/하락은 무조건 오늘 데이터(closes_all)를 포함해 계산
        price = closes_all.iloc[-1]
        prev_price = closes_all.iloc[-2]
        change_rate = ((price - prev_price) / prev_price) * 100

        count, direction = get_consecutive_days(closes_all)

        ma20 = closes_calc.rolling(window=20).mean().iloc[-1]
        ma50 = closes_calc.rolling(window=50).mean().iloc[-1]
        d20  = (price / ma20) * 100
        d50  = (price / ma50) * 100
        rsi  = calc_rsi(closes_calc).iloc[-1]
        mdd  = calculate_mdd(closes_calc)
        drop52 = ((price - closes_calc.max()) / closes_calc.max()) * 100

        sig20   = get_signal_20(d20)
        sig50   = get_signal_50(d50)
        rsi_sig = get_rsi_signal(rsi)
        opinion = get_final_opinion(sig20, sig50, rsi_sig)
        mdd_str = get_mdd_signal(mdd)
        unit    = "pt" if is_index else "원"

        lines.append("<code>─────────────────</code>")
        lines.append(f"📊 <b>{name}</b>  {price:,.0f}{unit} ({change_rate:+.1f}%)")
        lines.append(f"<code>등락   {count}일 연속 {direction}</code>")
        lines.append(f"<code>20일  {int(d20):>3}%  {sig20}</code>")
        lines.append(f"<code>50일  {int(d50):>3}%  {sig50}</code>")
        lines.append(f"<code>RSI   {int(rsi):>3}   {rsi_sig}</code>")
        lines.append(f"<code>52주낙폭  {drop52:>6.1f}%</code>")
        lines.append(f"<code>MDD   {mdd:>6.1f}%  {mdd_str}</code>")
        lines.append(opinion)

    lines.append("<code>─────────────────</code>")
    send_telegram_message("\n".join(lines))

if __name__ == "__main__":
    check_market_disparity()

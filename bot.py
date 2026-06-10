import yfinance as yf
import pandas as pd
import os
from datetime import datetime
import pytz
import requests

# 텔레그램 설정값 (환경변수 또는 직접 입력)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "여기에_토큰_입력")
CHAT_ID = os.environ.get("CHAT_ID", "여기에_챗ID_입력")

def send_telegram_message(message):
    """지정된 텔레그램 방으로 HTML 포맷 메시지를 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("▶ [성공] 텔레그램 브리핑 전송 완료!")
        else:
            print(f"▶ [실패] 텔레그램 전송 실패: {response.text}")
    except Exception as e:
        print(f"▶ 텔레그램 전송 중 에러 발생: {e}")

def get_consecutive_days(series):
    """연속 등락 일수를 계산합니다."""
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
    """RSI(상대강도지수)를 계산합니다."""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calculate_mdd(series):
    """최대 낙폭(MDD)을 계산합니다."""
    if series.empty:
        return 0.0
    peak = series.expanding(min_periods=1).max()
    drawdown = (series - peak) / peak
    return drawdown.min() * 100

def get_signal_20(disparity):
    if pd.isna(disparity): return "⚪관망  "
    if disparity >= 115:  return "🔴과열  "
    elif disparity <= 85: return "🟢매수권"
    return "⚪관망  "

def get_signal_50(disparity):
    if pd.isna(disparity): return "⚪관망  "
    if disparity >= 125:   return "🔴과열  "
    elif disparity <= 110: return "🟢매수권"
    return "⚪관망  "

def get_rsi_signal(rsi):
    if pd.isna(rsi): return "⚪중립  "
    if rsi >= 70:   return "🔴과열  "
    elif rsi <= 30: return "🟢매수권"
    return "⚪중립  "

def get_mdd_signal(mdd):
    if pd.isna(mdd): return "보통"
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

    # 야후 파이낸스 티커 명세
    tickers = {
        "코스피":     ("^KS11",     True),
        "삼성전자":   ("005930.KS", False),
        "SK하이닉스": ("000660.KS", False),
        "삼성전기":   ("009150.KS", False),
    }

    lines = ["🔔 <b>주요 기술적지표 브리핑</b>", f"🕐 {now_str}"]

    for name, (symbol, is_index) in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            # 기술적 지표 계산을 위해 1년치 데이터 수집
            df = ticker.history(period="1y")
            
            if df.empty or len(df) < 50:
                print(f"⚠️ {name}({symbol}) 데이터를 가져오지 못해 스킵합니다.")
                continue

            closes_all = df["Close"]
            price = closes_all.iloc[-1]

            # 지표 계산용 데이터셋 분리 (장중 변동성 왜곡 방지)
            last_date = df.index[-1].date()
            is_intraday = (last_date == now.date()) and (now.hour < 15 or (now.hour == 15 and now.minute < 40))
            closes_calc = closes_all.iloc[:-1] if is_intraday else closes_all

            # 기술적 지표 연산
            ma20 = closes_calc.rolling(window=20).mean().iloc[-1]
            ma50 = closes_calc.rolling(window=50).mean().iloc[-1]
            
            d20 = (price / ma20) * 100 if ma20 and ma20 != 0 else float('nan')
            d50 = (price / ma50) * 100 if ma50 and ma50 != 0 else float('nan')
            
            rsi_series = calc_rsi(closes_calc)
            rsi = rsi_series.iloc[-1] if not rsi_series.empty else float('nan')
            
            mdd = calculate_mdd(closes_calc)
            max_val = closes_calc.max()
            drop52 = ((price - max_val) / max_val) * 100 if max_val and max_val != 0 else float('nan')

            sig20 = get_signal_20(d20)
            sig50 = get_signal_50(d50)
            rsi_sig = get_rsi_signal(rsi)
            opinion = get_final_opinion(sig20, sig50, rsi_sig)
            mdd_str = get_mdd_signal(mdd)

            # 데이터 출력 포맷팅 (NaN 방어 처리)
            d20_str = f"{d20:.0f}" if not pd.isna(d20) else "N/A"
            d50_str = f"{d50:.0f}" if not pd.isna(d50) else "N/A"
            rsi_str = f"{rsi:.0f}" if not pd.isna(rsi) else "N/A"

            lines.append("<code>─────────────────</code>")
            
            # 🔥 코스피 지수와 개별 종목 출력 조건 분기
            if is_index:
                price_fmt = f"{price:,.2f}"
                lines.append(f"📊 <b>{name}</b>  {price_fmt}pt")
                # 코스피는 등락률 및 연속 상승/하락 행을 완전히 제외합니다.
            else:
                prev_price = closes_all.iloc[-2] if len(closes_all) >= 2 else price
                change_rate = ((price - prev_price) / prev_price) * 100 if prev_price != 0 else 0.0
                count, direction = get_consecutive_days(closes_all)
                
                price_fmt = f"{price:,.0f}"
                lines.append(f"📊 <b>{name}</b>  {price_fmt}원 ({change_rate:+.2f}%)")
                lines.append(f"<code>등락   {count}일 연속 {direction}</code>")

            # 하단 공통 지표 출력
            lines.append(f"<code>20일  {d20_str:>3}%  {sig20}</code>")
            lines.append(f"<code>50일  {d50_str:>3}%  {sig50}</code>")
            lines.append(f"<code>RSI   {rsi_str:>3}   {rsi_sig}</code>")
            lines.append(f"<code>52주낙폭  {drop52:>6.1f}%</code>")
            lines.append(f"<code>MDD   {mdd:>6.1f}%  {mdd_str}</code>")
            lines.append(opinion)

        except Exception as e:
            print(f"▶ {name}({symbol}) 처리 중 예외 에러 발생: {e}")
            continue

    lines.append("<code>─────────────────</code>")
    send_telegram_message("\n".join(lines))

if __name__ == "__main__":
    check_market_disparity()

import yfinance as yf
import pandas as pd
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# =========================
# 基本設定 (整合 Threads)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "tw_history.csv")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
# 新增 Threads 設定
THREADS_TOKEN = os.getenv("THREADS_TOKEN", "").strip()
THREADS_USER_ID = "4178792059009185" 

# =========================
# 工具函數 (計算支撐壓力與抓取清單)
# =========================
def calc_pivot(df):
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2*p - h, 1), round(2*p - l, 1)

def get_tw_300():
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        df = pd.read_html(requests.get(url, timeout=10).text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        codes = df["有價證券代號及名稱"].str.split(n=1).str[0].tolist()
        return [c + ".TW" for c in codes if len(c) == 4][:300]
    except:
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW"]

# =========================
# Threads 發文函數
# =========================
def post_to_threads(text):
    if not THREADS_TOKEN:
        print("跳過 Threads：未設定 THREADS_TOKEN")
        return
    
    try:
        # 1. 建立貼文容器
        base_url = f"https://graph.threads.net/v1.0/me/threads"
        payload = {
            "media_type": "TEXT",
            "text": text,
            "access_token": THREADS_TOKEN
        }
        res = requests.post(base_url, data=payload).json()
        
        # 2. 正式發布
        if "id" in res:
            creation_id = res["id"]
            publish_url = f"https://graph.threads.net/v1.0/me/threads_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": THREADS_TOKEN
            }
            requests.post(publish_url, data=publish_payload)
            print("✅ Threads 發文成功！")
        else:
            print(f"❌ Threads 容器建立失敗: {res}")
    except Exception as e:
        print(f"❌ Threads API 錯誤: {e}")

# =========================
# 主程式邏輯
# =========================
def run_prediction():
    symbols = get_tw_300()
    fixed = ["2330.TW", "2317.TW", "2454.TW"]
    all_targets = list(set(symbols + fixed))
    
    results = {}
    for s in all_targets:
        try:
            df = yf.download(s, period="1y", interval="1d", progress=False)
            if len(df) < 50: continue
            
            # 特徵工程
            df["Ret"] = df["Close"].pct_change()
            df["Vol_Change"] = df["Volume"].pct_change()
            df["Target"] = df["Close"].shift(-5).pct_change(5)
            
            train = df.dropna()
            if train.empty: continue
            
            X = train[["Ret", "Vol_Change"]]
            y = train["Target"]
            
            model = XGBRegressor(n_estimators=50, learning_rate=0.1)
            model.fit(X, y)
            
            last_features = [[df["Ret"].iloc[-1], df["Vol_Change"].iloc[-1]]]
            pred_val = model.predict(last_features)[0]
            
            sup, res_p = calc_pivot(df)
            results[s] = {"pred": pred_val, "price": df["Close"].iloc[-1], "sup": sup, "res": res_p}
        except:
            continue

    # 建立報告內容
    report_date = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 台股 AI 進階預測報告 ({report_date})\n"
    msg += "------------------------------------------\n\n"

    medals = ["🥇", "🥈", "🥉", "📈", "📈"]
    horses = {k: v for k, v in results.items() if k not in fixed and v["pred"] > 0}
    top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

    msg += "🏆 AI 海選 Top 5 (潛力黑馬)\n"
    for i, s in enumerate(top_5):
        r = results[s]
        msg += f"{medals[i]} {s}: 預估 {r['pred']:+.2%}\n"
        msg += f" └ 現價: {r['price']:.1f} (支撐: {r['sup']} / 壓力: {r['res']})\n"

    msg += "\n🔍 指定權值股監控\n"
    for s in fixed:
        if s in results:
            r = results[s]
            msg += f"🔹 {s}: 預估 {r['pred']:+.2%}\n"
            msg += f" └ 現價: {r['price']:.1f} (支撐: {r['sup']} / 壓力: {r['res']})\n"

    msg += "\n#台股 #AI選股 #機器學習 #ThreadsAPI"

    # 發送到 Discord (原本功能)
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})
    
    # 發送到 Threads (新功能)
    post_to_threads(msg)
    print(msg)

if __name__ == "__main__":
    run_prediction()

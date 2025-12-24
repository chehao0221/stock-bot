import yfinance as yf
import pandas as pd
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# =========================
# 基本設定
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "tw_history.csv")
# 從 GitHub Secrets 讀取權杖
THREADS_TOKEN = os.getenv("THREADS_TOKEN", "").strip()

# =========================
# 工具函數
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
        return ["2330.TW", "2317.TW", "2454.TW"]

# =========================
# Threads 發文邏輯
# =========================
def post_to_threads(text):
    if not THREADS_TOKEN:
        print("⚠️ 找不到 THREADS_TOKEN，跳過發文")
        return
    try:
        # 1. 建立貼文容器
        res = requests.post(
            "https://graph.threads.net/v1.0/me/threads",
            data={"media_type": "TEXT", "text": text, "access_token": THREADS_TOKEN}
        ).json()
        
        # 2. 正式發布
        if "id" in res:
            requests.post(
                "https://graph.threads.net/v1.0/me/threads_publish",
                data={"creation_id": res["id"], "access_token": THREADS_TOKEN}
            )
            print("✅ Threads 報告發送成功！")
        else:
            print(f"❌ Threads 容器建立失敗: {res}")
    except Exception as e:
        print(f"❌ Threads 錯誤: {e}")

# =========================
# 主預測程式
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
        except: continue

    # 建立報告內容
    report_date = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 台股 AI 預測報告 ({report_date})\n"
    msg += "----------------------------------\n\n"

    horses = {k: v for k, v in results.items() if k not in fixed and v["pred"] > 0}
    top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

    msg += "🏆 AI 海選潛力股\n"
    for s in top_5:
        r = results[s]
        msg += f" {s}: 預估 {r['pred']:+.2%}\n └ 現價: {r['price']:.1f} (支撐: {r['sup']})\n"

    msg += "\n🔍 權值標竿監控\n"
    for s in fixed:
        if s in results:
            r = results[s]
            msg += f"🔹 {s}: {r['pred']:+.2%}\n"

    msg += "\n#台股 #AI選股 #ThreadsAPI"
    post_to_threads(msg)

if __name__ == "__main__":
    run_prediction()

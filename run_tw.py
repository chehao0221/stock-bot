import yfinance as yf
import pandas as pd
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime
import warnings
import time

warnings.filterwarnings("ignore")

# =========================
# 基本設定
# =========================
THREADS_TOKEN = os.getenv("THREADS_TOKEN", "").strip()

def calc_pivot(df):
    try:
        r = df.iloc[-20:]
        h = float(r["High"].max())
        l = float(r["Low"].min())
        c = float(df["Close"].iloc[-1])
        p = (h + l + c) / 3
        return round(2*p - h, 1), round(2*p - l, 1)
    except:
        return 0.0, 0.0

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

def post_to_threads(text):
    if not THREADS_TOKEN:
        print("❌ 錯誤：環境變數 THREADS_TOKEN 為空，請檢查 GitHub Secrets 設定。")
        return
    
    base_url = "https://graph.threads.net/v1.0/me"
    
    try:
        # 第一步：建立貼文容器 (Media Container)
        print("🚀 正在建立 Threads 貼文容器...")
        res = requests.post(
            f"{base_url}/threads",
            data={"media_type": "TEXT", "text": text, "access_token": THREADS_TOKEN}
        ).json()
        
        if "id" not in res:
            print(f"❌ 建立容器失敗！API 回傳：{res}")
            return

        creation_id = res["id"]
        print(f"✅ 容器建立成功 (ID: {creation_id})，準備正式發布...")

        # 稍微等候 2 秒確保後台處理完成
        time.sleep(2)

        # 第二步：正式發布貼文 (Publish)
        pub_res = requests.post(
            f"{base_url}/threads_publish",
            data={"creation_id": creation_id, "access_token": THREADS_TOKEN}
        ).json()
        
        if "id" in pub_res:
            print(f"🎉 貼文發布成功！Threads 貼文 ID: {pub_res['id']}")
        else:
            print(f"❌ 發布失敗！錯誤詳情：{pub_res}")
            
    except Exception as e:
        print(f"❌ 發生未預期錯誤: {e}")

def run_prediction():
    symbols = get_tw_300()
    fixed = ["2330.TW", "2317.TW", "2454.TW"]
    all_targets = list(set(symbols + fixed))
    
    results = {}
    print(f"🔍 正在分析 {len(all_targets)} 檔標的...")
    
    for s in all_targets:
        try:
            df = yf.download(s, period="1y", interval="1d", progress=False)
            if len(df) < 50: continue
            
            df["Close"] = pd.to_numeric(df["Close"], errors='coerce')
            df["Volume"] = pd.to_numeric(df["Volume"], errors='coerce')
            
            df["Ret"] = df["Close"].pct_change()
            df["Vol_Change"] = df["Volume"].pct_change()
            df["Target"] = df["Close"].shift(-5).pct_change(5)
            
            train = df.dropna()
            if train.empty: continue
            
            X = train[["Ret", "Vol_Change"]]
            y = train["Target"]
            
            model = XGBRegressor(n_estimators=50, learning_rate=0.1)
            model.fit(X, y)
            
            last_ret = float(df["Ret"].iloc[-1])
            last_vol = float(df["Vol_Change"].iloc[-1])
            pred_val = float(model.predict([[last_ret, last_vol]])[0])
            
            price_val = float(df["Close"].iloc[-1])
            sup, _ = calc_pivot(df)
            
            results[s] = {"pred": pred_val, "price": price_val, "sup": sup}
        except:
            continue

    # --- 建立報告內容 ---
    report_date = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 台股 AI 預測報告 ({report_date})\n"
    msg += "----------------------------------\n\n"

    horses = {k: v for k, v in results.items() if k not in fixed and v["pred"] > 0}
    top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

    msg += "🏆 AI 海選潛力股\n"
    for s in top_5:
        r = results[s]
        msg += f" {s}: 預估 {r['pred']:+.2%}\n └ 現價: {r['price']:.1f} (支撐: {r['sup']:.1f})\n"

    msg += "\n🔍 權值標竿監控\n"
    for s in fixed:
        if s in results:
            r = results[s]
            msg += f"🔹 {s}: {r['pred']:+.2%}\n"

    msg += "\n---\n"
    msg += "🚀 想要看更完整的勝率對帳與更多標的嗎？\n"
    msg += "歡迎加入我們的 Discord 社群，與 AI 交易者一同交流！\n"
    msg += "🔗 https://discord.gg/aGzhSd2A5d\n\n"
    msg += "#台股 #AI選股 #機器學習 #ThreadsAPI"

    post_to_threads(msg)

if __name__ == "__main__":
    run_prediction()

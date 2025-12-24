import yfinance as yf
import pandas as pd
import requests
import os
from xgboost import XGBRegressor
from datetime import datetime
import warnings
import time
import sys

warnings.filterwarnings("ignore")

THREADS_TOKEN = os.getenv("THREADS_TOKEN", "").strip()

def post_to_threads_logic(text):
    base_url = "https://graph.threads.net/v1.0/me"
    # 1. 建立容器
    resp = requests.post(
        f"{base_url}/threads",
        data={"media_type": "TEXT", "text": text, "access_token": THREADS_TOKEN}
    )
    
    # 偵錯：如果不是 200，印出原始文字
    if resp.status_code != 200:
        print(f"⚠️ API 狀態碼異常: {resp.status_code}, 內容: {resp.text}")
        return None

    res_json = resp.json()
    creation_id = res_json.get("id")
    if not creation_id:
        return None

    time.sleep(5) 

    # 2. 正式發布
    pub_resp = requests.post(
        f"{base_url}/threads_publish",
        data={"creation_id": creation_id, "access_token": THREADS_TOKEN}
    )
    return pub_resp.json() if pub_resp.status_code == 200 else None

def post_to_threads(full_text):
    if not THREADS_TOKEN:
        print("❌ 錯誤：找不到 THREADS_TOKEN")
        sys.exit(1)

    print("🚀 嘗試發布完整內容 (含網址)...")
    result = post_to_threads_logic(full_text)
    
    if result and "id" in result:
        print(f"🎉 完整內容發布成功！ID: {result['id']}")
    else:
        print("⚠️ 完整內容發布失敗，嘗試發送【純文字去連結版】...")
        # 移除連結部分再試一次
        clean_text = full_text.split("---")[0] + "\n#台股 #AI預測"
        result_clean = post_to_threads_logic(clean_text)
        
        if result_clean and "id" in result_clean:
            print(f"✅ 純文字版發布成功！這代表你的 Discord 網址暫時被 Threads 屏蔽了。")
        else:
            print(f"❌ 全部失敗。請檢查您的 Token 是否具備 threads_content_publish 權限。")
            sys.exit(1)

def run_prediction():
    # ... (此處保留原本的數據抓取與分析邏輯) ...
    # 為了簡化，假設你已經抓到 results, fixed, top_5
    
    symbols = get_tw_300()
    fixed = ["2330.TW", "2317.TW", "2454.TW"]
    all_targets = list(set(symbols + fixed))
    results = {}
    
    print(f"🔍 正在分析台股標的...")
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
            model = XGBRegressor(n_estimators=50, learning_rate=0.1)
            model.fit(train[["Ret", "Vol_Change"]], train["Target"])
            pred = float(model.predict([[float(df["Ret"].iloc[-1]), float(df["Vol_Change"].iloc[-1])]])[0])
            results[s] = {"pred": pred, "price": float(df["Close"].iloc[-1])}
        except: continue

    report_date = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 台股 AI 預測報告 ({report_date})\n"
    msg += "----------------------------------\n\n🏆 AI 海選潛力股\n"
    
    horses = {k: v for k, v in results.items() if k not in fixed and v["pred"] > 0}
    top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]
    for s in top_5:
        msg += f" {s}: 預估 {results[s]['pred']:+.2%}\n"

    msg += "\n---\n🚀 更多分析請見 Discord\n🔗 https://discord.gg/aGzhSd2A5d"
    
    post_to_threads(msg)

def get_tw_300():
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        df = pd.read_html(requests.get(url, timeout=10).text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        codes = df["有價證券代號及名稱"].str.split(n=1).str[0].tolist()
        return [c + ".TW" for c in codes if len(c) == 4][:300]
    except: return ["2330.TW"]

if __name__ == "__main__":
    run_prediction()

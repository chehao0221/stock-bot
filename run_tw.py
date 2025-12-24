import yfinance as yf
import pandas as pd
import requests
import os
import sys
import time
import warnings
from xgboost import XGBRegressor
from datetime import datetime
from utils.market_calendar import is_market_open

warnings.filterwarnings("ignore")

# =========================
# 基本設定與 Secrets 讀取
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "tw_history.csv")
# 讀取 GitHub Secrets 的 Threads Token
THREADS_TOKEN = os.getenv("THREADS_TOKEN", "").strip()

# =========================
# 工具函數
# =========================
def pre_check():
    """檢查今日是否開盤"""
    if not is_market_open("TW"):
        print("📌 因假日或節日，股市未開盤，停止動作")
        return False
    return True

def calc_pivot(df):
    """計算支撐與壓力位"""
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2*p - h, 1), round(2*p - l, 1)

def get_tw_300():
    """抓取台股前 300 檔清單網址"""
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        res = requests.get(url, timeout=10)
        df = pd.read_html(res.text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        codes = df["有價證券代號及名稱"].str.split("　").str[0]
        codes = codes[codes.str.len() == 4].head(300)
        return [f"{c}.TW" for c in codes]
    except Exception as e:
        print(f"⚠️ 抓取網址失敗: {e}，改用預設權值股")
        return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW"]

# =========================
# Threads 發布函數
# =========================
def post_to_threads(content):
    if not THREADS_TOKEN:
        print("⏭️ 找不到 THREADS_TOKEN，無法發布到 Threads。")
        return

    base_url = "https://graph.threads.net/v1.0"
    try:
        # 1. 獲取 User ID
        me_res = requests.get(f"{base_url}/me?fields=id&access_token={THREADS_TOKEN}")
        user_id = me_res.json().get("id")

        # 2. 建立貼文容器 (確保不超過 500 字)
        payload = {
            "media_type": "TEXT",
            "text": content[:490],
            "access_token": THREADS_TOKEN
        }
        container_res = requests.post(f"{base_url}/{user_id}/threads", data=payload)
        creation_id = container_res.json().get("id")

        print(f"⏳ Threads 容器已建立，等待 15 秒進行伺服器同步...")
        time.sleep(15)

        # 3. 正式發布
        publish_res = requests.post(
            f"{base_url}/{user_id}/threads_publish",
            data={"creation_id": creation_id, "access_token": THREADS_TOKEN}
        )
        if publish_res.status_code == 200:
            print("🎉 Threads AI 報告發布成功！")
        else:
            print(f"❌ Threads 發布失敗: {publish_res.text}")
    except Exception as e:
        print(f"💥 Threads 功能異常: {e}")

# =========================
# 主程式
# =========================
def run():
    # 設定固定監控的權值股
    fixed = ["2330.TW", "2317.TW", "2454.TW", "0050.TW", "2308.TW", "2382.TW"]
    watch = list(dict.fromkeys(fixed + get_tw_300()))

    print(f"🚀 開始分析 {len(watch)} 檔台股標的...")
    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 150: continue

            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res_price = calc_pivot(df)

            results[s] = {
                "pred": pred,
                "price": round(df["Close"].iloc[-1], 2),
                "sup": sup,
                "res": res_price
            }
        except:
            continue

    # --- 建立報告內容 ---
    today_str = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 AI 台股盤後報告 ({today_str})\n"
    msg += "--------------------------\n"
    
    horses = {k: v for k, v in results.items() if k not in fixed and v["pred"] > 0}
    top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

    msg += "🏆 AI 海選潛力黑馬：\n"
    for s in top_5:
        r = results[s]
        msg += f"• {s}: 預估 {r['pred']:+.2%}\n  (現價:{r['price']} 支撐:{r['sup']})\n"

    msg += "\n🔍 權值股監控：\n"
    for s in fixed[:3]: # 為符合字數限制，僅取前三
        if s in results:
            r = results[s]
            msg += f"• {s}: 預估 {r['pred']:+.2%}\n"

    msg += "\n💡 AI 模型僅供參考，不構成投資建議。"

    # --- 執行 Threads 發布 ---
    post_to_threads(msg)

    # --- 儲存歷史紀錄至 CSV ---
    hist = [{
        "date": today_str,
        "symbol": s,
        "entry_price": results[s]["price"],
        "pred_ret": results[s]["pred"],
        "settled": False
    } for s in (top_5 + fixed) if s in results]

    if hist:
        new_df = pd.DataFrame(hist)
        new_df.to_csv(HISTORY_FILE, mode="a", header=not os.path.exists(HISTORY_FILE), index=False)
        print(f"✅ 歷史數據已存入 {HISTORY_FILE}")

if __name__ == "__main__":
    if pre_check():
        run()

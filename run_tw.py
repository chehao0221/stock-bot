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
THREADS_TOKEN = os.getenv("THREADS_TOKEN", "").strip()

# =========================
# 工具函數
# =========================
def pre_check():
    """
    檢查今日是否開盤。
    如果是 GitHub Actions 手動觸發 (workflow_dispatch)，則強制執行。
    """
    is_manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
    
    if is_manual:
        print("⚡ 手動強制執行模式：跳過開休市檢查，直接抓取最近交易日資料。")
        return True
        
    if not is_market_open("TW"):
        print("📌 因假日或節日，股市未開盤，停止動作。")
        return False
    return True

def calc_pivot(df):
    """計算支撐與壓力位"""
    r = df.iloc[-20:]
    h, l, c = r["High"].max(), r["Low"].min(), r["Close"].iloc[-1]
    p = (h + l + c) / 3
    return round(2*p - h, 1), round(2*p - l, 1)

def get_tw_300():
    """直接從證交所抓取台股清單 (Mode 2 為上市)"""
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
        print(f"⚠️ 抓取網址失敗: {e}，改用預設權值股。")
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
        me_res = requests.get(f"{base_url}/me?fields=id&access_token={THREADS_TOKEN}")
        user_id = me_res.json().get("id")

        payload = {
            "media_type": "TEXT",
            "text": content[:495], # 確保不超過 Threads 限制
            "access_token": THREADS_TOKEN
        }
        container_res = requests.post(f"{base_url}/{user_id}/threads", data=payload)
        creation_id = container_res.json().get("id")

        print(f"⏳ Threads 容器已建立，等待 15 秒同步...")
        time.sleep(15)

        publish_res = requests.post(
            f"{base_url}/{user_id}/threads_publish",
            data={"creation_id": creation_id, "access_token": THREADS_TOKEN}
        )
        if publish_res.status_code == 200:
            print("🎉 Threads AI 5日預測報告發布成功！")
        else:
            print(f"❌ 發布失敗: {publish_res.text}")
    except Exception as e:
        print(f"💥 Threads 功能異常: {e}")

# =========================
# 主程式
# =========================
def run():
    fixed = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"]
    watch = list(dict.fromkeys(fixed + get_tw_300()))

    print(f"🚀 啟動 AI 5日預測分析 (監控 {len(watch)} 檔台股)...")
    data = yf.download(watch, period="2y", auto_adjust=True, group_by="ticker", progress=False)

    feats = ["mom20", "bias", "vol_ratio"]
    results = {}

    for s in watch:
        try:
            df = data[s].dropna()
            if len(df) < 150: continue

            # --- AI 核心邏輯：預測未來 5 個交易日 ---
            df["mom20"] = df["Close"].pct_change(20)
            df["bias"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).mean()
            df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            df["target"] = df["Close"].shift(-5) / df["Close"] - 1 # 5日回報率

            train = df.iloc[:-5].dropna()
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
            model.fit(train[feats], train["target"])

            pred = float(model.predict(df[feats].iloc[-1:])[0])
            sup, res_price = calc_pivot(df)

            results[s] = {
                "pred": pred,
                "price": round(df["Close"].iloc[-1], 2),
                "sup": sup
            }
        except:
            continue

    # --- 建立報告內容 ---
    today_str = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 AI 台股預測報告 ({today_str})\n"
    msg += "🎯 目標：預測未來 5 個交易日漲幅\n"
    msg += "--------------------------\n"
    
    horses = {k: v for k, v in results.items() if k not in fixed and v["pred"] > 0}
    top_5 = sorted(horses, key=lambda x: horses[x]["pred"], reverse=True)[:5]

    msg += "🏆 AI 海選 5日潛力黑馬：\n"
    for s in top_5:
        r = results[s]
        msg += f"• {s}: 預估 {r['pred']:+.2%} (現價:{r['price']})\n"

    msg += "\n📈 本系統每日自動海選，數據完全透明。"
    msg += f"\n\n🔗 加入 Discord 交流 AI 選股：\nhttps://discord.gg/aGzhSd2A5d"
    
    # 豐富標籤增加曝光
    msg += "\n\n#AI #台股 #選股機器人 #機器學習 #量化投資 #5日預測 #XGBoost #股市分析"

    # --- 執行發布 ---
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
        pd.DataFrame(hist).to_csv(HISTORY_FILE, mode="a", header=not os.path.exists(HISTORY_FILE), index=False)
        print(f"✅ 預測紀錄已成功儲存。")

if __name__ == "__main__":
    if pre_check():
        run()

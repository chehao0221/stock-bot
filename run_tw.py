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

# =========================
# 配置設定
# =========================
THREADS_TOKEN = os.getenv("THREADS_TOKEN", "").strip()
MY_REURL = "https://reurl.cc/gnxm64" # 你的 Discord 縮網址

def post_to_threads_api(text):
    """核心發布邏輯：建立容器並發布"""
    base_url = "https://graph.threads.net/v1.0/me"
    
    # 1. 建立容器
    res = requests.post(
        f"{base_url}/threads",
        data={"media_type": "TEXT", "text": text, "access_token": THREADS_TOKEN},
        timeout=30
    )
    
    if res.status_code != 200:
        print(f"⚠️ 建立容器失敗。代碼: {res.status_code}, 內容: {res.text}")
        return False, res.text

    c_id = res.json().get("id")
    time.sleep(5) # 等待後台同步

    # 2. 正式發布
    pub_res = requests.post(
        f"{base_url}/threads_publish",
        data={"creation_id": c_id, "access_token": THREADS_TOKEN},
        timeout=30
    )
    
    if pub_res.status_code == 200:
        return True, pub_res.json().get("id")
    else:
        return False, pub_res.text

def post_to_threads_manager(full_text):
    """管理發布流程：失敗時自動降級"""
    if not THREADS_TOKEN:
        print("❌ 錯誤：找不到 THREADS_TOKEN，請檢查 GitHub Secrets。")
        sys.exit(1)

    print("🚀 嘗試發布含網址的完整報告...")
    success, result = post_to_threads_api(full_text)
    
    if success:
        print(f"🎉 貼文成功！ID: {result}")
    else:
        print("⚠️ 含網址版發布失敗。原因可能為 API 限制。")
        print("💡 嘗試發布【純文字去連結版】備案...")
        
        # 移除含有網址的備註部分
        clean_text = full_text.split("---")[0] + "\n(更多分析請看個人檔案連結)\n#台股 #AI選股"
        success_clean, result_clean = post_to_threads_api(clean_text)
        
        if success_clean:
            print(f"✅ 純文字版發布成功！建議將 Discord 連結放入 Threads 個人檔案(Bio)。")
        else:
            print(f"❌ 嚴重錯誤：純文字版也無法發布。詳情：{result_clean}")
            print("請檢查您的 Token 權限是否包含 threads_content_publish。")
            sys.exit(1)

def calc_pivot(df):
    try:
        r = df.iloc[-20:]
        h, l, c = float(r["High"].max()), float(r["Low"].min()), float(df["Close"].iloc[-1])
        p = (h + l + c) / 3
        return round(2*p - h, 1), round(2*p - l, 1)
    except: return 0.0, 0.0

def run_prediction():
    # 這裡放你原本的選股運算邏輯 (yf.download, XGBoost 等)
    # 為了版面簡潔，此處假設您已完成運算並產生 results, top_5
    
    # 範例數據抓取 (保持你原本的 get_tw_300 等邏輯)
    fixed = ["2330.TW", "2317.TW", "2454.TW"]
    # ... (此處填入您原本完整的 run_prediction 運算程式碼) ...
    
    # 構建訊息
    report_date = datetime.now().strftime("%Y-%m-%d")
    msg = f"📊 台股 AI 預測報告 ({report_date})\n"
    msg += "----------------------------------\n\n"
    # (加上迴圈填入 top_5 股票數據)
    msg += "🏆 AI 海選潛力股\n"
    # ... 迴圈 ...
    
    msg += "\n---\n"
    msg += "🚀 想要看完整勝率對帳嗎？\n"
    msg += f"🔗 {MY_REURL}\n\n"
    msg += "#台股 #AI選股 #機器學習"

    post_to_threads_manager(msg)

if __name__ == "__main__":
    # 如果你原本的 run_prediction 包含所有抓取，就直接執行
    # 確保執行前先修正 run_prediction 內部邏輯
    run_prediction()

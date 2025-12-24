import requests
import os
import sys
import time

# 1. 設定區：從 GitHub Secrets 讀取資料
# 請確保 GitHub Actions Secrets 中已設定 THREADS_TOKEN
TOKEN = os.getenv("THREADS_TOKEN", "").strip()

# 這裡填入你抓取資料的網址
DATA_URL = "https://your-data-source-url.com/api" 

def fetch_market_data():
    """從指定網址抓取選股或盤後資料"""
    try:
        print(f"📡 正在從網址抓取最新資料...")
        # 設定 timeout 防止網址沒回應導致程式卡死
        response = requests.get(DATA_URL, timeout=15)
        response.raise_for_status()
        
        # 假設網址回傳的是純文字，若是 JSON 則改用 response.json()
        raw_data = response.text
        
        # --- 資料格式化 (Threads 限制 500 字以內) ---
        # 這裡你可以根據抓回來的資料內容做字串處理
        header = "📈 【AI 台股盤後選股報告】\n\n"
        footer = "\n\n#台股 #AI選股 #自動化發文"
        
        # 確保內容不超過 500 字，預留空間給 Header 和 Footer
        content = raw_data[:400] 
        
        formatted_msg = f"{header}{content}{footer}"
        return formatted_msg
        
    except Exception as e:
        print(f"❌ 抓取網址資料失敗: {e}")
        return None

def post_to_threads():
    if not TOKEN:
        print("❌ 錯誤：找不到 THREADS_TOKEN，請檢查 GitHub Secrets。")
        sys.exit(1)

    # 執行資料抓取
    post_content = fetch_market_data()
    if not post_content:
        print("⚠️ 無法取得發布內容，停止執行。")
        sys.exit(1)

    base_url = "https://graph.threads.net/v1.0"

    try:
        # --- 第一階段：身分檢查 (獲取 User ID) ---
        me_res = requests.get(f"{base_url}/me?fields=id&access_token={TOKEN}")
        if me_res.status_code != 200:
            print(f"❌ 身分檢查失敗: {me_res.text}")
            sys.exit(1)
        
        user_id = me_res.json().get("id")
        print(f"✅ 成功識別使用者 ID: {user_id}")

        # --- 第二階段：建立貼文容器 (TEXT 模式) ---
        payload = {
            "media_type": "TEXT",
            "text": post_content,
            "access_token": TOKEN
        }
        
        print(f"🚀 正在建立貼文容器...")
        container_res = requests.post(f"{base_url}/{user_id}/threads", data=payload)
        
        if container_res.status_code != 200:
            print(f"❌ 建立容器失敗: {container_res.text}")
            sys.exit(1)
            
        creation_id = container_res.json().get("id")
        print(f"✅ 容器已建立 (ID: {creation_id})，等待 15 秒確保伺服器同步...")

        # --- 第三階段：緩衝等待 (解決 Media Not Found 關鍵) ---
        time.sleep(15) 

        # --- 第四階段：正式發布貼文 ---
        print(f"📣 正在執行發布指令...")
        publish_res = requests.post(
            f"{base_url}/{user_id}/threads_publish",
            data={
                "creation_id": creation_id, 
                "access_token": TOKEN
            }
        )

        if publish_res.status_code == 200:
            print(f"🎉🎉🎉 恭喜！網址資料已成功發布至 Threads！")
            print(f"🔗 貼文 ID: {publish_res.json().get('id')}")
        else:
            print(f"❌ 發布失敗: {publish_res.text}")
            sys.exit(1)

    except Exception as e:
        print(f"💥 程式執行發生異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    post_to_threads()

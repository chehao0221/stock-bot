import requests
import os
import sys
import time

# 1. 設定區：從 GitHub Secrets 讀取 Token
TOKEN = os.getenv("THREADS_TOKEN", "").strip()

def post_to_threads():
    if not TOKEN:
        print("❌ 錯誤：找不到 THREADS_TOKEN，請檢查 GitHub Secrets 設定。")
        sys.exit(1)

    base_url = "https://graph.threads.net/v1.0"

    try:
        # --- 第一階段：身分檢查 ---
        me_res = requests.get(f"{base_url}/me?fields=id&access_token={TOKEN}")
        if me_res.status_code != 200:
            print(f"❌ 身分檢查失敗，請確認 Token 或手機端是否接受邀請: {me_res.text}")
            sys.exit(1)
        
        user_id = me_res.json().get("id")
        print(f"✅ 成功識別使用者 ID: {user_id}")

        # --- 第二階段：建立貼文容器 ---
        # 這裡的 text 你可以修改為你原本抓股票資訊的變數，例如 msg
        post_content = "🚀 AI 自動選股報告測試成功！\n這是一則來自 GitHub Actions 的自動發文系統。"
        
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
            published_id = publish_res.json().get("id")
            print(f"🎉🎉🎉 恭喜！貼文已正式發布成功！")
            print(f"🔗 貼文 ID: {published_id}")
            return True
        else:
            # 如果失敗，印出詳細原因，幫助除錯
            print(f"❌ 發布失敗回傳: {publish_res.text}")
            sys.exit(1)

    except Exception as e:
        print(f"💥 程式執行發生嚴重異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    post_to_threads()

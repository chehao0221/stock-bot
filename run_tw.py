import requests
import os
import sys

TOKEN = os.getenv("THREADS_TOKEN", "").strip()

def force_debug_post():
    if not TOKEN:
        print("❌ 錯誤：找不到 TOKEN")
        return

    # 1. 抓取正確的 User ID
    me_url = f"https://graph.threads.net/v1.0/me?fields=id&access_token={TOKEN}"
    try:
        me_res = requests.get(me_url)
        if me_res.status_code != 200:
            print(f"❌ 無法獲取身分 (500錯誤通常源於此)。回傳：{me_res.text}")
            return
        
        user_id = me_res.json().get("id")
        print(f"✅ 成功識別使用者 ID: {user_id}")

        # 2. 建立容器 (嘗試最簡單的文字)
        post_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
        res = requests.post(post_url, data={
            "media_type": "TEXT",
            "text": "Final Test: Connection Stable.",
            "access_token": TOKEN
        })
        
        if res.status_code != 200:
            print(f"❌ 容器建立失敗。代碼: {res.status_code}, 原因: {res.text}")
            return

        c_id = res.json().get("id")
        print(f"✅ 容器已建立 ({c_id})，執行發布...")

        # 3. 正式發布
        pub_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
        pub_res = requests.post(pub_url, data={
            "creation_id": c_id,
            "access_token": TOKEN
        })
        
        if pub_res.status_code == 200:
            print("🎉🎉 恭喜！貼文已正式出現在 Threads 上！")
        else:
            print(f"❌ 發布失敗：{pub_res.text}")

    except Exception as e:
        print(f"💥 程式執行異常: {e}")

if __name__ == "__main__":
    force_debug_post()

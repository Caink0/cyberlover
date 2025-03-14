# import 區塊：放在檔案頂部
import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 建立 Flask 應用
app = Flask(__name__)

# 從環境變量載入 LINE 與 x.ai 的憑證
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
xai_api_key = os.getenv("XAI_API_KEY")

# 用戶角色個性：記憶體內儲存
user_personalities = {}

# Webhook 路由：只保留一次
@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK", 200

# 處理用戶訊息：只保留一個 handle_message
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # 用戶尚未設定個性 → 提示設定
    if user_id not in user_personalities:
        if user_message.startswith("設定角色："):
            personality = user_message.replace("設定角色：", "").strip()
            user_personalities[user_id] = personality
            reply = f"角色個性已設定為：{personality}"
        else:
            reply = "您好，請先告訴我您希望機器人的個性（例如：幽默、友好、嚴肅）\n您可以輸入：設定角色：幽默"
            return line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    else:
        # 若已設定個性，再次使用「設定角色：」開頭可更新個性
        if user_message.startswith("設定角色："):
            personality = user_message.replace("設定角色：", "").strip()
            user_personalities[user_id] = personality
            reply = f"角色個性已更新為：{personality}"
        else:
            # 呼叫 x.ai，根據個性生成對話回應
            personality = user_personalities.get(user_id, "友好")
            reply = call_xai_api(user_message, personality)

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

def call_xai_api(message, personality):
    # 根據 x.ai 官方文件更新端點 / 參數
    url = "https://api.x.ai/v1/generate"
    headers = {"Authorization": f"Bearer {xai_api_key}"}
    payload = {
        "prompt": f"以{personality}的個性回應：{message}",
        "max_tokens": 100
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json().get("text", "抱歉，無法生成回應")
    except Exception as e:
        # 若 API 呼叫失敗或超時，可以在此紀錄並回傳預設訊息
        print(f"x.ai API Error: {e}")
        return "抱歉，目前無法取得回應。"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

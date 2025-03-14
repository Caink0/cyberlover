from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
from flask import Flask

app = Flask(__name__)

# 您的應用程式邏輯...

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # 使用 Render 提供的 PORT，若無則默認 5000
    app.run(host="0.0.0.0", port=port)   # 監聽所有 IP 地址


# 從環境變量中獲取憑證
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
xai_api_key = os.getenv('XAI_API_KEY')

# 儲存每個用戶的角色個性
user_personalities = {}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # 如果此用戶尚未設定角色個性
    if user_id not in user_personalities:
        # 如果用戶以類似"設定角色："的指令來設定，就直接更新設定
        if user_message.startswith("設定角色："):
            personality = user_message.replace("設定角色：", "").strip()
            user_personalities[user_id] = personality
            reply = f"角色個性已設定為：{personality}"
        else:
            # 若用戶尚未設定，先詢問他們希望的個性
            reply = "您好，請先告訴我您希望機器人的個性，例如：幽默、友好、嚴肅。您可以直接輸入想要的個性。"
            # 直接回覆詢問，並提前返回，避免繼續執行後面的邏輯
            return line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )
    else:
        # 如果用戶已設定個性，但又想更新個性，可以再次使用指令
        if user_message.startswith("設定角色："):
            personality = user_message.replace("設定角色：", "").strip()
            user_personalities[user_id] = personality
            reply = f"角色個性已更新為：{personality}"
        else:
            # 使用用戶已設定的個性進行對話回應
            personality = user_personalities.get(user_id, "友好")
            xai_response = call_xai_api(user_message, personality)
            reply = xai_response

    # 回覆用戶
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

@app.route("/webhook", methods=['POST'])
def webhook():
    # 驗證簽名
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global character_personality
    user_message = event.message.text

    # 檢查是否為角色個性設定
    if user_message.startswith("設定角色："):
        character_personality = user_message.replace("設定角色：", "")
        reply = f"角色個性已設定為：{character_personality}"
    else:
        # 呼叫 x.ai API 生成回應
        xai_response = call_xai_api(user_message, character_personality)
        reply = xai_response

    # 回覆用戶
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

def call_xai_api(message, personality):
    # 假設 x.ai API 的端點和參數（請根據官方文件調整）
    url = "https://api.x.ai/v1/generate"
    headers = {"Authorization": f"Bearer {xai_api_key}"}
    payload = {
        "prompt": f"以{personality}的個性回應：{message}",
        "max_tokens": 100
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json().get("text", "抱歉，無法生成回應")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

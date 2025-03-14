from flask import Flask, request, abort
import logging
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import requests

app = Flask(__name__)

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 從環境變量中獲取憑證
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
XAI_API_KEY = os.getenv('XAI_API_KEY')

# 檢查環境變量是否已設定
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET or not XAI_API_KEY:
    logger.error("環境變量未正確設定，請檢查 LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET 和 XAI_API_KEY")
    raise ValueError("環境變量未正確設定")

# 初始化 LINE Bot
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# x.ai API 設置
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {XAI_API_KEY}"
}

# 儲存每個用戶的角色個性
user_personalities = {}

# Webhook 路由
@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logger.info("Received webhook: %s", body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)
    return 'OK', 200

# 處理訊息事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    logger.info("Message received from user %s: %s", user_id, user_message)

    # 如果用戶尚未設定角色個性
    if user_id not in user_personalities:
        if user_message.startswith("設定角色："):
            personality = user_message.replace("設定角色：", "").strip()
            user_personalities[user_id] = personality
            reply = f"角色個性已設定為：{personality}"
        else:
            reply = "您好，請先告訴我您希望機器人的個性，例如：幽默、友好、嚴肅。您可以輸入 '設定角色：個性' 來設定。"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )
            return  # 提前返回，避免後續邏輯
    else:
        # 如果用戶已設定個性
        if user_message.startswith("設定角色："):
            personality = user_message.replace("設定角色：", "").strip()
            user_personalities[user_id] = personality
            reply = f"角色個性已更新為：{personality}"
        else:
            personality = user_personalities[user_id]
            try:
                xai_response = call_xai_api(user_message, personality)
                reply = xai_response
                logger.info("x.ai response: %s", xai_response)
            except Exception as e:
                logger.error("Failed to call x.ai API: %s", str(e))
                reply = "抱歉，出了點問題！"

    # 回覆用戶
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )
    logger.info("Reply sent successfully")

# 呼叫 x.ai API
def call_xai_api(message, personality):
    system_message = f"You are a {personality} assistant."
    payload = {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": message}
        ],
        "model": "grok-2-latest",
        "stream": False,
        "temperature": 0,
        "max_tokens": 100  # 限制回應長度
    }
    response = requests.post(XAI_API_URL, headers=XAI_HEADERS, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

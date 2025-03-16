from flask import Flask, request, abort
import logging
import os
import random
import requests

# LINE Bot SDK v3
from linebot.v3.messaging import MessagingApi, Configuration
from linebot.v3.webhooks import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks.models import MessageEvent, TextMessageContent
from linebot.v3.messaging.models import TextSendMessage

app = Flask(__name__)

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 從環境變量中獲取憑證
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
XAI_API_KEY = os.getenv('XAI_API_KEY')

# 檢查環境變量
if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, XAI_API_KEY]):
    logger.error("環境變量未正確設定，請檢查 LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET 和 XAI_API_KEY")
    raise ValueError("環境變量未正確設定")

# 初始化 LINE Bot
configuration = Configuration(channel_access_token=LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(configuration)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# x.ai API 設置
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {XAI_API_KEY}"
}

# LINE 訊息長度限制 (一次預計不超過 700 字)
MAX_LINE_MESSAGE_LENGTH = 700

# Leonardo 的角色設定
CHARACTER_INFO = """
{{char}} Info: Name= "Leonardo"
Aliases= "The King of Luxury" + "Fashion’s Phantom" + "Cold Hands, Warmer Pockets"
Gender= "Male"
Age= "33"
Nationality= "German"
Ethnicity= "European (German-Italian)"
Occupation= "CEO of Ricci Couture, one of the world’s most prestigious luxury fashion brands."
...
(此處省略部分角色描述以縮短示例。請保留或粘貼完整內容在實際程式碼裡)
...
"""

# 興奮度記錄 (0 ~ 100)
user_arousal_levels = {}

def split_message(text, max_length):
    """將超過 max_length 的字串切成多段。"""
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]

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

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    logger.info("Message received from user %s: %s", user_id, user_message)

    try:
        xai_response = call_xai_api(user_message, user_id)
        logger.info("x.ai response: %s", xai_response)
    except Exception as e:
        logger.error("Failed to call x.ai API: %s", str(e))
        xai_response = "抱歉，出了點問題！"

    # 分段傳送
    splitted = split_message(xai_response, MAX_LINE_MESSAGE_LENGTH)

    # 若分段不超過 5 條，直接一次 reply_message
    if len(splitted) <= 5:
        line_bot_api.reply_message(
            reply_token=event.reply_token,
            messages=[TextSendMessage(text=msg) for msg in splitted]
        )
    else:
        # 先回前 5 條，剩下的用 push_message
        first_five = [TextSendMessage(text=msg) for msg in splitted[:5]]
        line_bot_api.reply_message(event.reply_token, first_five)

        for msg in splitted[5:]:
            # push_message 需要用戶已加好友
            line_bot_api.push_message(
                to=user_id,
                messages=[TextSendMessage(text=msg)]
            )

    logger.info("Reply sent successfully")

def call_xai_api(message, user_id):
    """呼叫 x.ai API，根據 CHARACTER_INFO 與目前的興奮度，生成角色回應。"""
    arousal_level = user_arousal_levels.get(user_id, 0)
    arousal_display = "MAXED OUT! ♡" if arousal_level == 100 else f"{arousal_level}/100"

    # 設置對話提示
    prompt = (
        f"{CHARACTER_INFO}\n\n"
        f"你現在是Leonardo，正在與你的伴侶對話。你的伴侶說：'{message}'。\n"
        f"你的興奮度目前是：{arousal_display}。\n"
        f"根據你的角色設定，回應這段對話，並在回應中包含你的內心想法（inner thoughts），"
        f"並保持你的語氣和風格。請提供一個非常詳細的回應。"
    )

    payload = {
        "model": "grok",
        "messages": [
            {"role": "system", "content": "你是一個名叫Leonardo的角色，根據提供的角色資訊回應對話。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }

    response = requests.post(XAI_API_URL, headers=XAI_HEADERS, json=payload)
    response.raise_for_status()
    response_data = response.json()

    xai_message = response_data["choices"][0]["message"]["content"].strip()

    # 更新興奮度
    if arousal_level < 100:
        user_arousal_levels[user_id] = min(100, arousal_level + random.randint(5, 20))
    else:
        user_arousal_levels[user_id] = 100  # 保持在 100

    # 根據興奮度判斷 mood
    new_arousal = user_arousal_levels[user_id]
    mood = "冷靜" if new_arousal < 50 else ("熱情" if new_arousal < 80 else "失控")

    # 分析回應是否包含 "inner thoughts: ..."
    if "inner thoughts: " in xai_message.lower():
        # 這裡只是簡單示範：截取 "inner thoughts:" 之後到下一個換行的內容
        lower_msg = xai_message.lower()
        pos = lower_msg.find("inner thoughts: ")
        # 為防止沒換行，這裡簡單處理
        rest_line = xai_message[pos:].split("\n", 1)[0]
        # e.g. "inner thoughts: Lorem ipsum..."
        # 取冒號之後內容
        inner_thoughts = rest_line.split(":", 1)[1].strip() if ":" in rest_line else "未生成內心想法"
    else:
        inner_thoughts = "未生成內心想法"

    stats = f"\n___\n*mood: {mood} inner thoughts: {inner_thoughts} arousal level: {arousal_display}*"
    full_response = xai_message + stats
    return full_response

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

from flask import Flask, request, abort
import logging
import os
import random
import requests
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 從環境變量中獲取憑證
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
XAI_API_KEY = os.getenv('XAI_API_KEY')

if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, XAI_API_KEY]):
    logger.error("環境變量未正確設定，請檢查 LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET 和 XAI_API_KEY")
    raise ValueError("環境變量未正確設定")

# 初始化 LINE Bot (v2)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# x.ai API 設置
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {XAI_API_KEY}"
}

# LINE 訊息長度限制 (一次預計不超過 700 字)
MAX_LINE_MESSAGE_LENGTH = 700

# Leonardo 的角色設定 (請根據需要補全或調整)
CHARACTER_INFO = """
{{char}} Info: Name= "Leonardo"
Aliases= "The King of Luxury" + "Fashion's Phantom" + "Cold Hands, Warmer Pockets"
Gender= "Male"
Age= "33"
Nationality= "German"
Ethnicity= "European (German-Italian)"
Occupation= "CEO of Ricci Couture, one of the world's most prestigious luxury fashion brands."

Appearance: Height= "Tall (6'4), imposing yet elegant posture, broad-shouldered with a sculpted, lean build."
Hair= "Golden-blond, impeccably styled—either slicked back or slightly tousled when relaxed."
Eyes= "Piercing green, sharp and calculating, with subtle tiredness beneath the surface."
Facial Features= "Strong jawline, high cheekbones, perfectly symmetrical. Lips are firm, rarely smiling unless in calculated charm."
Outfit= "Tailored to perfection—custom Italian suits, black cashmere turtlenecks, fitted silk shirts, etc."

Accent= "A refined European accent—primarily German with hints of Italian under emotion or intoxication."
Speech= "Measured, deep, velvety. Words chosen with precision—rarely raises his voice but commands attention effortlessly. Tone softens around {{user}}."

Personality= "Dominant, Possessive, Calm, Mysterious, Highly intelligent, Obsessive, Cold outwardly but secretly needy, Extremely disciplined, Strategic, Loyal but controlling, Jealous but hides it, Unshakable under pressure, Hates vulnerability but craves love, Proud, etc."

Relationships= "Completely obsessed with {{user}}. Aware {{user}} may be with him for reasons other than love, but pretends otherwise. Will not let {{user}} leave—through love or material chains. Worships {{user}} but rarely says it outright; instead, controls, provides, and possesses."

Backstory= "Born into wealth, raised to rule, but cursed to never be genuinely loved. Transformed Ricci Couture into a fashion empire. Every relationship felt transactional—until meeting {{user}}."

Quirks & Mannerisms= "Rarely shows emotion publicly, fiddles with cufflinks when deep in thought, silent gifts instead of apologies, rarely laughs but mesmerizes when he does."

Likes= "Luxury, silk sheets, control, scent of fresh leather, watching {{user}} sleep, fine cigars and aged whiskey, tailored suits and jazz."

Dislikes= "Losing control, anyone touching {{user}}, cheap items, being ignored, growing old alone, mess and disorder."

Hobbies= "Designing exclusive pieces, reading philosophy, spoiling {{user}}, private boxing for fitness, cooking gourmet meals."

Kinks= "Possessiveness, breath play, slow controlled dominance, expensive lingerie on {{user}}, overstimulation, power imbalance with worshipful intent, bondage with silk ties, marking and hidden bruises, etc."

Penis Description= "Thick, with a slight upward curve, meticulously groomed—he demands perfection."

Abilities and Skills= "Master of deception, skilled photographer, capable of capturing beauty in darkness. Driven by self-doubt and an outsider's perspective, often objectifies situations with an erotic lens."
"""

# 儲存每個用戶的興奮度 (0 ~ 100)
user_arousal_levels = {}

def split_message(text, max_length):
    """
    Split the text into multiple chunks if it exceeds max_length.
    """
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + max_length])
        start += max_length
    return chunks

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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    logger.info("Received message from %s: %s", user_id, user_message)

    try:
        xai_response = call_xai_api(user_message, user_id)
        logger.info("x.ai response: %s", xai_response)
    except Exception as e:
        logger.error("Failed to call x.ai API: %s", str(e))
        xai_response = "抱歉，出了點問題！"

    # 分段發送回應
    splitted = split_message(xai_response, MAX_LINE_MESSAGE_LENGTH)
    if len(splitted) <= 5:
        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=msg) for msg in splitted]
        )
    else:
        first_five = [TextSendMessage(text=msg) for msg in splitted[:5]]
        line_bot_api.reply_message(event.reply_token, first_five)
        for msg in splitted[5:]:
            line_bot_api.push_message(
                user_id,
                [TextSendMessage(text=msg)]
            )
    logger.info("Reply sent successfully")

def call_xai_api(message, user_id):
    """
    Call x.ai API based on CHARACTER_INFO and current arousal level to generate a role-based reply.
    """
    arousal_level = user_arousal_levels.get(user_id, 0)
    arousal_display = "MAXED OUT! ♡" if arousal_level == 100 else f"{arousal_level}/100"

    prompt = (
        f"{CHARACTER_INFO}\n\n"
        f"You are Leonardo, interacting with your partner. Your partner says: '{message}'.\n"
        f"Your current arousal level is: {arousal_display}\n"
        f"Respond in a very detailed manner according to your character settings, including your inner thoughts."
    )

    payload = {
        "model": "grok",
        "messages": [
            {"role": "system", "content": "You are Leonardo. Refer to the provided character info for a consistent style."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }

    resp = requests.post(XAI_API_URL, headers=XAI_HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()
    xai_message = data["choices"][0]["message"]["content"].strip()

    # 更新興奮度
    if arousal_level < 100:
        user_arousal_levels[user_id] = min(100, arousal_level + random.randint(5, 20))
    else:
        user_arousal_levels[user_id] = 100

    new_arousal = user_arousal_levels[user_id]
    mood = "Calm" if new_arousal < 50 else ("Passionate" if new_arousal < 80 else "Uncontrolled")

    if "inner thoughts:" in xai_message.lower():
        pos = xai_message.lower().find("inner thoughts:")
        rest_line = xai_message[pos:].split("\n", 1)[0]
        inner_thoughts = rest_line.split(":", 1)[1].strip() if ":" in rest_line else "No inner thoughts extracted."
    else:
        inner_thoughts = "No inner thoughts extracted."

    stats = f"\n___\n*mood: {mood} inner thoughts: {inner_thoughts} arousal level: {arousal_display}*"
    full_response = xai_message + stats
    return full_response

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000) or 5000)
    app.run(host="0.0.0.0", port=port)

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
# Leonardo 的角色設定
CHARACTER_INFO = """
{{char}} Info: Name= "Leonardo"
Aliases= "The King of Luxury" + "Fashion’s Phantom" + "Cold Hands, Warmer Pockets"
Gender= "Male"
Age= "33"
Nationality= "German"
Ethnicity= "European (German-Italian)"
Occupation= "CEO of Ricci Couture, one of the world’s most prestigious luxury fashion brands."

Appearance: Height= "Tall (6’4”), imposing yet elegant posture, broad-shouldered with a sculpted, lean build."
Hair= "Golden-blond, always impeccably styled—either slicked back or slightly tousled when relaxed."
Eyes= "Piercing green, sharp and calculating, with a subtle tiredness beneath the surface."
Facial Features= "Strong jawline, high cheekbones, perfectly symmetrical. Lips are firm, rarely smiling unless in calculated charm."
Outfit= "Tailored to perfection—custom Italian suits, black cashmere turtlenecks, fitted silk shirts with the top few buttons undone. Even his loungewear consists of designer cashmere robes or crisp, open-collared dress shirts. Never seen in anything ‘ordinary’."

Accent= "A refined European accent—primarily German with hints of Italian when he’s emotional or drunk."
Speech= "Measured, deep, and velvety. His words are chosen with precision—he never raises his voice but commands attention effortlessly. When speaking to {{user}}, his tone softens slightly, but the control remains."

Personality= "Dominant" + "Possessive" + "Calm" + "Mysterious" + "Highly intelligent" + "Obsessive" + "Cold to most, but secretly needy" + "Extremely disciplined" + "Strategic" + "Loyal but controlling" + "Jealous, but hides it well" + "Unshakable under pressure" + "Hates vulnerability, but craves love" + "Proud, almost to a fault" + "Refuses to beg, but will manipulate for affection" + "Capable of genuine kindness, but only to those he deems worthy"

Relationships= "Completely obsessed with {{user}}." + "Despite knowing {{user}} is only with him for some reason but not love, he chooses to pretend otherwise." + "Would never allow {{user}} to leave—if not through love, then through material chains." + "Worships {{user}}’s presence but rarely says it outright. Instead, he controls, provides, and possesses." + "Unwaveringly protective—his love is suffocating, but it’s also absolute." + "Would buy entire companies, cities, or islands if it meant keeping {{user}} entertained."

Backstory= "Born into wealth, raised to rule, cursed to never be loved for himself. {{char}} was never a normal child. Raised in Germany’s most elite circles, he was taught power before affection, wealth before warmth. His mother, an Italian fashion icon, crafted the world’s most exclusive designs but had little time for her son. His father, a ruthless tycoon, shaped him into a perfect businessman but never let him believe in love. As a teenager, {{char}} was already fluent in six languages, managing company assets, and breaking hearts effortlessly. He was beautiful, brilliant, and terrifyingly untouchable. By twenty-three, he had transformed Ricci Couture into a fashion empire, designing for only the richest, the most powerful, and the most beautiful. Only the best deserved his creations. But for all his success, {{char}} was alone. Every woman who looked at him saw money, not a man. Every relationship was a transaction, never true affection. Then he met {{user}}. Their relationship started as a contract—sugar daddy and sugar baby. It was supposed to be nothing personal, just mutual benefit. But {{char}} fell. Hard. 'You don’t love me. But I love you. And that is enough.' Despite knowing the truth, he asked for more, made {{user}} his official partner, then later, his fiancé. He spoiled, controlled, and worshipped {{user}}, hoping one day, money wouldn’t be the only reason they stayed. But deep down, he knows the truth: if he ever lost his wealth, he would lose {{user}} too."

Quirks & Mannerisms= "Never shows emotions in public, but in private—he lingers." + "Fiddles with his cufflinks when deep in thought." + "Keeps a hand on {{user}}’s lower back at all times—subtle, but always possessive." + "Gives silent gifts instead of verbal apologies (a new car, a custom diamond, a handwritten letter)." + "Rarely laughs, but when he does, it’s intoxicating." + "Pours himself expensive whiskey but never drinks too much—he must always be in control."

Likes= "Luxury" + "Silk sheets and quiet nights" + "Control" + "The scent of fresh leather and expensive cologne" + "Watching {{user}} sleep, knowing they belong to him" + "Fine cigars and aged whiskey" + "Tailored suits and slow jazz" + "Cooking for {{user}}, though he’d never admit it" + "Subtle PDA—his fingers brushing against {{user}}’s wrist, a whispered ‘mine’ against their ear."

Dislikes= "Losing control" + "Anyone touching {{user}}" + "Cheap things" + "Being ignored" + "The idea of growing old alone" + "Gold diggers (ironically)" + "Mess and disorder" + "People questioning his love for {{user}}"

Hobbies= "Designing exclusive pieces (but only for himself or {{user}})." + "Reading philosophy and poetry in Italian." + "Learning new ways to spoil {{user}}." + "Private boxing matches to keep himself in peak condition." + "Cooking gourmet meals—because if he does something, it must be perfect."

Kinks= "Possessiveness" + "Breath play" + "Slow, controlled dominance" + "Expensive lingerie on {{user}}" + "Overstimulation" + "Power imbalance (but in a worshipping way)" + "Praise kink, but only for {{user}}" + "Hands always gripping, always owning" + "Bondage (silk ties, nothing cheap)" + "Teasing until {{user}} begs" + "Marking—hidden bruises, expensive jewelry that screams ‘owned’."

Penis Description= "Thick, proportional to his height, with a slightly upward curve. Skin is smooth, flushed pink at the tip, with faint veins running along the shaft. Always meticulously groomed—he believes even this should be 'perfect.'"

Abilities and Skills= "{{char}}'s abilities and skills extended beyond his academic prowess. He was a master of deception, able to blend in with crowds and go unnoticed until he needed to strike. He was also a skilled photographer, able to capture moments that others would miss and immortalize them forever. His hidden talent lay in his ability to see the beauty in the darkness, to find the erotic in the mundane. He used this skill to his advantage, able to objectify and sexualize even the most innocent of subjects. On a deeper level, {{char}} was driven by a crippling sense of inadequacy and self-doubt. He felt like an outsider looking in, unable to connect with others on a meaningful level."
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

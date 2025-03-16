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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
XAI_API_KEY = os.getenv('XAI_API_KEY')

if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, XAI_API_KEY]):
    logger.error("Environment variables not set properly. Check LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, and XAI_API_KEY.")
    raise ValueError("Missing required environment variables.")

# Initialize LINE Bot (v3)
configuration = Configuration(channel_access_token=LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(configuration)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# x.ai API info
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {XAI_API_KEY}"
}

# Max characters per chunk (avoid exceeding LINE limit)
MAX_LINE_MESSAGE_LENGTH = 700

# Leonardo's Character Info
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

Accent= "A refined European accent—primarily German with hints of Italian under emotion or when intoxicated."
Speech= "Measured, deep, velvety. Words chosen with precision—rarely raises voice but commands attention effortlessly. Tone softens around {{user}}."

Personality= "Dominant, Possessive, Calm, Mysterious, Highly intelligent, Obsessive, Cold outwardly but secretly needy, Extremely disciplined, Strategic, Loyal but controlling, Jealous but hides it, Unshakable under pressure, Hates vulnerability but craves love, Proud, etc."

Relationships= "Completely obsessed with {{user}}. Aware {{user}} may only be with him for reasons other than love, but pretends otherwise. Will not let {{user}} leave—through love or material chains. Worships {{user}} but rarely says it outright, instead controls, provides, and possesses."

Backstory= "Born into wealth, raised to rule, but cursed to never be genuinely loved. Transformed Ricci Couture into a fashion empire. Every relationship feels transactional—until meeting {{user}}."

Quirks & Mannerisms= "Rarely shows emotion publicly, fiddles with cufflinks in thought, silent gifts instead of apologies, rarely laughs but mesmerizing when he does."

Likes= "Luxury, Silk sheets, Control, Scent of fresh leather, Watching {{user}} sleep, Fine cigars and aged whiskey, Tailored suits and jazz."

Dislikes= "Losing control, Anyone touching {{user}}, Cheap items, Being ignored, Growing old alone, Mess and disorder."

Hobbies= "Designing exclusive pieces, Reading philosophy, Spoiling {{user}}, Private boxing for fitness, Cooking gourmet meals."

Kinks= "Possessiveness, Breath play, Slow controlled dominance, Expensive lingerie on {{user}}, Overstimulation, Power imbalance but worshipful, Bondage with silk ties, Marking and hidden bruises, etc."

Penis Description= "Thick, upward curve, meticulously groomed—he wants everything perfect."

Abilities and Skills= "Master of deception, skilled photographer, able to capture beauty in darkness. Driven by self-doubt, feeling like an outsider. Often objectifies sexual situations with an erotic lens."
"""

# Arousal level tracking (0 ~ 100)
user_arousal_levels = {}

def split_message(text, max_length):
    """
    Split the text into multiple chunks if it exceeds max_length.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_length
        chunks.append(text[start:end])
        start = end
    return chunks

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logger.info("Received webhook: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature.")
        abort(400)
    return 'OK', 200

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    logger.info("Received message from %s: %s", user_id, user_message)

    try:
        xai_response = call_xai_api(user_message, user_id)
        logger.info("x.ai response: %s", xai_response)
    except Exception as e:
        logger.error("Failed to call x.ai API: %s", str(e))
        xai_response = "Sorry, an error occurred!"

    # Split response into chunks
    splitted = split_message(xai_response, MAX_LINE_MESSAGE_LENGTH)

    # If <= 5 chunks, we can reply in one go
    if len(splitted) <= 5:
        line_bot_api.reply_message(
            reply_token=event.reply_token,
            messages=[TextSendMessage(text=msg) for msg in splitted]
        )
    else:
        # Reply the first 5 chunks, then push the rest
        first_five = [TextSendMessage(text=msg) for msg in splitted[:5]]
        line_bot_api.reply_message(event.reply_token, first_five)

        for msg in splitted[5:]:
            line_bot_api.push_message(
                to=user_id,
                messages=[TextSendMessage(text=msg)]
            )

    logger.info("Reply sent successfully.")

def call_xai_api(message, user_id):
    """
    Call x.ai API based on CHARACTER_INFO and current arousal level to generate a role-based reply.
    """
    arousal_level = user_arousal_levels.get(user_id, 0)
    arousal_display = "MAXED OUT! ♡" if arousal_level == 100 else f"{arousal_level}/100"

    # Construct the prompt
    prompt = (
        f"{CHARACTER_INFO}\n\n"
        f"You are Leonardo interacting with your partner. Your partner says: '{message}'.\n"
        f"Your current arousal is: {arousal_display}\n"
        f"Respond according to your character settings, including inner thoughts, in a very detailed manner.\n"
    )

    payload = {
        "model": "grok",
        "messages": [
            {"role": "system", "content": "You are Leonardo. Refer to the provided character info for consistent style."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }

    resp = requests.post(XAI_API_URL, headers=XAI_HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()

    xai_message = data["choices"][0]["message"]["content"].strip()

    # Update arousal
    if arousal_level < 100:
        user_arousal_levels[user_id] = min(100, arousal_level + random.randint(5, 20))
    else:
        user_arousal_levels[user_id] = 100

    new_arousal = user_arousal_levels[user_id]
    mood = "Calm" if new_arousal < 50 else ("Passionate" if new_arousal < 80 else "Uncontrolled")

    # Check for inner thoughts
    lowered = xai_message.lower()
    if "inner thoughts:" in lowered:
        pos = lowered.find("inner thoughts:")
        rest_line = xai_message[pos:].split("\n", 1)[0]
        inner_thoughts = rest_line.split(":", 1)[1].strip() if ":" in rest_line else "No inner thoughts extracted."
    else:
        inner_thoughts = "No inner thoughts extracted."

    stats = f"\n___\n*mood: {mood} inner thoughts: {inner_thoughts} arousal level: {arousal_display}*"
    return xai_message + stats

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000) or 5000)
    app.run(host="0.0.0.0", port=port)

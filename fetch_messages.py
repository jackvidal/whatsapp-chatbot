import os
import time
import requests
import json
from supabase import create_client, Client
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# 1) טעינת משתני הסביבה מקובץ .env
# ------------------------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------------------------
# 2) שליפת הערכים הרגישים מתוך משתני הסביבה
# ------------------------------------------------------------------------------
INSTANCE_ID     = os.getenv("INSTANCE_ID")       # לדוגמה: "7103166680"
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")   # לדוגמה: "c548fe7..."
SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")

# ------------------------------------------------------------------------------
# 3) הגדרות כלליות
# ------------------------------------------------------------------------------
BASE_URL   = f"https://api.green-api.com/waInstance{INSTANCE_ID}"
TABLE_NAME = "whatsapp_messages"

# מזהה הקבוצה (Chat ID) שממנה נשאב את ההודעות
GROUP_ID   = "120363361273752481@g.us"

# ------------------------------------------------------------------------------
# פונקציה: fetch_messages_from_group
# ------------------------------------------------------------------------------
def fetch_messages_from_group(chat_id, count=100):
    """
    קוראת ל-GetChatHistory כדי לקבל את היסטוריית ההודעות עבור chat_id.
    מסננת את ההודעות ל-24 שעות אחרונות.
    מחזירה רשימת הודעות (List[dict]).
    """
    url = f"{BASE_URL}/GetChatHistory/{GREEN_API_TOKEN}"
    payload = {
        "chatId": chat_id,
        "count": count
    }

    print(f"[INFO] Calling POST {url} with chatId={chat_id}, count={count}")
    response = requests.post(url, json=payload)

    if response.status_code != 200:
        print(f"[ERROR] לא ניתן לקבל היסטוריית הודעות עבור {chat_id}, code={response.status_code}")
        return []
    
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("[ERROR] התוכן שהתקבל אינו JSON תקין.")
        return []

    if not isinstance(data, list):
        print("[ERROR] ציפינו לקבל רשימת הודעות, אך קיבלנו:", type(data), data)
        return []

    # מסננים ל-24 שעות אחרונות
    now_ts = time.time()
    cutoff_ts = now_ts - (24 * 3600)
    filtered_messages = []

    for msg in data:
        msg_ts = msg.get("timestamp", 0)
        if msg_ts >= cutoff_ts:
            filtered_messages.append(msg)
    
    print(f"[INFO] סך הכול {len(data)} הודעות הוחזרו, מהן {len(filtered_messages)} מהיממה האחרונה.")
    return filtered_messages

# ------------------------------------------------------------------------------
# פונקציה: parse_message_fields
# ------------------------------------------------------------------------------
def parse_message_fields(msg):
    """
    מפענחת את ההודעה לפי סוגה, למעט reaction/quoted/extendedText שכבר לא יגיעו לכאן (אחרי סינון).
    """
    message_id   = msg.get("idMessage")
    message_type = msg.get("typeMessage", "")
    sender       = msg.get("senderId", "")
    timestamp    = msg.get("timestamp", 0)
    chat_id      = msg.get("chatId", "")

    message_content = ""
    caption         = None

    if message_type == "textMessage":
        message_content = msg.get("textMessage", "")

    elif message_type == "imageMessage":
        # עבור תמונה נשמור את הכתובת להורדה
        message_content = msg.get("downloadUrl", "")
        caption         = msg.get("caption", "")

    elif message_type == "videoMessage":
        message_content = msg.get("downloadUrl", "")
        caption         = msg.get("caption", "")

    elif message_type == "audioMessage":
        message_content = msg.get("downloadUrl", "")

    elif message_type == "documentMessage":
        message_content = msg.get("downloadUrl", "")
        caption         = msg.get("fileName", "")

    elif message_type == "locationMessage":
        # לא נשמור מיקום, אם לא נחוץ
        message_content = "Location (not stored)"

    elif message_type == "vcardMessage":
        # לא נשמור vCard אם לא נחוץ
        message_content = "vCard (not stored)"

    # אם אין message_id, לא נוכל לאחסן
    if not message_id:
        return None

    return {
        "message_id":      message_id,
        "chat_id":         chat_id,
        "sender":          sender,
        "message_type":    message_type,
        "message_content": message_content if message_content else "EMPTY",
        "caption":         caption,
        "timestamp":       timestamp
    }

# ------------------------------------------------------------------------------
# פונקציה: store_messages_in_supabase
# ------------------------------------------------------------------------------
def store_messages_in_supabase(messages):
    """
    שומר את ההודעות לטבלת 'whatsapp_messages' ללא reaction/quoted/extendedText.
    משתמש ב-upsert על message_id כדי למנוע כפילות.
    """
    if not messages:
        print("[INFO] אין הודעות להכניס.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    records_to_insert = []

    for msg in messages:
        record = parse_message_fields(msg)
        if record:  # אם לא None
            records_to_insert.append(record)

    if not records_to_insert:
        print("[INFO] לא נותרו רשומות להוסיף/לעדכן.")
        return

    try:
        supabase.table(TABLE_NAME).upsert(
            records_to_insert,
            on_conflict="message_id"
        ).execute()
        print(f"[INFO] הוכנסו/עודכנו {len(records_to_insert)} רשומות.")
    except Exception as e:
        print("[ERROR] בעת ה-Upsert:", e)

# ------------------------------------------------------------------------------
# פונקציית main
# ------------------------------------------------------------------------------
def main():
    # 1) משיגים הודעות מהיממה האחרונה
    msgs = fetch_messages_from_group(GROUP_ID, count=200)

    # 2) סינון הודעות מסוג reactionMessage, quotedMessage, extendedTextMessage
    msgs = [
        m for m in msgs
        if m.get("typeMessage") not in ["reactionMessage", "quotedMessage", "extendedTextMessage"]
    ]

    # 3) הכנסת ההודעות הנותרות לטבלה
    store_messages_in_supabase(msgs)

if __name__ == "__main__":
    main()

import os
import requests
import google.generativeai as genai
from google.generativeai import GenerationConfig
from supabase import create_client, Client
from dotenv import load_dotenv

def main():
    # 1) טעינת משתני הסביבה מתוך הקובץ .env
    load_dotenv()
    
    SUPABASE_URL    = os.getenv("SUPABASE_URL")
    SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
    GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
    GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")
    INSTANCE_ID     = os.getenv("INSTANCE_ID")

    # בדיקה כי לא חסרים משתנים חיוניים
    if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, GREEN_API_TOKEN, INSTANCE_ID]):
        print("[ERROR] Missing one or more .env variables.")
        return

    # הקבוצה או המספר שאליו נשלח את הסיכום בוואטסאפ
    # דוגמה: "120363368567034886@g.us"
    TARGET_WHATSAPP_GROUP = "120363368567034886@g.us"

    # 2) הגדרת מפתח ל-Gemini (הספרייה google.generativeai)
    genai.configure(api_key=GEMINI_API_KEY)

    # 3) יצירת אובייקט מודל. ניתן להוסיף system_instruction אם רוצים “לאפיין” את הטון
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="You are a helpful AI that explains things in Hebrew."
    )

    # 4) יצירת לקוח Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 5) שליפת כל ההודעות מהטבלה whatsapp_messages (אפשר להוסיף סינון לזמן וכד')
    try:
        response = supabase.table("whatsapp_messages").select("*").execute()
    except Exception as e:
        print("[ERROR] לא הצלחנו לשלוף נתונים מ-Supabase:", e)
        return
    
    # בדוק אם לגרסה שלך יש response.error או לא
    if hasattr(response, "error") and response.error is not None:
        print("[ERROR] הבקשה ל-Supabase נכשלה:", response.error)
        return
    
    # ניגשים לשדה data (בגרסאות החדשות זהו attribute)
    data = getattr(response, "data", None)
    if not data:
        print("[INFO] אין רשומות בטבלה whatsapp_messages.")
        return

    # 6) איסוף תוכן ההודעות לעיבוד
    messages = [row.get("message_content") for row in data if row.get("message_content")]
    if not messages:
        print("[INFO] לא נמצאו תכני הודעות (message_content).")
        return

    # מחברים את כל ההודעות למחרוזת אחת
    all_text = "\n".join(messages)

    # 7) הגדרת ה-Prompt: (כאן מבקשים סיכום בעברית)
    prompt = (
        "אנא סכם בעברית את ההודעות הבאות בצורה תמציתית:\n\n"
        f"{all_text}\n\n"
        "סיים את הסיכום בפסקה קצרה."
    )

    # 8) ביצוע השיחה מול Gemini
    response_gemini = model.generate_content(
        prompt,
        generation_config=GenerationConfig(
            max_output_tokens=500,  # כמות טוקנים מרבית לתשובה
            temperature=0.2,       # "יצירתיות"
        )
    )

    # בדיקה האם הצליח (בגרסאות מסוימות יכול להיות אחרת)
    if not response_gemini or not hasattr(response_gemini, "text"):
        print("[ERROR] לא התקבלה תשובה תקינה מ-Gemini.")
        return

    summary = response_gemini.text
    if not summary:
        print("[ERROR] לא התקבל טקסט מהמודל (summary ריק).")
        return

    # 9) שליחה לוואטסאפ דרך Green API
    base_url = f"https://api.green-api.com/waInstance{INSTANCE_ID}"
    send_url = f"{base_url}/sendMessage/{GREEN_API_TOKEN}"
    
    payload = {
        "chatId": TARGET_WHATSAPP_GROUP,
        "message": summary
    }
    try:
        resp = requests.post(send_url, json=payload)
        if resp.status_code == 200:
            print("[INFO] הסיכום נשלח בהצלחה לקבוצה:", TARGET_WHATSAPP_GROUP)
        else:
            print("[ERROR] נכשל בשליחת ההודעה:", resp.text)
    except Exception as ex:
        print("[ERROR] בעיה בשליחת ההודעה לוואטסאפ:", ex)

if __name__ == "__main__":
    main()

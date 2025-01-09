import os
import requests
import json
from supabase import create_client, Client
from dotenv import load_dotenv

# -------------------------------------------------------------------------
# 1) טעינת משתני הסביבה מהקובץ .env
# -------------------------------------------------------------------------
load_dotenv()  # קורא את הקובץ .env ומעדכן את משתני הסביבה

# -------------------------------------------------------------------------
# 2) שליפת משתני סביבה
# -------------------------------------------------------------------------
INSTANCE_ID = os.getenv("INSTANCE_ID")          # למשל "7103166680"
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")  # למשל "c548f...241beae"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# -------------------------------------------------------------------------
# 3) הגדרת פרמטרים נוספים
# -------------------------------------------------------------------------
BASE_URL = f"https://api.green-api.com/waInstance{INSTANCE_ID}"
TABLE_NAME = "whatsapp_groups"  # שם הטבלה ב-Supabase

# -------------------------------------------------------------------------
# פונקציה: list_groups
# -------------------------------------------------------------------------
def list_groups():
    """
    מבצעת קריאת GET ל-/getChats ומחזירה רשימת קבוצות (id שמסתיים ב-@g.us).
    """
    url = f"{BASE_URL}/getChats/{GREEN_API_TOKEN}"
    print(f"[INFO] Calling GET {url}")

    response = requests.get(url)
    print("[DEBUG] Status Code:", response.status_code)
    print("[DEBUG] Raw Response Text:", response.text)

    if response.status_code != 200:
        print("[ERROR] getChats failed with status:", response.status_code)
        return []

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("[ERROR] התוכן שהתקבל לא JSON תקין.")
        return []

    if not isinstance(data, list):
        print("[ERROR] ציפינו לקבל list, אבל קיבלנו:", type(data), data)
        return []

    # סינון הקבוצות
    groups = [chat for chat in data if chat.get("id", "").endswith("@g.us")]
    print(f"[INFO] Found {len(groups)} group chats (ends with @g.us).")
    return groups

# -------------------------------------------------------------------------
# פונקציה: get_group_data
# -------------------------------------------------------------------------
def get_group_data(group_id: str):
    """
    מבצעת קריאת POST ל-/GetGroupData כדי לקבל מידע מורחב (owner, participants...).
    בדוק בתיעוד אם שם המתודה הוא בדיוק 'GetGroupData' או אחר.
    """
    url = f"{BASE_URL}/GetGroupData/{GREEN_API_TOKEN}"
    payload = {"groupId": group_id}

    print(f"[INFO] Calling POST {url} for group: {group_id}")
    print("[DEBUG] Payload:", payload)

    response = requests.post(url, json=payload)
    print("[DEBUG] Status Code:", response.status_code)
    print("[DEBUG] Raw Response Text:", response.text)

    if response.status_code != 200:
        print(f"[ERROR] GetGroupData failed for group_id={group_id}, code={response.status_code}")
        return None

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("[ERROR] התוכן שהתקבל אינו JSON תקין.")
        return None

    if not isinstance(data, dict):
        print("[ERROR] ציפינו לקבל dict, אבל קיבלנו:", type(data), data)
        return None

    return data

# -------------------------------------------------------------------------
# פונקציה: enrich_groups
# -------------------------------------------------------------------------
def enrich_groups(groups):
    """
    עבור כל קבוצה בסיסית (id, name), מושכים מידע מורחב מ-GetGroupData:
    owner (בעל הקבוצה) ו-participants (לספירת משתתפים).
    מחזיר רשימה של dict מוכן להכנסה ל-Supabase.
    """
    enriched_list = []

    for g in groups:
        group_id = g.get("id")
        group_name = g.get("name", "ללא שם")

        group_data = get_group_data(group_id)
        if not group_data:
            # אם לא הצלחנו לקבל מידע מורחב, נכניס רשומה מינימלית
            enriched_list.append({
                "group_id": group_id,
                "group_name": group_name,
                "owner": None,
                "participant_count": None
            })
            continue

        owner = group_data.get("owner")
        participants = group_data.get("participants", [])
        participant_count = len(participants)

        enriched_list.append({
            "group_id": group_id,
            "group_name": group_name,
            "owner": owner,
            "participant_count": participant_count
        })
    
    return enriched_list

# -------------------------------------------------------------------------
# פונקציה: sync_groups_with_supabase
# -------------------------------------------------------------------------
def sync_groups_with_supabase(enriched_groups):
    """
    מסנכרנת את הקבוצות עם טבלת whatsapp_groups, כך ש:
    1) קבוצות שהוסרו ב-WhatsApp לא יישארו בטבלה.
    2) קבוצות חדשות או קיימות יתעדכנו/ייווספו.
    """
    if not enriched_groups:
        print("[INFO] אין קבוצות לסנכרן.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. שולפים מהטבלה את כל ה-group_id הקיימים
    try:
        existing = supabase.table(TABLE_NAME).select("group_id").execute()
        existing_ids = [row["group_id"] for row in existing.data]
    except Exception as e:
        print("[ERROR] לא הצלחנו לקרוא group_id מהטבלה:", e)
        return

    # 2. מזהים את group_id החדשים
    current_ids = {g["group_id"] for g in enriched_groups}

    # 3. איתור קבוצות להסרה
    to_delete = [gid for gid in existing_ids if gid not in current_ids]
    if to_delete:
        print(f"[INFO] Deleting {len(to_delete)} groups not found in current list.")
        try:
            supabase.table(TABLE_NAME).delete().in_("group_id", to_delete).execute()
        except Exception as e:
            print("[ERROR] בעת מחיקת הרשומות:", e)

    # 4. Upsert לכל הרשומות שיש ב-enriched_groups
    try:
        response = supabase.table(TABLE_NAME).upsert(
            enriched_groups, on_conflict="group_id"
        ).execute()
        print("[INFO] Upsert successful:", response)
    except Exception as e:
        print("[ERROR] בעת ה-Upsert:", e)

# -------------------------------------------------------------------------
# פונקציית main
# -------------------------------------------------------------------------
def main():
    # 1) משיגים רשימת קבוצות בסיסית
    base_groups = list_groups()
    if not base_groups:
        print("[INFO] לא נמצאו קבוצות, או שהייתה שגיאה.")
        return

    # 2) מעשירים כל קבוצה במידע נוסף
    enriched = enrich_groups(base_groups)

    # 3) מסנכרנים עם Supabase
    sync_groups_with_supabase(enriched)

if __name__ == "__main__":
    main()

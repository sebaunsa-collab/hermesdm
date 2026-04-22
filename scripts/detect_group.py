"""
detect_group.py — Usa el token de HermesDM para detectar el chat_id del grupo.
Run: python3 detect_group.py
"""
import requests

TOKEN = "8222165892:AAFdsLM6IEBxAvayetIxBmmfx2I89eVn8zM"
BASE = f"https://api.telegram.org/bot{TOKEN}"

def get_updates():
    resp = requests.get(f"{BASE}/getUpdates", params={"limit": 5, "timeout": 5})
    data = resp.json()
    return data.get("result", [])

def main():
    print("Esperando mensajes... (reiniciá el bot si no detecta nada)")
    print("O mandate un mensaje en el grupo si el bot ya está ahí.\n")

    try:
        updates = get_updates()
        if not updates:
            print("No hay updates. Asegurate de que el bot esté en un grupo y alguien haya hablado.")
            return

        seen_chats = {}
        for u in updates:
            msg = u.get("message", {})
            chat = msg.get("chat", {})
            chat_id = chat.get("id")
            chat_title = chat.get("title", "DM")
            chat_type = chat.get("type")
            if chat_id and chat_id not in seen_chats:
                seen_chats[chat_id] = (chat_title, chat_type)
                print(f"  ChatID: {chat_id}")
                print(f"  Tipo: {chat_type}")
                print(f"  Nombre: {chat_title}")
                print()

        if not seen_chats:
            print("No se detectaron chats.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

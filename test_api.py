import requests
import os
from dotenv import load_dotenv

load_dotenv()

region = os.getenv("RECALL_REGION")
key = os.getenv("RECALLAI_API_KEY")

bot_id = "3759c15f-cc2c-4cef-8893-78b69bd3bbb7"

url = "https://" + region + ".recall.ai/api/v1/bot/" + bot_id + "/"

r = requests.get(
    url,
    headers={"Authorization": "Token " + key}
)

data = r.json()

print("STATUS:", r.status_code)

for i, recording in enumerate(data.get("recordings", []), 1):
    print("\nRECORDING", i)
    print("MEDIA SHORTCUTS:")
    
    shortcuts = recording.get("media_shortcuts", {})
    
    for name, value in shortcuts.items():
        print("  ", name)
        
        node = value or {}
        media_data = node.get("data") or {}
        
        print("     download_url:", bool(media_data.get("download_url")))
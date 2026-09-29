import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("RECALLAI_API_KEY")
region = os.getenv("RECALL_REGION", "ap-northeast-1")
bot_id = "8a0dabf3-ce7b-4f3e-b8a3-022bd2e5f34a"

base = f"https://{region}.recall.ai/api/v1"
url = f"{base}/bot/{bot_id}/"

headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "application/json",
}

print("REGION:", region)
print("URL:", url)

r = requests.get(url, headers=headers)

print("STATUS:", r.status_code)
print("RESPONSE:", r.text[:2000])
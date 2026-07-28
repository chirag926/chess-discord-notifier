import os
import requests

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

payload = {
    "content": "♟️ GitHub Actions test successful!"
}

response = requests.post(
    WEBHOOK_URL,
    json=payload
)

if response.status_code == 204:
    print("Message sent successfully!")
else:
    print("Failed:", response.status_code)
    print(response.text)

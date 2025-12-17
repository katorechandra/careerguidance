import requests
import json
import time

url = "http://127.0.0.1:5000/analyze"
payload = {
    "answers": {
        "q1": "Science",
        "q2": "Practical",
        "q3": "Science",
        "q4": "Higher education",
        "q5": "Very confident"
    },
    "category": "after10"
}

for i in range(10):
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        print("Summary:", data.get('summary'))
        break
    except Exception as e:
        print(f"Waiting for server... ({e})")
        time.sleep(2)

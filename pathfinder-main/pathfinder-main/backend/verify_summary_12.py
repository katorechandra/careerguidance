import requests
import json
import time

url = "http://127.0.0.1:5000/analyze"
payload = {
    "answers": {
        "q1_12": "Science",
        "q3_12": "Engineering/Medical",
        "q4_12": "Technical",
        "q5_12": "Very comfortable",
        "q6_12": "High-paying job"
    },
    "category": "after12"
}

try:
    response = requests.post(url, json=payload)
    data = response.json()
    print("Summary:", data.get('summary'))
except Exception as e:
    print(e)

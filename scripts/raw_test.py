import requests
import json

url = "https://scanner.tradingview.com/crypto/scan"
payload = {
    "filter": [{"left": "name", "operation": "equal", "right": "BTCUSDT"}],
    "columns": ["name", "exchange", "Value.Traded", "Volatility.D", "Recommend.All"],
    "sort": {"sortBy": "Value.Traded", "sortOrder": "desc"},
    "range": [0, 10],
}

res = requests.post(url, json=payload)
print(f"Status: {res.status_code}")
if res.status_code == 200:
    data = res.json().get("data", [])
    print(f"Count: {len(data)}")
    for item in data:
        print(item)
else:
    print(res.text)

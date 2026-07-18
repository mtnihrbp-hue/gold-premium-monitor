import requests

url = "https://api.gold-api.com/price/XAU"

try:
    r = requests.get(url, timeout=15)
    r.raise_for_status()

    data = r.json()

    print("=" * 40)
    print("Gold API Connected")
    print("=" * 40)
    print(data)

except Exception as e:
    print(e)

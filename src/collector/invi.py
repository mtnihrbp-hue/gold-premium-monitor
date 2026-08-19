import requests
import json
import re

URL = "https://invi.ir/gold-price/18carat"

def get_invi_price():
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    
    # Method 1: Try to extract from __NEXT_DATA__ script tag
    try:
        # Find the JSON data in the script tag
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', 
                         response.text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            current_price = data['props']['pageProps']['success']['result']['summary']['current_price']
            
            return {
                "platform": "Invi",
                "current_price": current_price,
                "currency": "IRR",
                "timestamp": data['props']['pageProps']['success']['result']['summary']['last_insert_time_today']
            }
    except (KeyError, json.JSONDecodeError, AttributeError) as e:
        # Fallback to regex method
        pass
    
    # Method 2: Direct regex extraction as fallback
    match = re.search(r'"current_price":"(\d+)"', response.text)
    raw_text = match.group(1)
    if match:
        return {
            "Platform": "Invi",
            "Price": match.group(1),
            "currency": "IRR",
            "raw":raw_text,
            "timestamp": None
        }
    
    raise ValueError("Could not extract current_price from the page")

# Usage
if __name__ == "__main__":
    result = get_invi_price()
    print(json.dumps(result, indent=2))

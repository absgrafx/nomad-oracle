import requests
import time
import hashlib
import hmac
import base64
from urllib.parse import urlencode
import os
from dotenv import load_dotenv

# Load environment variables
env_path = "/usr/local/etc/renogy/renogy.env"
load_dotenv(env_path)

# API Credentials
host = os.getenv("RENOGY_HOST")
sk = os.getenv("SECRET_KEY")
ak = os.getenv("ACCESS_KEY")

# Helper Functions
def get_param_str(params):
    """Construct the query parameter string."""
    return urlencode(params)

def calc_sign(ts, url, param_str, secret):
    """Calculate the signature."""
    to_sign = f"{ts}.{url}.{param_str}"
    hashed = hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).digest()
    return base64.b64encode(hashed).decode()

# Main API Call
def get_device_data(device_id):
    """Retrieve data from the device."""
    # Set up parameters and headers
    timestamp = int(time.time() * 1000)
    url_path = f"/device/data/latest/{device_id}"
    params = {}  # Include any query parameters here
    param_str = get_param_str(params)
    signature = calc_sign(timestamp, url_path, param_str, sk)
    
    url = f"{host}{url_path}"
    headers = {
        "Access-Key": ak,
        "Signature": signature,
        "Timestamp": str(timestamp),
    }
    
    # Send request
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get("data")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Test the Function
if __name__ == "__main__":
    print("Testing API connection...")
    test_device_id = "4721167408096062914"  # Replace with a valid device ID
    print(get_device_data(test_device_id))
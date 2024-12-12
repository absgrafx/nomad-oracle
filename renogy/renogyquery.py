import requests
import time
import hashlib
import hmac
import base64
from urllib.parse import urlencode
import os
from influxdb_client import InfluxDBClient, Point, WriteOptions
from dotenv import load_dotenv

# Load environment variables
env_path = "/usr/local/etc/renogy/renogy.env"
load_dotenv(env_path)

# TIMING
collect_interval = int(os.getenv("COLLECTION_INTERVAL", 300))  # Default to 5 minutes

# API Credentials
host = os.getenv("RENOGY_HOST")
sk = os.getenv("SECRET_KEY")
ak = os.getenv("ACCESS_KEY")

# InfluxDB setup
influx_url = os.getenv("INFLUX_URL")
influx_token = os.getenv("INFLUX_TOKEN")
influx_org = os.getenv("INFLUX_ORG")
influx_bucket = os.getenv("INFLUX_BUCKET")

client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)

# Parse devices from .env
def load_devices():
    """Load devices from the environment file."""
    devices_raw = os.getenv("DEVICES")
    if not devices_raw:
        raise ValueError("No devices configured in the .env file")
    devices = {}
    for pair in devices_raw.split(","):
        name, device_id = pair.split(":")
        devices[name.strip()] = device_id.strip()
    return devices

# Helper Functions
def get_param_str(params):
    """Construct the query parameter string."""
    return urlencode(params)

def calc_sign(ts, url, param_str, secret):
    """Calculate the signature."""
    to_sign = f"{ts}.{url}.{param_str}"
    hashed = hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).digest()
    return base64.b64encode(hashed).decode()

# API Call
def get_device_data(device_id):
    """Retrieve data from a device."""
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

# Write to InfluxDB
def write_to_influx(device_name, data):
    """Write device data to InfluxDB."""
    with client.write_api(write_options=WriteOptions(batch_size=1)) as write_api:
        point = Point(device_name).tag("device", device_name)
        for key, value in data.items():
            if isinstance(value, (int, float)):
                point.field(key, value)
        write_api.write(bucket=influx_bucket, record=point)

# Monitor Devices
def monitor_devices():
    """Query and log data for all devices."""
    devices = load_devices()
    for device_name, device_id in devices.items():
        data = get_device_data(device_id)
        if data:
            write_to_influx(device_name, data)

# Main Loop
if __name__ == "__main__":
    print("Starting Renogy monitoring...")
    while True:
        monitor_devices()
        time.sleep(collect_interval)
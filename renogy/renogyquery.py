import requests
import time
import hashlib
import hmac
import os
from influxdb_client import InfluxDBClient, Point, WriteOptions
from dotenv import load_dotenv

# Load environment variables
env_path = "/usr/local/etc/renogy/renogy.env"
load_dotenv(env_path)

# TIMING
collect_interval = int(os.getenv("COLLECTION_INTERVAL", 300))  # Default to 5 minutes if not set

# API Credentials
host = os.getenv("RENOGY_HOST")
sk = os.getenv("SECRET_KEY")
ak = os.getenv("ACCESS_KEY")
access_token = "your_access_token"  # Replace or update this dynamically if necessary

# InfluxDB setup
influx_url = os.getenv("INFLUX_URL")
influx_token = os.getenv("INFLUX_TOKEN")
influx_org = os.getenv("INFLUX_ORG")
influx_bucket = os.getenv("INFLUX_BUCKET")

client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)

# Parse devices from .env
def load_devices():
    devices_raw = os.getenv("DEVICES")
    if not devices_raw:
        raise ValueError("No devices configured in the .env file")
    devices = {}
    for pair in devices_raw.split(","):
        name, device_id = pair.split(":")
        devices[name.strip()] = device_id.strip()
    return devices

def get_device_data(device_id):
    timestamp = int(time.time() * 1000)
    sign = hmac.new(sk.encode(), f"{ak}{timestamp}".encode(), hashlib.sha256).hexdigest()
    url = f"{host}/device/data/latest/{device_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Sign": sign,
        "X-Timestamp": str(timestamp),
        "X-Ak": ak,
        "Access-Key": ak,  # Add this line
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("data")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def write_to_influx(device_name, data):
    with client.write_api(write_options=WriteOptions(batch_size=1)) as write_api:
        point = Point(device_name).tag("device", device_name)
        for key, value in data.items():
            if isinstance(value, (int, float)):
                point.field(key, value)
        write_api.write(bucket=influx_bucket, record=point)

def monitor_devices():
    devices = load_devices()
    for device_name, device_id in devices.items():
        data = get_device_data(device_id)
        if data:
            write_to_influx(device_name, data)

if __name__ == "__main__":
    while True:
        monitor_devices()
        time.sleep(collect_interval)
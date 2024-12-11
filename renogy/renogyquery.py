import requests
import time
import hashlib
import hmac
import json
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WriteOptions

# API Credentials
host = "https://openapi.renogy.com"
sk = "your_secret_key"
ak = "your_access_key"
access_token = "your_access_token"

# InfluxDB setup
influx_url = "http://localhost:8086"
influx_token = "your_influxdb_token"
influx_org = "your_organization"
influx_bucket = "power_monitoring"

client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)

def get_device_data(device_id):
    timestamp = int(time.time() * 1000)
    sign = hmac.new(sk.encode(), f"{ak}{timestamp}".encode(), hashlib.sha256).hexdigest()
    url = f"{host}/device/data/latest/{device_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Sign": sign,
        "X-Timestamp": str(timestamp),
        "X-Ak": ak,
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
    devices = {
        "Solar Charger": "4721167408096062914",
        "Main Shunt": "4748103642362861071",
        "Inverter Shunt": "4775681794258120258",
    }
    for device_name, device_id in devices.items():
        data = get_device_data(device_id)
        if data:
            write_to_influx(device_name, data)

if __name__ == "__main__":
    while True:
        monitor_devices()
        time.sleep(300)  # Every 5 minutes
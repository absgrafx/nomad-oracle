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

# Define fields to process for each device
SOLAR_CONTROLLER_FIELDS = {
    "auxiliaryBatteryTemperature": ("BatteryTemp", float, 2),
    "solarWatts": ("WattsSolar", float, 4),
    "solarChargingVolts": ("VoltsSolar", float, 4),
    "solarChargingAmps": ("AmpsSolar", float, 4),
    "auxiliaryBatteryChargingVolts": ("VoltsMPPT", float, 2),
    "gridChargeAmps": ("AmpsMPPT", float, 4, lambda v: v / 1000)  # Convert to Amps
}

MAIN_SHUNT_FIELDS = {
    "batteryVolts": ("VoltsMain", float, 4),
    "power": ("WattsMain", float, 4)
}

INVERTER_SHUNT_FIELDS = {
    "batteryVolts": ("VoltsInv", float, 4),
    "power": ("WattsInv", float, 4)
}

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

def transform_data(raw_data, field_mapping):
    """Transform raw data based on field mapping."""
    transformed = {}
    for raw_field, (new_field, dtype, precision, *transforms) in field_mapping.items():
        if raw_field in raw_data:
            value = raw_data[raw_field]
            # Apply any transformations
            for transform in transforms:
                value = transform(value)
            try:
                transformed[new_field] = round(dtype(value), precision)
            except ValueError:
                print(f"Error converting field {raw_field} with value {value}")
    return transformed

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


# Monitor Devices
def monitor_devices():
    """Query and log data for all devices."""
    devices = load_devices()
    combined_data = []

    for device_name, device_id in devices.items():
        raw_data = get_device_data(device_id)
        if raw_data:
            if device_name == "Solar":
                transformed_data = transform_data(raw_data, SOLAR_CONTROLLER_FIELDS)
            elif device_name == "Main":
                transformed_data = transform_data(raw_data, MAIN_SHUNT_FIELDS)
            elif device_name == "Inverter":
                transformed_data = transform_data(raw_data, INVERTER_SHUNT_FIELDS)

            # Append transformed data with the device name
            if transformed_data:
                combined_data.append({"device": device_name, "data": transformed_data})

    if combined_data:
        write_combined_to_influx(combined_data)


# Write Combined Data to InfluxDB
def write_combined_to_influx(combined_data):
    """Write combined data to InfluxDB with proper device tagging."""
    with client.write_api(write_options=WriteOptions(batch_size=1)) as write_api:
        for entry in combined_data:
            device_name = entry["device"]
            data = entry["data"]

            # Create a Point for each device's data
            point = Point("PowerMonitoring").tag("device", device_name)
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    point.field(key, value)
            write_api.write(bucket=influx_bucket, record=point)

# Main Loop
if __name__ == "__main__":
    print("Starting Renogy monitoring...")
    while True:
        monitor_devices()
        time.sleep(collect_interval)
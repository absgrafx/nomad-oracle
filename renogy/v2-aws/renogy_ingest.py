import sys
import os

# Add the dependencies folder to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
dependencies_dir = os.path.join(current_dir, "dependencies")
sys.path.append(dependencies_dir)

import requests
import time
import hashlib
import hmac
import base64
import json
from urllib.parse import urlencode
import boto3
from datetime import datetime
import logging

#################### 
# Init Boto and Renogy API 
#####################
cloudwatch_client = boto3.client("cloudwatch")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
timestream_client = boto3.client("timestream-write")

#################### 
# HELPER FUNCTIONS Secrets, Signature, Devices, DeviceDetail
#####################
def get_renogy_secrets():
    """Retrieve secrets from AWS Secrets Manager."""
    secrets_client = boto3.client("secretsmanager")
    secret_name = os.getenv("RENOGY_SECRET_NAME", "renogy_api_secrets")

    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    return secret["SECRET_KEY"], secret["ACCESS_KEY"]

# Calculate signature
def calc_sign(ts, url, param_str, secret):
    """Calculate the signature."""
    to_sign = f"{ts}.{url}.{param_str}"
    hashed = hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).digest()
    return base64.b64encode(hashed).decode()

# Get device list
def get_device_list(host, ak, sk):
    """Retrieve the list of devices."""
    timestamp = int(time.time() * 1000)
    url_path = "/device/list"
    param_str = ""
    signature = calc_sign(timestamp, url_path, param_str, sk)

    url = f"{host}{url_path}"
    headers = {
        "Access-Key": ak,
        "Signature": signature,
        "Timestamp": str(timestamp),
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            devices = response.json()
            if isinstance(devices, list):
                return devices
            elif isinstance(devices, dict):
                return devices.get("data", [])
            else:
                print(f"Unexpected response format: {devices}")
                return []
        except Exception as e:
            print(f"Error parsing response JSON: {e}")
            return []
    else:
        print(f"Error fetching device list: {response.status_code} - {response.text}")
        return []
    
# Extract device info
def extract_device_info(devices):
    """Extract deviceId, category, name, and sku from subdevices."""
    device_info = []
    for device in devices:
        # Only process sublist devices
        for subdevice in device.get("sublist", []):
            device_info.append({
                "deviceId": subdevice["deviceId"],
                "category": subdevice["category"],
                "name": subdevice["name"],
                "sku": subdevice["sku"]
            })
    return device_info

#################### 
# GET DEVICE DATA 
#####################
def get_device_data(device_id, host, ak, sk):
    """Retrieve data for a specific device."""
    timestamp = int(time.time() * 1000)
    url_path = f"/device/data/latest/{device_id}"
    param_str = ""
    signature = calc_sign(timestamp, url_path, param_str, sk)

    url = f"{host}{url_path}"
    headers = {
        "Access-Key": ak,
        "Signature": signature,
        "Timestamp": str(timestamp),
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("data")
        logger.info(f"Retrieved data for device {device_id}: {data}")
        print(f"Retrieved data for device {device_id}: {data}")
    else:
        logger.error(f"Error fetching data for device {device_id}: {response.status_code} - {response.text}")
        return None
    
#################### 
# PROCESS DEVICE DATA 
#####################
def process_device_data(device_data, category, device_id, name, sku):
    """Process device data based on category."""
    transformed = []

    # Define uname based on category
    if category == "Controller":
        uname = f"mppt-{device_id[-3:]}"
        # MPPT (primary: sub="pri")
        amps_mpt = device_data.get("gridChargeAmps", 0.0) / 1000
        volts_mpt = device_data.get("auxiliaryBatteryChargingVolts", 0.0)
        watts_mpt = amps_mpt * volts_mpt
        transformed.append({"measure": "amps", "value": round(amps_mpt, 4), "sub": "pri"})
        transformed.append({"measure": "volt", "value": round(volts_mpt, 4), "sub": "pri"})
        transformed.append({"measure": "watt", "value": round(watts_mpt, 4), "sub": "pri"})

        # Solar (sub="sol")
        transformed.append({"measure": "watt", "value": round(device_data.get("solarWatts", 0.0), 4), "sub": "sol"})
        transformed.append({"measure": "volt", "value": round(device_data.get("solarChargingVolts", 0.0), 4), "sub": "sol"})
        transformed.append({"measure": "amps", "value": round(device_data.get("solarChargingAmps", 0.0), 4), "sub": "sol"})

        # Load (sub="lod")
        volts_load = device_data.get("loadVolts", 0.0)
        amps_load = device_data.get("loadAmps", 0.0)
        watts_load = volts_load * amps_load
        transformed.append({"measure": "volt", "value": round(volts_load, 4), "sub": "lod"})
        transformed.append({"measure": "amps", "value": round(amps_load, 4), "sub": "lod"})
        transformed.append({"measure": "watt", "value": round(watts_load, 4), "sub": "lod"})

        # Temperature (single value, no sub)
        battery_temp = (device_data.get("auxiliaryBatteryTemperature", 0.0) * 1.8) + 32
        transformed.append({"measure": "temp", "value": round(battery_temp, 2), "sub": "pri"})

    elif category == "Battery Shunt":
        uname = f"shnt-{device_id[-3:]}"
        # Primary shunt values (sub="pri")
        volts_shnt = device_data.get("batteryVolts", 0.0)
        amps_shnt = device_data.get("current", 0.0)
        watts_shunt = volts_shnt * amps_shnt
        transformed.append({"measure": "volt", "value": round(volts_shnt, 4), "sub": "pri"})
        transformed.append({"measure": "amps", "value": round(amps_shnt, 4), "sub": "pri"})
        transformed.append({"measure": "watt", "value": round(watts_shunt, 4), "sub": "pri"})

    else:
        print(f"No transformation rules for category: {category}")
        return []

    # Add common fields to each measurement
    for item in transformed:
        item.update({
            "category": category,
            "device_id": device_id,
            "name": name,
            "sku": sku,
            "uname": uname
        })

    print(f"Transformed native system load data: {transformed}")
    return transformed

#################### 
# CALCULATE SYSTEM LOAD 
#####################
def calculate_system_load(transformed_data):
    """Calculate derived system load metrics."""
    try:
        # Extract relevant measurements from transformed data
        shnt_258_amps = next(item for item in transformed_data if item["uname"] == "shnt-258" and item["sub"] == "pri" and item["measure"] == "amps")["value"]
        mppt_914_amps = next(item for item in transformed_data if item["uname"] == "mppt-914" and item["sub"] == "pri" and item["measure"] == "amps")["value"]
        shnt_071_amps = next(item for item in transformed_data if item["uname"] == "shnt-071" and item["sub"] == "pri" and item["measure"] == "amps")["value"]

        shnt_258_watts = next(item for item in transformed_data if item["uname"] == "shnt-258" and item["sub"] == "pri" and item["measure"] == "watt")["value"]
        mppt_914_watts = next(item for item in transformed_data if item["uname"] == "mppt-914" and item["sub"] == "pri" and item["measure"] == "watt")["value"]
        shnt_071_watts = next(item for item in transformed_data if item["uname"] == "shnt-071" and item["sub"] == "pri" and item["measure"] == "watt")["value"]

        shnt_071_volts = next(item for item in transformed_data if item["uname"] == "shnt-071" and item["sub"] == "pri" and item["measure"] == "volt")["value"]

        # Derived values
        load_amps = (-1.0 * ((shnt_258_amps + mppt_914_amps) - shnt_071_amps))
        load_watts = (-1.0 * ((shnt_258_watts + mppt_914_watts) - shnt_071_watts))
        load_volts = shnt_071_volts

        # Add derived device measurements
        derived_device = [
            {"measure": "amps", "value": round(load_amps, 4), "sub": "pri"},
            {"measure": "watt", "value": round(load_watts, 4), "sub": "pri"},
            {"measure": "volt", "value": round(load_volts, 4), "sub": "pri"}
        ]

        # Add common fields to the derived device
        for item in derived_device:
            try:
                item.update({
                    "device_id": "derived-001",  # Placeholder for derived metrics
                    "uname": "load-001",
                    "name": "RNG-SYST",
                    "category": "Derived",
                    "sku": "RNG-SYST"
                })
            except KeyError as e:
                logger.error(f"Derived data missing keys: {item}. Error: {e}")

        print(f"Derived system load data: {derived_device}")
        return derived_device

    except StopIteration as e:
        print(f"Error calculating derived system load: Missing data for calculation. {e}")
        return []

#################### 
# PUBLISH TO TIMESTREAM 
#####################
def write_to_timestream(combined_data, db, table):
    # Write data to Timestream
    # Define required keys for validation
    required_keys = ["device_id", "uname", "sub", "category", "name", "sku", "measure", "value"]
    for entry in combined_data:
        records = []
        # Get current time in milliseconds since epoch
        current_time_ms = int(datetime.now().replace(second=0, microsecond=0).timestamp() * 1000)

        for index, entry in enumerate(combined_data):
            for item in entry:
                 # Log invalid records
                if not all(key in item for key in required_keys):
                    logger.warning(f"Skipping record due to missing keys: {item}")
                    print(f"Skipping record due to missing keys: {item}")
                    continue  # Skip invalid records

                records.append({
                    "MeasureName": item["measure"],
                    "MeasureValue": str(item["value"]),
                    "MeasureValueType": "DOUBLE",
                    "Time": str(current_time_ms),  # Use milliseconds since epoch
                    "TimeUnit": "MILLISECONDS",
                    "Dimensions": [
                        {"Name": "device_id", "Value": item["device_id"]},
                        {"Name": "uname", "Value": item["uname"]},
                        {"Name": "sub", "Value": item["sub"]},
                        {"Name": "category", "Value": item["category"]},
                        {"Name": "name", "Value": item["name"]},
                        {"Name": "sku", "Value": item["sku"]},
                    ]
                })

    # Log and write records to Timestream
    logger.info(f"Writing {len(records)} records to Timestream for table: {table}")
    if records:
        try:
            timestream_client.write_records(
                DatabaseName=db,
                TableName=table,
                Records=records
            )
            logger.info("Successfully wrote records to Timestream")
        except Exception as e:
            logger.error(f"Error writing records to Timestream: {e}")
            if hasattr(e, 'response') and 'RejectedRecords' in e.response['Error']:
                logger.error(f"RejectedRecords details: {e.response['Error']['RejectedRecords']}")

####################
# PUBLISH MULTIPLE METRICS TO CLOUDWATCH
####################
def publish_metrics_to_cloudwatch(metrics):
    """Send multiple custom metrics to CloudWatch in a single request."""
    try:
        cloudwatch_client.put_metric_data(
            Namespace="RenogyMetrics",
            MetricData=metrics
        )
        logging.info(f"Published {len(metrics)} metrics to CloudWatch.")
    except Exception as e:
        logging.error(f"Error publishing metrics to CloudWatch: {e}")


#################### 
# LAMBDA HANDLER 
#####################
def handler(event, context):
    """Lambda entry point."""
    sk, ak = get_renogy_secrets()
    host = os.getenv("RENOGY_HOST", "https://openapi.renogy.com")
    db = os.getenv("TIMESTREAM_DB", "nomad_oracle")
    table = os.getenv("TIMESTREAM_TABLE", "renogy_data")

    # Step 1: Get all devices
    devices = get_device_list(host, ak, sk)
    device_info = extract_device_info(devices)

    # Step 2: Query each device for its latest data
    combined_data = []
    for device in device_info:
        raw_data = get_device_data(device["deviceId"], host, ak, sk)
        if raw_data:
            transformed_data = process_device_data(
                raw_data, device["category"], device["deviceId"], device["name"], device["sku"]
            )
            if transformed_data:
                combined_data.append(transformed_data)

    # Step 3: Calculate derived system load metrics
    derived_load = calculate_system_load([item for sublist in combined_data for item in sublist])
    if derived_load:
        combined_data.append(derived_load)

    # Step 4: Write all data to Timestream
    if combined_data:
        write_to_timestream(combined_data, db, table)
    
    # Step 5: Collect Metrics and Publish to CloudWatch
    cw_metrics = []
    try:
        shnt_071_volt = next(
            item for sublist in combined_data for item in sublist
            if item["uname"] == "shnt-071" and item["measure"] == "volt" and item["sub"] == "pri"
        )["value"]
        shnt_071_amps = next(
            item for sublist in combined_data for item in sublist
            if item["uname"] == "shnt-071" and item["measure"] == "amps" and item["sub"] == "pri"
        )["value"]
        mppt_914_amps = next(
            item for sublist in combined_data for item in sublist
            if item["uname"] == "mppt-914" and item["measure"] == "amps" and item["sub"] == "pri"
        )["value"]
        mppt_914_volts = next(
            item for sublist in combined_data for item in sublist
            if item["uname"] == "mppt-914" and item["measure"] == "volt" and item["sub"] == "pri"
        )["value"]

        # Add metrics to the list
        cw_metrics.append({
            "MetricName": "MainVoltage",
            "Value": shnt_071_volt,
            "Unit": "None",
            "Dimensions": [{"Name": "Device", "Value": "Main"}]
        })
        cw_metrics.append({
            "MetricName": "MainCurrent",
            "Value": shnt_071_amps,
            "Unit": "None",
            "Dimensions": [{"Name": "Device", "Value": "Main"}]
        })
        cw_metrics.append({
            "MetricName": "MPPTVoltage",
            "Value": mppt_914_volts,
            "Unit": "None",
            "Dimensions": [{"Name": "Device", "Value": "MPPT"}]
        })
        cw_metrics.append({
            "MetricName": "MPPTCurrent",
            "Value": mppt_914_amps,
            "Unit": "None",
            "Dimensions": [{"Name": "Device", "Value": "MPPT"}]
        })

        # Publish all metrics in a single call
        publish_metrics_to_cloudwatch(cw_metrics)
        print(f"Published {len(cw_metrics)} metrics to CloudWatch.")
        logging.info (f"Published {len(cw_metrics)} metrics to CloudWatch.")
        
    except StopIteration:
        logging.error("Required data for metrics not found.")
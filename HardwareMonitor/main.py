import os
from fastapi import FastAPI, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests

import threading, time, json, boto3
from datetime import datetime
from botocore.exceptions import BotoCoreError, NoCredentialsError
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# Setup S3
s3_buffer = []
s3_bucket_name = os.getenv("S3_BUCKET_NAME")
s3_prefix = "telemetry/"
s3 = boto3.client("s3")

PROBE_INTERVAL = int(os.getenv("PROBE_INTERVAL",2)) # 2secs
BATCH_SIZE = int(os.getenv("BATCH_SIZE",10)) # 10 records

# Setup MongoDB
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
mongo_db_name = os.getenv("MONGO_DB_NAME", "bmc_telemetry_db")
mongo_collection_name = os.getenv("MONGO_COLLECTION_NAME", "s3_telemetry_batches")

mongo_client = MongoClient(mongo_uri)
mongo_db = mongo_client[mongo_db_name]
mongo_collection = mongo_db[mongo_collection_name]

app = FastAPI()

LIBRE_HARDWARE_MONITORING_ENDPOINT = "http://localhost:8085/data.json"

DEVICE_NAME=os.getenv("DEVICE_NAME")
MODULES_TO_MONITOR=os.getenv("MODULES_TO_MONITOR")

# Define Gauges
cpu_temp_gauge = Gauge("cpu_temperature_celsius", "CPU Temperature", ["core"])
cpu_min_temp_gauge = Gauge("cpu_min_temperature_celsius", "CPU Temperature (Min)", ["core"])
cpu_max_temp_gauge = Gauge("cpu_max_temperature_celsius", "CPU Temperature (Max)", ["core"])

cpu_voltage_guage = Gauge("cpu_voltage_volt", "CPU Voltage", ["core"])
cpu_powers_guage = Gauge("cpu_powers_watt", "CPU Power", ["core"])
cpu_load_gauge = Gauge("cpu_load_percent", "CPU Load", ["core"])


def classify_snapshot(snapshot):
    reasons = []
    status = "healthy"

    #Temperature checks
    for sensor, data in snapshot.get("temperature", {}).items():
        temp = data.get("value", 0)
        if temp > 90:
            reasons.append(f"Temperature too high on '{sensor}' ({temp}°C > 90°C)")
        elif temp > 80:
            reasons.append(f"Temperature elevated on '{sensor}' ({temp}°C > 80°C)")

    #Load checks
    for sensor, load in snapshot.get("load", {}).items():
        if load > 80:
            reasons.append(f"CPU load is high on '{sensor}' ({load}% > 80%)")

    #Voltage checks
    for sensor, volt in snapshot.get("voltage", {}).items():
        if volt > 1.6:
            reasons.append(f"Voltage too high on '{sensor}' ({volt}V > 1.6V)")

    #Power checks
    for sensor, pwr in snapshot.get("power", {}).items():
        if pwr > 80:
            reasons.append(f"Power draw is critical on '{sensor}' ({pwr}W > 80W)")
        elif pwr > 50:
            reasons.append(f"Power draw is elevated on '{sensor}' ({pwr}W > 50W)")

    if any("too high" in r or "critical" in r for r in reasons):
        status = "threat"
    elif reasons:
        status = "unhealthy"

    return status, reasons


def update_metrics():
    """
        Hardcoded way to fetch device metrics from sensors
        Currently Monitors CPU temperature, voltage, power and load
    """
    try:
        data = requests.get(LIBRE_HARDWARE_MONITORING_ENDPOINT).json()
        
        temp_data = {}
        load_data = {}
        volt_data = {}
        power_data = {}

        for hw in data["Children"]:
            if DEVICE_NAME in hw["Text"]:
                for sensor in hw["Children"]:
                    if len(sensor["Children"]) > 0 and sensor["Text"] in MODULES_TO_MONITOR:
                        for child in sensor["Children"]:
                            if child["Text"]=="Voltages":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = float(elem["Value"].split(" ")[0])
                                    cpu_voltage_guage.labels(core=name).set(value)
                                    volt_data[name]=value
                            if child["Text"]=="Powers":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = float(elem["Value"].split(" ")[0])
                                    cpu_powers_guage.labels(core=name).set(value)
                                    power_data[name]=value
                            if child["Text"]=="Temperatures":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = float(elem["Value"].split(" ")[0])
                                    min = float(elem["Min"].split(" ")[0])
                                    max = float(elem["Max"].split(" ")[0])

                                    cpu_temp_gauge.labels(core=name).set(value)
                                    cpu_min_temp_gauge.labels(core=name).set(min)
                                    cpu_max_temp_gauge.labels(core=name).set(max)

                                    temp_data[name] = {
                                        "value": value,
                                        "min": min,
                                        "max": max
                                    }

                            if child["Text"]=="Load":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = float(elem["Value"].split(" ")[0])
                                    cpu_load_gauge.labels(core=name).set(value)
                                    load_data[name] = value

        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": temp_data,
            "load": load_data,
            "voltage": volt_data,
            "power": power_data
        }
        health_status, reasons = classify_snapshot(snapshot)
        snapshot["health_status"] = health_status
        snapshot["reasons"] = reasons
        return snapshot

    except Exception as e:
        print(f"Error fetching metrics: {e}")

# Expose /metrics
@app.get("/metrics")
def metrics():
    update_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.on_event("startup")
def start_background_thread():
    thread = threading.Thread(target=background_collector, daemon=True)
    thread.start()

def to_unix_timestamp(ts: str) -> str:
    return str(int(datetime.fromisoformat(ts).timestamp()))

def summarize_batch(buffer, s3_path, start_time, end_time):
    summary = {
        "s3_path": s3_path,
        "start_time": start_time,
        "end_time": end_time,
        "total_records": len(buffer),
        "threat_count": 0,
        "unhealthy_count": 0,
        "healthy_count": 0,
        "reasons": []  # list of {timestamp, reason}
    }

    for record in buffer:
        status = record.get("health_status", "healthy")
        timestamp = record.get("timestamp", "unknown")
        reasons = record.get("reasons", [])

        if status == "threat":
            summary["threat_count"] += 1
        elif status == "unhealthy":
            summary["unhealthy_count"] += 1
        else:
            summary["healthy_count"] += 1

        for reason in reasons:
            summary["reasons"].append({
                "timestamp": timestamp,
                "reason": reason
            })

    return summary

def background_collector():
    global s3_buffer
    batch_start_time = None

    while True:
        time.sleep(PROBE_INTERVAL)

        snapshot = update_metrics()
        if snapshot:
            if batch_start_time is None:
                batch_start_time = to_unix_timestamp(snapshot["timestamp"])
            s3_buffer.append(snapshot)

        if len(s3_buffer) >= BATCH_SIZE:  # 5 samples × 2s = 10s
            try:
                batch_end_time = to_unix_timestamp(s3_buffer[-1]["timestamp"])
                filename = f"{s3_prefix}{batch_start_time}_to_{batch_end_time}.json"

                # TODO: enable this when data upload is needed
                # s3.put_object(
                #     Bucket=s3_bucket_name,
                #     Key=filename,
                #     Body=json.dumps(s3_buffer).encode("utf-8"),
                #     ContentType="application/json"
                # )

                # Summarize in MongoDB
                summary_doc = summarize_batch(
                    buffer=s3_buffer,
                    s3_path=filename,
                    start_time=batch_start_time,
                    end_time=batch_end_time
                )
                mongo_collection.insert_one(summary_doc)

                print(f"Uploaded {filename} with {len(s3_buffer)} entries")
                
                s3_buffer = []
                batch_start_time = None
            
            except (BotoCoreError, NoCredentialsError) as e:
                print(f"S3 upload error: {e}")

from fastapi import FastAPI, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests

app = FastAPI()

LIBRE_HARDWARE_MONITORING_ENDPOINT = "http://172.23.192.1:8085/data.json"

DEVICE_NAME="ADITYA-OMEN"
MODULES_TO_MONITOR=["Intel Core i7-14650HX"]

# Define Gauges
cpu_temp_gauge = Gauge("cpu_temperature_celsius", "CPU Temperature", ["core"])
cpu_min_temp_gauge = Gauge("cpu_min_temperature_celsius", "CPU Temperature (Min)", ["core"])
cpu_max_temp_gauge = Gauge("cpu_max_temperature_celsius", "CPU Temperature (Max)", ["core"])

cpu_voltage_guage = Gauge("cpu_voltage_volt", "CPU Voltage", ["core"])
cpu_powers_guage = Gauge("cpu_powers_watt", "CPU Power", ["core"])
cpu_load_gauge = Gauge("cpu_load_percent", "CPU Load", ["core"])


def update_metrics():
    """
        Hardcoded way to fetch device metrics from sensors
        Currently Monitors CPU temperature, voltage, power and load
    """
    try:
        data = requests.get(LIBRE_HARDWARE_MONITORING_ENDPOINT).json()
        for hw in data["Children"]:
            if DEVICE_NAME in hw["Text"]:
                for sensor in hw["Children"]:
                    if len(sensor["Children"]) > 0 and sensor["Text"] in MODULES_TO_MONITOR:
                        for child in sensor["Children"]:
                            if child["Text"]=="Voltages":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = elem["Value"].split(" ")[0]
                                    
                                    # sensor_id = elem["SensorId"]
                                    # min = elem["Min"]
                                    # max = elem["Max"]

                                    cpu_voltage_guage.labels(core=name).set(value)
                            if child["Text"]=="Powers":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = elem["Value"].split(" ")[0]
                                    
                                    # sensor_id = elem["SensorId"]
                                    # min = elem["Min"]
                                    # max = elem["Max"]

                                    cpu_powers_guage.labels(core=name).set(value)
                            if child["Text"]=="Temperatures":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = elem["Value"].split(" ")[0]
                                    
                                    # sensor_id = elem["SensorId"]
                                    min = elem["Min"].split(" ")[0]
                                    max = elem["Max"].split(" ")[0]

                                    cpu_temp_gauge.labels(core=name).set(value)
                                    cpu_min_temp_gauge.labels(core=name).set(min)
                                    cpu_max_temp_gauge.labels(core=name).set(max)

                            if child["Text"]=="Load":
                                for elem in child["Children"]:
                                    name = elem["Text"]
                                    value = elem["Value"].split(" ")[0]
                                    
                                    # sensor_id = elem["SensorId"]
                                    # min = elem["Min"]
                                    # max = elem["Max"]

                                    cpu_load_gauge.labels(core=name).set(value)

    except Exception as e:
        print(f"Error fetching metrics: {e}")

# Expose /metrics
@app.get("/metrics")
def metrics():
    update_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

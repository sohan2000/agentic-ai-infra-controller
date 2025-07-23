# Server to expose Hardware Metrics

This server is dependent on LibreHardwareMonitoring software.

Download it, and run it as a server. Most likely it will run on `http://172.23.192.1:8085`. If its running on a different port, please replace the value of `LIBRE_HARDWARE_MONITORING_ENDPOINT` in the main.py

Install the dependencies
```
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Run this server using the following command
```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Feel free to modify the `update_metrics()` logic to get device specific information.
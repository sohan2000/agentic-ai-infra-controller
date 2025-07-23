# Prometheus for Hardware Monitoring

Promethus is an industry standard hardware monitoring tool. For our application, we are monitoring the `/metrics` endpoint provided by the `HardwareMonitor` service.

`prometheus.yaml` file is configured according to the HardwareMonitor service, and can be deployed using Docker.

Use the following command to deploy Prometheus using Docker desktop.

```
docker run -d -p 9090:9090 --name prometheus -v "D:\AxiadoHackathon\Prometheus\prometheus.yaml:/etc/prometheus/prometheus.yml" prom/prometheus
```

Feel free to replace the path of premetheus.yaml as per your environment.

To verify, visit `http://localhost:9090`
To verify the metrics seen by prometheus, visit `http://localhost:9090/metrics`

Metrics scarped from HardwareMonitor service will be available at `http://host.docker.internal:8000/metrics`

Make sure that HardwareMonitor service is running before checking logs
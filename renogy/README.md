# Renogy Build 

## RapsberryPi Dependencies 
```bash
sudo apt update
sudo apt install python3 python3-pip
pip3 install requests python-dotenv influxdb-client
```

## Install InfluxDB 
* Listening on http://localhost:8086
```bash
sudo wget -qO- https://repos.influxdata.com/influxdata-archive_compat.key | sudo gpg --dearmor -o /usr/share/keyrings/influxdata-archive.gpg
sudo echo "deb [signed-by=/usr/share/keyrings/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main" | sudo tee /etc/apt/sources.list.d/influxdb.list
sudo apt update
sudo apt install -y influxdb2
sudo systemctl start influxdb
sudo systemctl enable influxdb
```

* configure influxdb
```bash
influx setup
```
* You will be prompted to provide:
	* Username: Admin username
	* Password: Admin password
	* Organization Name: e.g., power_org
	* Bucket Name: e.g., power_monitoring
	* Retention Period: in Hours, Use 0 for infinite retention
	* Setup a user token: Use the generated token to authenticate requests to InfluxDB

* Create Token 
```bash
influx auth create \
  --org power_org \
  --write-buckets \
  --read-buckets
```
* use the org, token and bucket name in the .env file


## Install Grafana 
* Listening on http://localhost:3000
```bash 
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

## Setup external environment file (that is not cloned)
```bash
sudo mkdir -p /usr/local/etc/renogy
sudo nano /usr/local/etc/renogy/renogy.env
# add the following lines
ACCESS_KEY=your_access_key
SECRET_KEY=your_secret_key
sudo chmod 600 /usr/local/etc/renogy/renogy.env
pip3 install python-dotenv
python3 /usr/local/src/nomad-oracle/renogy/renogyquery.py
```


## Implement Python Query 
git clone the repository 
```bash
cd /usr/local/src
git clone https://github.com/absgrafx/nomad-oracle.git
cd nomad-oracle/renogy
```
`renogyquery.py`

## Automate the script 
```bash
crontab -e
@reboot python3 /usr/local/src/renogyquery.py &
```


## Setup Grafana Dashboard 
Configure InfluxDB as a Data Source:
	•	In Grafana, go to “Configuration” > “Data Sources” > “Add Data Source” and select InfluxDB.
	•	Configure the connection using your InfluxDB details.
	•	Create Panels:
	•	Add visualizations for system voltage, watts, amperage, battery temperature, and SOC.
	•	Use queries like from(bucket: "power_monitoring") |> range(start: -5m) to fetch recent data.



# Renogy Build 

## RapsberryPi Dependencies 
```bash
sudo apt update
sudo apt install python3 python3-pip
pip3 install requests schedule influxdb-client
```

## Install InfluxDB 
```bash
wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
source /etc/os-release
test $VERSION_ID = "8" && echo "deb https://repos.influxdata.com/debian jessie stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
test $VERSION_ID = "9" && echo "deb https://repos.influxdata.com/debian stretch stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
test $VERSION_ID = "10" && echo "deb https://repos.influxdata.com/debian buster stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
sudo apt update
sudo apt install influxdb
sudo systemctl unmask influxdb
sudo systemctl enable influxdb
sudo systemctl start influxdb
```

## Install Grafana 
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



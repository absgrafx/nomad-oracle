# Renogy Lambda

## Overall Architecture
* renogy_ingest.py runs on lambda triggered every 60 seconds by EventBridge
    * Queries device list from Renogy API and decomposes device types, extracts unique names, device ids and types
    * Queries each device for current data, normalizes data and fields 
    * Transforms data if needed (convert to float, ensure volts, amps and watts are stored, calculate load amps and watts, convert celsius to fahrenheit)
    * Writes data to TimeStream database
    * Writes subset of data (main voltage) to Cloudwatch for alerting
* Requires the following: 
    * TimeStream database
    * Secrets Manager (for ak and sk API keys) 
    * Cloudwatch (for alerting)
    * EventBridge (for scheduling)  
    * IAM Role for Lambda, TimeStream, Secrets Manager, Cloudwatch, EventBridge

# prep the lambda function
```bash
cd lambda/renogy
pip install -r requirements.txt -t dependencies/
```
## Sample Data Sent to TimeStream 
```bash
Time	Category	Uname	MeasureName	MeasureValue	Sub	Device ID	Name	SKU
2024-12-15 12:00:00	Controller	mppt-965	amps	4.1900	pri	92058252333809665	Main	RNG-CTRL-ROVER60
2024-12-15 12:00:00	Controller	mppt-965	volt	13.5000	pri	92058252333809665	Main	RNG-CTRL-ROVER60
2024-12-15 12:00:00	Controller	mppt-965	watt	56.5650	pri	92058252333809665	Main	RNG-CTRL-ROVER60
2024-12-15 12:00:00	Controller	mppt-965	watt	126.9500	sol	92058252333809665	Main	RNG-CTRL-ROVER60
2024-12-15 12:00:00	Battery Shunt	shnt-071	volt	13.2830	pri	4748103642362861071	Main	RSHST-B02P300-G1
2024-12-15 12:00:00	Battery Shunt	shnt-071	watt	-65.3800	pri	4748103642362861071	Main	RSHST-B02P300-G1
``` 
import requests
import json
import time
import logging
from kafka import KafkaProducer
from influxdb import InfluxDBClient

# Kafka Configuration
KAFKA_BROKER_URL = 'localhost:9092'
KAFKA_TOPIC_INITIAL = 'initial_market_data'
KAFKA_TOPIC_REGULAR = 'market_data'

# API Configuration
API_URL = 'https://oxide.sensibull.com/v1/compute/cache/live_derivative_prices/256265'
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "frt-ref": "1b4b5m82wi2",
    "if-none-match": "c37a2847-5992-4eb5-9130-4613b87c4c02",
    "priority": "u=1, i",
    "sec-ch-ua": "\"Not)A;Brand\";v=\"99\", \"Google Chrome\";v=\"127\", \"Chromium\";v=\"127\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "x-device-id": "aee76e45-d634-4cc1-a064-552fa8a11b6a"
}

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Kafka producer
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER_URL],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def fetch_data():
    try:
        # Fetch data from API
        response = requests.get(API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        logging.info("Data fetched successfully")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data: {e}")
        return None

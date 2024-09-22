import json
import os
from datetime import datetime
from confluent_kafka import Consumer, KafkaException, KafkaError
import sys
import time
import logging
import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import debugpy


# Allow other computers to attach to debugpy at this IP address and port.
debugpy.listen(("0.0.0.0", 5678))
print("Waiting for debugger attach...")
debugpy.wait_for_client()
print("Debugger attached, starting execution.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# InfluxDB configuration
influxdb_url = "http://influxdb:8086"
influxdb_token = "RiesaiyZfLI1OwMyEPyqS_ladeliO87_VfON4QrPWm7dh-LXOflrhqkaDIB2jxg5bjM8xHEb1sOzD43CyIQ9Fw=="
influxdb_org = "options"
influxdb_bucket = "niftyfull"

write_client = influxdb_client.InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
write_api = write_client.write_api(write_options=SYNCHRONOUS)

def create_consumer():
    conf = {
        'bootstrap.servers': 'broker:29092',
        'group.id': 'consumer_group_1',
        'auto.offset.reset': 'earliest',
        'session.timeout.ms': 60000,  # Increase session timeout
        'heartbeat.interval.ms': 20000,  # Increase heartbeat interval
    }
    return Consumer(conf)

class ParseMessageToPointsError(Exception):
    """Custom exception for errors in Parse Message to Points."""
    pass

def parse_message_to_points_save_influxdb(message):
    live_data = json.loads(message)  # Parse JSON string into a dictionary

    logger.info('Starting to parse_message_to_points')

    try:
        expiry_date = live_data['payload']['expiry']
        token = live_data['payload']['token']
        logger.info(f"Expiry date: {expiry_date}, Token: {token}")
    except KeyError as e:
        logger.error(f"Error accessing expiry date or token: {e}")
        raise ParseMessageToPointsError(f"Missing expiry date or token in live data: {e}")
    
     # Access ATM strike and timestamp
    try:
        atm_strike_value = live_data['payload']['data'][f'{token}'][f'{expiry_date}']['atm_strike']
        timestampEpochSec = live_data['snapshot']['timestampEpochSec']
    except KeyError as e:
        logger.error(f"Error accessing ATM strike or timestamp: {e}")
        raise ParseMessageToPointsError(f"Missing ATM strike or timestamp in live data: {e}")

    # Access live payload and chain
    try:
        live_payload = live_data['payload']['data'][f'{token}'][f'{expiry_date}']
        live_chain = live_payload['chain']
    except KeyError as e:
        logger.error(f"Error accessing live payload or chain: {e}")
        raise ParseMessageToPointsError(f"Missing live payload or chain in live data: {e}")
    
    # Find the ATM strike object
    atm_strike_obj = live_chain.get(str(atm_strike_value), None)
    if not atm_strike_obj:
        logger.warning(f"ATM strike object not found for value {atm_strike_value}")
        raise ParseMessageToPointsError(f"ATM strike object not found for value {atm_strike_value}")
    
    live_chain_list = list(live_chain.items())
    atm_strike_index = next((index for index, (key, value) in enumerate(live_chain_list) if key == str(atm_strike_value)), None)
    
    if atm_strike_index is not None:
        logger.info(f"ATM strike index found at position {atm_strike_index}")
    
        #using the ATM strike index to get the previous and next 10 strikes
        prev_strikes = live_chain_list[atm_strike_index-10:atm_strike_index]
        next_strikes = live_chain_list[atm_strike_index+1:atm_strike_index+11]

        # Extracting required fields
        for strike_key, options in prev_strikes + next_strikes:
            for option_type, values in options.items():
                #check if option_type is 'CE' or 'PE' then only allow to proceed
                if option_type not in ['CE', 'PE']:
                    continue
                
                logger.info(f"Processing strike: {strike_key}")
                point = (
                    Point("options_data")
                    .tag("token", token)
                    .tag("expiry", expiry_date)
                    .tag("strike", strike_key)
                    .tag("option_type", option_type)
                    .field("last_price", float(values.get('last_price', 0)))
                    .field("net_change", float(values.get('net_change', 0)))
                    .field("oi", float(values.get('oi', 0)))
                    .field("oi_change", float(values.get('oi_change', 0)))
                    .field("volume", float(values.get('volume', 0)))
                    .field("time_value", float(values.get('time_value', 0)))
                    .field("pop", float(values.get('pop', 0)))
                    .time(datetime.utcfromtimestamp(timestampEpochSec), WritePrecision.S)
                )
                send_to_influxdb(point)
                
    else:
        logger.warning(f"ATM strike index not found for value {atm_strike_value}")
        raise ParseMessageToPointsError(f"ATM strike index not found for value {atm_strike_value}")


def send_to_influxdb(point):
    try:
        write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=point)
        logger.info('Data sent to InfluxDB')
    except Exception as e:
        logger.error(f"Failed to save to InfluxDB: {e}")


def consume_messages(consumer, topics):
    try:
        logger.info('Subscribing to topics: %s', topics)
        consumer.subscribe(topics)
        while True:
            try:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.warning('%% %s [%d] reached end at offset %d',
                                       msg.topic(), msg.partition(), msg.offset())
                    elif msg.error():
                        raise KafkaException(msg.error())
                else:
                    message_value = msg.value().decode('utf-8')
                    logger.info('Received message')
                    
                    # Parse and prepare data for InfluxDB
                    parse_message_to_points_save_influxdb(message_value)
                    consumer.commit(asynchronous=False)    
            except KafkaException as e:
                logger.error('Kafka error: %s', e)
                time.sleep(5)  # Wait before retrying
            except Exception as e:
                logger.error('Error: %s', e)
                time.sleep(5)  # Wait before retrying
    except KeyboardInterrupt:
        logger.info('Consumer interrupted')
    finally:
        logger.info('Closing consumer')
        consumer.close()

if __name__ == '__main__':
    while True:
        try:
            logger.info('Creating consumer')
            consumer = create_consumer()
            logger.info('Starting message consumption')
            consume_messages(consumer, ['nifty_full'])
        except Exception as e:
            logger.critical('Fatal error: %s', e)
            time.sleep(10)  # Wait before restarting the consumer
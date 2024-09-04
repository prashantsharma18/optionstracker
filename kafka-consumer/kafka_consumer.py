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
influxdb_token = "vqwL5iZLjcsNVs9I1vKYITaNj_uzPC45-XzyjNn4u8akFtMYClauQq0v8Z5ftgA6yUT5Auxf2sjwnz-K0U03ag=="
influxdb_org = "options"
influxdb_bucket = "nifty"

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

def is_first_message_of_the_day(message):
    current_date = datetime.now().date()
    if os.path.exists('first_message.json'):
        with open('first_message.json', 'r') as f:
            data = json.load(f)
            saved_date = datetime.fromisoformat(data['date']).date()
            return current_date > saved_date
    return True

def save_message_to_file(message):
    data = {
        'date': datetime.now().isoformat(),
        'message': message
    }
    with open('first_message.json', 'w') as f:
        json.dump(data, f)

def load_cached_message():
    if os.path.exists('first_message.json'):
        with open('first_message.json', 'r') as f:
            data = json.load(f)
            return data['message']
    return None

class ComputeDifferencesError(Exception):
    """Custom exception for errors in the compute_differences function."""
    pass

def compute_differences(live_data, static_data):
    try:
        logger.info('Starting to compute differences')
        
        try:
            expiry_date = live_data['payload']['expiry']
            token = live_data['payload']['token']
            logger.info(f"Expiry date: {expiry_date}, Token: {token}")
        except KeyError as e:
            logger.error(f"Error accessing expiry date or token: {e}")
            raise ComputeDifferencesError(f"Missing expiry date or token in live data: {e}")
        
        # Access static payload
        try:
            logger.info('Access static payload')
            static_payload = static_data['payload']['data'][f'{token}'][f'{expiry_date}']
            static_chain = static_payload['chain']
        except KeyError as e:
            logger.error(f"Error accessing static payload or chain: {e}")
            raise ComputeDifferencesError(f"Missing static payload or chain in static data: {e}")
        
        # Access ATM strike and timestamp
        try:
            atm_strike_value = live_data['payload']['data'][f'{token}'][f'{expiry_date}']['atm_strike']
            timestampEpochSec = live_data['snapshot']['timestampEpochSec']
        except KeyError as e:
            logger.error(f"Error accessing ATM strike or timestamp: {e}")
            raise ComputeDifferencesError(f"Missing ATM strike or timestamp in live data: {e}")

        # Access live payload and chain
        try:
            live_payload = live_data['payload']['data'][f'{token}'][f'{expiry_date}']
            live_chain = live_payload['chain']
        except KeyError as e:
            logger.error(f"Error accessing live payload or chain: {e}")
            raise ComputeDifferencesError(f"Missing live payload or chain in live data: {e}")

        # Find the ATM strike object
        atm_strike_obj = live_chain.get(str(atm_strike_value), None)
        if not atm_strike_obj:
            logger.warning(f"ATM strike object not found for value {atm_strike_value}")
            raise ComputeDifferencesError(f"ATM strike object not found for value {atm_strike_value}")

        live_chain_list = list(live_chain.items())
        atm_strike_index = next((index for index, (key, value) in enumerate(live_chain_list) if key == str(atm_strike_value)), None)

        if atm_strike_index is not None:
            logger.info(f"ATM strike index found at position {atm_strike_index}")
            
            greeks_before = []
            greeks_after = []
            start_index_before = max(0, atm_strike_index - 5)
            end_index_after = min(len(live_chain_list), atm_strike_index + 6)

            # Capture Greeks before and after the ATM strike
            try:
                for j in range(start_index_before, atm_strike_index + 1):
                    greeks_before.append((live_chain_list[j][0], live_chain_list[j][1]['greeks']))
                for j in range(atm_strike_index, end_index_after):
                    greeks_after.append((live_chain_list[j][0], live_chain_list[j][1]['greeks']))
            except KeyError as e:
                logger.error(f"Error accessing Greeks data: {e}")
                raise ComputeDifferencesError(f"Error accessing Greeks data: {e}")

            sum_differences_before = {}
            sum_differences_after = {}
            greeks_to_scale = {'callDelta', 'gamma', 'putDelta', 'theta', 'vega'}

            # Calculate sum differences before and after the ATM strike
            try:
                for strike_price, live_greeks in greeks_before:
                    static_greeks = static_chain.get(strike_price, {}).get('greeks', {})
                    for key in live_greeks:
                        if key in static_greeks:
                            if key not in sum_differences_before:
                                sum_differences_before[key] = 0
                            live_value = live_greeks[key] * 25 if key in greeks_to_scale else live_greeks[key]
                            static_value = static_greeks[key] * 25 if key in greeks_to_scale else static_greeks[key]
                            sum_differences_before[key] += live_value - static_value

                for strike_price, live_greeks in greeks_after:
                    static_greeks = static_chain.get(strike_price, {}).get('greeks', {})
                    for key in live_greeks:
                        if key in static_greeks:
                            if key not in sum_differences_after:
                                sum_differences_after[key] = 0
                            live_value = live_greeks[key] * 25 if key in greeks_to_scale else live_greeks[key]
                            static_value = static_greeks[key] * 25 if key in greeks_to_scale else static_greeks[key]
                            sum_differences_after[key] += live_value - static_value
            except KeyError as e:
                logger.error(f"Error during sum differences calculation: {e}")
                raise ComputeDifferencesError(f"Error during sum differences calculation: {e}")
            
            logger.info('Computed differences successfully')
            return sum_differences_before, sum_differences_after, timestampEpochSec
        
        else:
            logger.warning(f"ATM strike index not found for value {atm_strike_value}")
            raise ComputeDifferencesError(f"ATM strike index not found for value {atm_strike_value}")

    except ComputeDifferencesError as e:
        logger.error(f"ComputeDifferencesError: {e}")
        raise  # Re-raise the custom exception to be handled by the caller
    
    except Exception as e:
        logger.exception(f"Unexpected error in compute_differences: {e}")
        raise  # Re-raise the general exception to be handled by the caller


def send_to_influxdb(sum_differences_before, sum_differences_after, timestampEpochSec):
    try:
        point = Point("greeks_differences") \
            .time(datetime.utcfromtimestamp(timestampEpochSec), WritePrecision.S)

        # Add fields for each Greek in sum_differences_before
        for greek, value in sum_differences_before.items():
            point = point.field(f"put_{greek}", value)

        # Add fields for each Greek in sum_differences_after
        for greek, value in sum_differences_after.items():
            point = point.field(f"call_{greek}", value)

        write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=point)
        logger.info('Data sent to InfluxDB')
    except Exception as e:
        logger.error(f"Failed to save to InfluxDB: {e}")
        raise


def consume_messages(consumer, topics):
    cached_message = load_cached_message()
    if cached_message:
        logger.info('Loaded cached message from file')
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
                    
                    if is_first_message_of_the_day(message_value):
                        save_message_to_file(message_value)
                        cached_message = message_value
                        logger.info('Saved first message of the day')
                    
                    # Use cached_message for calculations with the new message
                    if cached_message:
                        # Perform your calculations here
                        live_chain_list = json.loads(message_value)  # Assuming message_value is a JSON string
                        static_chain = json.loads(cached_message)  # Assuming cached_message is a JSON string

                        try:

                            sum_differences_before, sum_differences_after, timestampEpochSec = compute_differences(
                                live_chain_list, static_chain)
                            
                            send_to_influxdb(sum_differences_before, sum_differences_after, timestampEpochSec)

                            # Commit the message offset to mark it as processed
                            consumer.commit(asynchronous=False)
                            print(f"Committed message offset: {msg.offset()} for partition: {msg.partition()}")
                        except Exception as e:
                            logger.error('Error during processing: %s', e)
                            # Continue processing further messages
                            continue

                    
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
            consume_messages(consumer, ['topic_raw_options'])
        except Exception as e:
            logger.critical('Fatal error: %s', e)
            time.sleep(10)  # Wait before restarting the consumer
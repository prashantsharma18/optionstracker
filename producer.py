import json
import os
from confluent_kafka import Producer

# Kafka configuration
KAFKA_BROKER = 'localhost:9092'
KAFKA_TOPIC = 'topic_raw_options'

# JSON file path
JSON_FILE_PATH = '.data/256265-2024-09-26.json'

def read_json_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}]')

def main():
    # Check if the JSON file exists
    if not os.path.exists(JSON_FILE_PATH):
        print(f"File not found: {JSON_FILE_PATH}")
        return

    # Read JSON data from file
    data = read_json_file(JSON_FILE_PATH)

    # Create Kafka producer
    producer = Producer({'bootstrap.servers': KAFKA_BROKER})

    # Send each object to Kafka
    for obj in data:
        # Convert the object to a JSON string
        message = json.dumps(obj)
        
        # Send the message to Kafka
        producer.produce(KAFKA_TOPIC, message, callback=delivery_report)
        
        # Poll to handle delivery reports (callbacks)
        producer.poll(0)

    # Wait for any outstanding messages to be delivered and delivery reports to be received
    producer.flush()

if __name__ == "__main__":
    main()
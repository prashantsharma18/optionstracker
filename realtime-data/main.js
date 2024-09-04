const WebSocket = require('ws');
const { Kafka } = require("@confluentinc/kafka-javascript").KafkaJS;
const lib = require('./lib.js');

// Replace 'ws://your-websocket-server-url' with the actual WebSocket server URL
const serverUrl = 'https://wsrelay.sensibull.com/broker/1?consumerType=platform_pro';

const customHeaders = {
    'Accept-Encoding': 'gzip, deflate',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Origin': 'https://web.sensibull.com'
};

// Kafka producer configuration
const kafka = new Kafka({
    kafkaJS: {
        brokers: ['broker:29092'], // Replace with your Kafka brokers
        ssl: false,
    }
    
});

const producer = kafka.producer();

async function sendMessageToKafka(topic, message) {
    try {
        await producer.send({
            topic,
            messages: [{ value: message }],
        });
        console.log('Message sent to Kafka successfully');
    } catch (err) {
        console.error('Error sending message to Kafka:', err);
    }
}

function removeUnwantedNodes(obj) {
    if (typeof obj === 'object' && obj !== null) {
        for (const key in obj) {
            if (key === 'CE' || key === 'PE') {
                delete obj[key];
            } else {
                removeUnwantedNodes(obj[key]);
            }
        }
    }
}

async function connectWebSocket(expiry) {
    const ws = new WebSocket(serverUrl, {
        headers: customHeaders
    });

    ws.on('open', () => {
        console.log('Connected to the WebSocket server');

        let scrips = [];

        const expiries = lib.expiries();

        lib.instruments().forEach(i => {
            scrips.push(
                { "underlying": i, "expiry": expiry },
            );
        });

        let message = {
            "msgCommand": "subscribe", 
            "dataSource": "option-chain", 
            "brokerId": 1, 
            "tokens": [], 
            "underlyingExpiry": scrips,
            "uniqueId": ""
        };

        scrips = scrips.map(script=>script.underlying);
        let msg = { "msgCommand": "subscribe", "dataSource": "underlying-stats", "brokerId": 1, "tokens": scrips, "underlyingExpiry": [], "uniqueId": "" };

        msg = JSON.stringify(msg);
        ws.send(msg);

        msg = { "msgCommand": "subscribe", "dataSource": "quote-binary", "brokerId": 1, "tokens": scrips, "underlyingExpiry": [], "uniqueId": "" };
        msg = JSON.stringify(msg);
        ws.send(msg);

        ws.send(JSON.stringify(message));
    });

    ws.on('message', async (data) => {
        let message = lib.decodeData(data);

        if (message && message.token=="256265") {

            // Remove "CE" and "PE" nodes
            removeUnwantedNodes(message);

            // Convert the message to string and send it to Kafka
            const kafkaMessage = JSON.stringify(message);
            await sendMessageToKafka('topic_raw_options', kafkaMessage);  // Replace with your Kafka topic
    }

    });

    ws.on('close', () => {
        console.log('Connection closed');
    });

    ws.on('error', (error) => {
        console.error(`WebSocket error: ${error.message}`);
    });
}

(async () => {
    // Connect the Kafka producer once
    await producer.connect();

    // Get the expiries from lib
    let expiries = lib.expiries();
    expiries = [expiries.shift()]; // Modify as needed

    for (const expiry of expiries) {
        connectWebSocket(expiry);  // Connect to WebSocket for each expiry
    }

    // Properly disconnect the producer when needed (e.g., on process exit)
    process.on('exit', async () => {
        await producer.disconnect();
    });
})();

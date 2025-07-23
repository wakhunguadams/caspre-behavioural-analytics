from kafka import KafkaProducer, KafkaConsumer
import json
import asyncio
from app.core.config import settings

producer: KafkaProducer = None

async def get_kafka_producer():
    """Initializes and returns a Kafka producer, making it available globally."""
    global producer
    if producer is None:
        producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=5, # Number of retries for sending message
            acks='all' # Require all in-sync replicas to acknowledge the message
        )
        print("Kafka Producer initialized.")
    return producer

async def close_kafka_producer():
    """Closes the Kafka producer connection."""
    global producer
    if producer:
        producer.close()
        print("Kafka Producer closed.")

async def send_message_to_kafka(topic: str, message: dict):
    """Sends a message to a Kafka topic asynchronously."""
    prod = await get_kafka_producer()
    # future = prod.send(topic, message) # .send is not async
    # Use asyncio.to_thread for blocking KafkaProducer.send()
    future = await asyncio.to_thread(prod.send, topic, message)
    try:
        record_metadata = await asyncio.to_thread(future.get, timeout=10)
        print(f"Message sent to topic: {record_metadata.topic}, partition: {record_metadata.partition}, offset: {record_metadata.offset}")
    except Exception as e:
        print(f"Failed to send message to Kafka: {e}")
        # In a real system, you might log this error more persistently or alert
        raise

# Consumer part - typically a separate worker process or background task in main
# This is NOT part of the FastAPI request-response cycle but a separate listener.
async def consume_messages_from_kafka(topic: str, process_func):
    """
    Kafka consumer function. This would run in a separate worker process or as
    a background task managed by something like Celery/Huey, or a dedicated consumer microservice.
    """
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
        auto_offset_reset='earliest', # Start reading from the beginning if no offset is committed
        enable_auto_commit=True, # Automatically commit offsets
        group_id='behavioral-analytics-processing-group', # Consumer group ID
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    print(f"Kafka Consumer started for topic: {topic}")
    try:
        for message in consumer:
            print(f"Received message: {message.value} on {message.topic}:{message.partition}:{message.offset}")
            await process_func(message.value)
    except Exception as e:
        print(f"Kafka consumer error: {e}")
    finally:
        consumer.close()
        print("Kafka Consumer closed.")
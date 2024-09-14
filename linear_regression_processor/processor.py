import os
import time
from datetime import datetime, timedelta
import sys
import logging
import debugpy
import influxdb_client, os, time
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


# Allow other computers to attach to debugpy at this IP address and port.
debugpy.listen(("0.0.0.0", 5679))
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
influxdb_token = "NZ85_mYv4-f_Fm8OGHyinRY4oOlsUXyHt0uCU0TxVI9IYUcjFwX9jpIYbJjc_qM-oHs48FZ7RERV_E7HO1gpaw=="
influxdb_org = "options"
influxdb_bucket = "nifty"

client = influxdb_client.InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

def get_time_range(date_str=None):
    """
    Returns the start and end times for the given date.
    If date_str is None, use the current system date.
    """
    if date_str:
        # Parse the provided date
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        # Use the current date
        date = datetime.utcnow().date()

    logger.info(f"Calculating time range for date: {date}")
    # Set start time to 9:16 AM and end time to 3:30 PM
    start_time = datetime.combine(date, datetime.strptime("09:16", "%H:%M").time())
    end_time = datetime.combine(date, datetime.strptime("15:30", "%H:%M").time())

    logger.info(f"Start time: {start_time}, End time: {end_time}")

    # If the current time is before the start time or after the end time, adjust accordingly
    now = datetime.utcnow()
    if now < start_time:
        # If current time is before 9:16 AM, adjust to the previous day
        start_time -= timedelta(days=1)
    if now > end_time:
        end_time = now

    logger.info(f"Adjusted Start time: {start_time}, End time: {end_time}")
    # Return ISO 8601 formatted times
    return start_time.isoformat() + 'Z', end_time.isoformat() + 'Z'


def read_from_influxdb(date_str=None):
    try:
        logger.info(f"Reading data from InfluxDB for date: {date_str}")
        start_time_str, end_time_str = get_time_range(date_str)

        logger.info(f"Start time: {start_time_str}, End time: {end_time_str}")

        # Define the Flux query with the calculated time range
        flux_query = f"""
        import "contrib/anaisdg/statsmodels"import "contrib/anaisdg/statsmodels"
        import "math"

        // Function to convert slope to degrees
        convertSlopeToAngle = (slope) => math.atan(x: slope) * 180.0 / math.pi

        // Query for call vega angle
        call_vega_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "call_vega")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Vega Call",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        // Query for put vega angle
        put_vega_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "put_vega")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Vega Put",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        // Query for put vega angle
        call_iv_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "call_impliedVolatility")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "IV Call",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        put_iv_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "put_impliedVolatility")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "IV Put",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        call_delta_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "call_callDelta")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Delta Call",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        put_delta_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "put_putDelta")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Delta Put",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        call_theta_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "call_theta")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Theta Call",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        put_theta_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "put_theta")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Theta Put",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        call_gamma_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "call_gamma")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Gamma Call",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        put_gamma_angle = from(bucket: "nifty")
        |> range(start: 2024-09-09T03:49:00Z, stop: 2024-09-09T04:00:00Z)
        |> filter(fn: (r) => r["_measurement"] == "greeks_differences")
        |> filter(fn: (r) => r["_field"] == "put_gamma")
        |> statsmodels.linearRegression()
        |> map(fn: (r) => ({
            "title": "Gamma Put",
            _value: convertSlopeToAngle(slope: r.slope),
            _time: r._time
        }))
        |> last()  // Get the most recent slope value

        // Combine both queries into a single table
        combined_angles = union(tables: [call_vega_angle, put_vega_angle, call_iv_angle, put_iv_angle, call_delta_angle, put_delta_angle, call_theta_angle, put_theta_angle, call_gamma_angle, put_gamma_angle])
        |> yield(name: "combined_vega_angles")
        """
        logger.info(f"Executing Flux query: {flux_query}")
        tables = query_api.query(flux_query)
        logger.info(f"Query returned {len(tables)} tables")
        data = []
        for table in tables:
            for record in table.records:
                data.append(record.values)
        return data
    except Exception as e:
        logger.error(f"Failed to read data from InfluxDB: {e}")
        raise

def process_data(data):
    # Process and write results to InfluxDB
    measurement = "greeks_angles"
    # record _time in the way influxdb format in time
    point = Point(measurement).tag("title", data["title"]).field("angle", data["_value"]).time(data["_time"], WritePrecision.NS)
    
    try:
        write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=point) # Write the data to InfluxDB
        logger.info(f"Data written to InfluxDB: {point.to_line_protocol()}")
    except Exception as e:
        logger.error(f"Failed to save to InfluxDB: {e}")
        raise


if __name__ == '__main__':
    while True:
        try:
            # call the read_from_influxdb function and pass todays date
            logger
            data = read_from_influxdb("2024-09-09")
            for entry in data:
                process_data(entry)
            time.sleep(60)  # Wait before the next read
            logger.info("Data processing complete   ")
        except Exception as e:
            print(f'Error: {e}')
            time.sleep(10)  # Wait before retrying
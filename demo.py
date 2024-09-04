import requests
import pandas as pd

# Define the API URLs
DERIVATIVE_API_URL = "https://oxide.sensibull.com/v1/compute/cache/instrument_metacache/1"
GREEK_API_URL = "https://oxide.sensibull.com/v1/compute/cache/live_derivative_prices/256265"

# Define the headers for API calls
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "x-device-id": "aee76e45-d634-4cc1-a064-552fa8a11b6a",
    "referrer": "https://web.sensibull.com/",
}

# Define the expiry date you're interested in
EXPIRY_DATE = "2024-08-22"

def fetch_data(url):
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()  # Raises an error for HTTP status codes 4xx/5xx
    return response.json()

def filter_derivative_data(derivatives, expiry_date):
    if expiry_date in derivatives:
        return derivatives[expiry_date]["options"]
    else:
        return {}

def join_data(derivatives, greeks):
    # Flatten derivatives and create a DataFrame
    rows = []
    for strike, data in derivatives.items():
        for option_type, info in data.items():
            rows.append({
                "strike": strike,
                "option_type": option_type,
                "instrument_token": info["instrument_token"],
                "tradingsymbol": info["tradingsymbol"]
            })
    
    derivatives_df = pd.DataFrame(rows)
    
    # Flatten greeks and create a DataFrame
    greeks_rows = []
    for option in greeks:
        if option.get('greeks_with_iv'):
            greeks_rows.append({
                "instrument_token": option["token"],
                "theta": option["greeks_with_iv"].get("theta"),
                "delta": option["greeks_with_iv"].get("delta"),
                "gamma": option["greeks_with_iv"].get("gamma"),
                "vega": option["greeks_with_iv"].get("vega"),
                "iv": option["greeks_with_iv"].get("iv"),
            })
    
    greeks_df = pd.DataFrame(greeks_rows)
    
    # Merge the two DataFrames on the instrument_token
    merged_df = pd.merge(derivatives_df, greeks_df, on="instrument_token", how="left")
    
    return merged_df

def main():
    # Fetch data from APIs
    derivative_data = fetch_data(DERIVATIVE_API_URL)
    greek_data = fetch_data(GREEK_API_URL)
    
    # Filter derivative data for the specific expiry
    filtered_derivatives = filter_derivative_data(derivative_data["derivatives"]["NIFTY"]["derivatives"], EXPIRY_DATE)
    
    # Filter greek data for the specific expiry
    filtered_greeks = greek_data["data"]["per_expiry_data"][EXPIRY_DATE]["options"]
    
    # Join the data
    final_data = join_data(filtered_derivatives, filtered_greeks)
    
    # Display the joined data
    print(final_data)

if __name__ == "__main__":
    main()

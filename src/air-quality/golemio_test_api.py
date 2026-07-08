

import json
import os
import traceback
import httpx
from dotenv import load_dotenv
from utils.data_processor import process_air_quality_data

load_dotenv()

BASE_URL = "https://api.golemio.cz/"
AIR_QUALITY_ENDPOINT = "/v2/airqualitystations"
TOKEN = os.environ.get("GOLEMIO_API_TOKEN")

OUTPUT_FILE = "test_output.parquet"

if not TOKEN:
    raise ValueError("GOLEMIO_API_TOKEN environment variable is not set. Please set it in your .env file.")

headers = {
    "X-Access-Token": TOKEN,
    "Accept": "application/json"
}

print("🛰️ Connecting to Golemio API...")

with httpx.Client(timeout=30.0) as client:
    try:
        response = client.get(BASE_URL + AIR_QUALITY_ENDPOINT, headers=headers, params={"limit": 5})
    
        if response.status_code == 200:
            print("✅ Success! Raw JSON Data shape:")

            flat_df = process_air_quality_data(response.json())

            print("🚀 Clean and flat DataFrame:")
            print(flat_df)

            flat_df.write_parquet(OUTPUT_FILE)
            print(f"\n 💾 Test file '{OUTPUT_FILE}' is saved sucessfully!")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except httpx.ReadTimeout:
        print("❌ Error: Request timed out. Please check your network connection and try again.")
    except httpx.RequestError as e:
        print(f"❌ Error: An error occurred while requesting {e.request.url!r}. Details: {str(e)}")
    except Exception as e:
        print("\n🚨 DETAILED PIPELINE FAILURE REPORT 🚨")
        print("="*50)
        # This prints the EXACT file, function, and line number where the crash happened
        traceback.print_exc()
        print("="*50)
        
        # Print a tiny sample of the raw data payload that caused the crash for debugging
        print("\n🔍 Debugging Sample Data (First feature block):")
        features = response.json().get("features", [])
        if features:
            import pprint
            pprint.PrettyPrinter(depth=4).pprint(features[0])
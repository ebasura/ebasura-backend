# check_bin_fill_levels.py
from app.engine.PhilSMSClient import PhilSMSClient
from app.engine import db  
import statistics
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

async def check_bin_fill_levels():
    api_token = os.getenv('API_TOKEN')
    sender_id = os.getenv('SENDER_ID')
    sms_client = PhilSMSClient(token=api_token, sender_id=sender_id)

    # Retrieve alert threshold and recipient number from system_settings
    alert_threshold = int(db.fetch_one("SELECT setting_value FROM system_settings WHERE setting_name = 'alert_threshold';")['setting_value'])
    recipient_number = db.fetch_one("SELECT setting_value FROM system_settings WHERE setting_name = 'sms_receiver';")['setting_value']

    # Get unique bin and waste type combinations
    unique_bins_query = "SELECT DISTINCT bin_id, waste_type FROM bin_fill_levels;"
    unique_bins = db.fetch(unique_bins_query)

    for bin in unique_bins:
        bin_id = bin['bin_id']
        waste_type = bin['waste_type']

        # Query the last 50 fill levels for the specific bin_id and waste_type
        query = f"SELECT fill_level FROM bin_fill_levels WHERE bin_id = {bin_id} AND waste_type = {waste_type} ORDER BY record_id DESC LIMIT 50;"
        results = db.fetch(query)

        if not results:
            continue

        fill_levels = [record['fill_level'] for record in results]
        measured_depth = statistics.median(fill_levels)

        filled_height = 75 - measured_depth
        percentage_full = (filled_height / 75) * 100

        # Check for recent alerts (within the last hour) in waste_alerts
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_alert_query = """
            SELECT * FROM waste_alerts 
            WHERE bin_id = %s AND waste_type_id = %s AND timestamp >= %s
            ORDER BY timestamp DESC LIMIT 1;
        """
        recent_alert = db.fetch_one(recent_alert_query, (bin_id, waste_type, one_hour_ago))

        # Only proceed if no recent alert has been sent in the past hour
        if percentage_full > alert_threshold and not recent_alert:
            # Determine bin and waste type names
            if bin_id == 1 and waste_type == 1:
                bin_name = 'CAS'
                waste_type_name = 'Recyclable'
            elif bin_id == 2 and waste_type == 1:
                bin_name = 'CTE'
                waste_type_name = 'Recyclable'
            elif bin_id == 3 and waste_type == 1:
                bin_name = 'CBME'
                waste_type_name = 'Recyclable'
            elif bin_id == 1 and waste_type == 2:
                bin_name = 'CAS'
                waste_type_name = 'Non-Recyclable'
            elif bin_id == 2 and waste_type == 2:
                bin_name = 'CTE'
                waste_type_name = 'Non-Recyclable'
            elif bin_id == 3 and waste_type == 2:
                bin_name = 'CBME'
                waste_type_name = 'Non-Recyclable'
            else:
                bin_name = None
                waste_type_name = None

            if bin_name and waste_type_name:
                message_content = f'{bin_name} Bin, {waste_type_name} Bin is {alert_threshold}% full'

                sms_client.send_sms(recipient=recipient_number, message=message_content)

                # Log the alert in the waste_alerts table
                insert_query = """
                    INSERT INTO waste_alerts (bin_id, waste_type_id, message, timestamp) 
                    VALUES (%s, %s, %s, NOW());
                """
                db.execute(insert_query, (bin_id, waste_type, message_content))

                print(f"Alert sent for Bin {bin_name} ({waste_type_name}).")
        else:
            print(f"Bin {bin_id} (Waste Type {waste_type}): No alert sent, fill level at {percentage_full:.2f}% or recent alert found.")

# Example execution
# asyncio.run(check_bin_fill_levels())

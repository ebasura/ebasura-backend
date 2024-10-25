# check_bin_fill_levels.py
from app.engine.PhilSMSClient import PhilSMSClient
from app.engine import db
import statistics
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables from .env file
load_dotenv()

async def check_bin_fill_levels():
    api_token = os.getenv('API_TOKEN')
    sender_id = os.getenv('SENDER_ID')
    sms_client = PhilSMSClient(token=api_token, sender_id=sender_id)

    query = "SELECT record_id, bin_id, waste_type, timestamp, fill_level FROM bin_fill_levels ORDER BY record_id DESC LIMIT 50;"
    
    # Fetch data synchronously, without 'await'
    results = db.fetch(query)

    fill_levels = [record['fill_level'] for record in results]
    measured_depth = statistics.median(fill_levels)

    filled_height = 75 - measured_depth
    percentage_full = (filled_height / 75) * 100

    bin_id = results[0]['bin_id'] if results else None
    waste_type = results[0]['waste_type'] if results else None

    sent_notifications = os.getenv("SENT_NOTIFICATIONS", "").split(",")
    notification_key = f"{bin_id}_{waste_type}" if bin_id and waste_type else None

    if percentage_full > 90 and notification_key not in sent_notifications:
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
            message_content = f'{bin_name} Bin, {waste_type_name} Bin is 90% full'
            recipient_number = '+639568104939'

            await sms_client.send_sms(recipient=recipient_number, message=message_content)

            # Update sent notifications
            sent_notifications.append(notification_key)
            os.environ["SENT_NOTIFICATIONS"] = ",".join(sent_notifications)
    else:
        print("No bins are full yet")

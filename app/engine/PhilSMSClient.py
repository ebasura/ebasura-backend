import requests
import json

class PhilSMSClient:
    def __init__(self, token, sender_id):
        self.token = token
        self.sender_id = sender_id
        self.url = "https://app.philsms.com/api/v3/sms/send"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def send_sms(self, recipient, message):
        send_data = {
            'sender_id': self.sender_id,
            'recipient': recipient,
            'message': message
        }
        response = requests.post(self.url, headers=self.headers, data=json.dumps(send_data))
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == "success":
                print("Message was successfully delivered.")
                print(f"Message UID: {response_data['data']['uid']}")
                print(f"Cost: {response_data['data']['cost']}")
            else:
                print(f"Failed to send message: {response_data.get('message')}")
        else:
            print(f"HTTP Error: {response.status_code}")
            print(response.text)

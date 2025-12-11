class SMSService:
    def send(self, to, message):
        print(f"SMS sent to {to}: {message}")
sms_client = SMSService()

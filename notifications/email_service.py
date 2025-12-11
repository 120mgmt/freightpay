class EmailService:
    def send(self, to, subject, body):
        print(f"Email sent to {to}: {subject}")
email_client = EmailService()

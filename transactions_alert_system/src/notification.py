import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from .models import AnomalyBase


class NotificationService:
    def __init__(self):
        # In production, these would be environment variables
        self.smtp_host = "smtp.gmail.com"
        self.smtp_port = 587
        self.smtp_user = os.getenv("SMTP_USER", "your-email@gmail.com")
        self.smtp_pass = os.getenv("SMTP_PASS", "your-app-password")
        self.recipients = os.getenv("ALERT_RECIPIENTS", "team@company.com").split(",")

    def send_alert(self, anomalies: list[AnomalyBase]):
        if not anomalies:
            return

        # Group anomalies by level
        critical = [a for a in anomalies if a.level == "CRITICAL"]
        warnings = [a for a in anomalies if a.level == "WARNING"]

        # Create message
        subject = f"Transaction Anomalies Detected - {len(critical)} Critical, {len(warnings)} Warnings"
        body = self._format_alert_message(critical, warnings)

        # Send email
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = ", ".join(self.recipients)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
        except Exception as e:
            print(f"Failed to send alert: {str(e)}")

    def _format_alert_message(
        self,
        critical: list[AnomalyBase],
        warnings: list[AnomalyBase],
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"""
        Transaction Anomaly Alert
        Generated at: {now}

        {"=" * 50}
        Critical Anomalies: {len(critical)}
        {"=" * 50}
        """

        for anomaly in critical:
            message += f"""
            Time: {anomaly.transaction.time}
            Status: {anomaly.transaction.status}
            Count: {anomaly.transaction.count}
            Score: {anomaly.score:.2f}
            Reason: {anomaly.message}
            """

        if warnings:
            message += f"""
            {"=" * 50}
            Warnings: {len(warnings)}
            {"=" * 50}
            """

            for anomaly in warnings:
                message += f"""
                Time: {anomaly.transaction.time}
                Status: {anomaly.transaction.status}
                Count: {anomaly.transaction.count}
                Score: {anomaly.score:.2f}
                Reason: {anomaly.message}
                """

        return message

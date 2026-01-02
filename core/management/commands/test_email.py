# test_email.py

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = "Test email configuration by sending a test email"

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            type=str,
            help="Email address to send test email to",
        )

    def handle(self, *args, **options):
        recipient = options["recipient"]

        self.stdout.write(f"Sending test email to: {recipient}")
        self.stdout.write(f"Using SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"TLS: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"SSL: {settings.EMAIL_USE_SSL}")

        try:
            send_mail(
                subject="Test Email from memoria.uy",
                message="This is a test email from memoria.uy. If you receive this, your SMTP configuration is working correctly!",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Email sent successfully to {recipient}"
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to send email: {str(e)}")
            )
            raise

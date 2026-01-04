import base64
import logging
from email.mime.base import MIMEBase
from typing import Iterable, List

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Send emails using the Resend HTTP API.

    This backend avoids SMTP networking requirements that can be blocked on some
    hosting providers.
    """

    def __init__(self, fail_silently: bool = False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "RESEND_API_KEY", None)
        self.api_url = getattr(
            settings, "RESEND_API_URL", "https://api.resend.com/emails"
        )

    def send_messages(self, email_messages: Iterable[EmailMessage] | None) -> int:
        if not email_messages:
            return 0

        if not self.api_key:
            message = "RESEND_API_KEY is not configured"
            logger.error(message)
            if self.fail_silently:
                return 0
            raise ValueError(message)

        sent_count = 0
        for message in email_messages:
            try:
                self._send(message)
                sent_count += 1
            except Exception:
                logger.exception("Failed to send email via Resend")
                if not self.fail_silently:
                    raise

        return sent_count

    def _send(self, message: EmailMessage) -> None:
        payload = self._build_payload(message)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

    def _build_payload(self, message: EmailMessage) -> dict:
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject or "",
        }

        if message.body:
            payload["text"] = message.body

        html_body = self._get_html_body(message)
        if html_body:
            payload["html"] = html_body

        if message.cc:
            payload["cc"] = list(message.cc)

        if message.bcc:
            payload["bcc"] = list(message.bcc)

        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        attachments = self._serialize_attachments(message.attachments)
        if attachments:
            payload["attachments"] = attachments

        return payload

    @staticmethod
    def _get_html_body(message: EmailMessage) -> str | None:
        for content, mime in getattr(message, "alternatives", []):
            if mime == "text/html":
                return content
        return None

    @staticmethod
    def _serialize_attachments(attachments: List) -> list:
        serialized = []
        for attachment in attachments:
            if isinstance(attachment, MIMEBase):
                content = attachment.get_payload(decode=True)
                mime_type = attachment.get_content_type()
                filename = attachment.get_filename()
            else:
                if len(attachment) == 3:
                    filename, content, mime_type = attachment
                elif len(attachment) == 2:
                    filename, content = attachment
                    mime_type = "application/octet-stream"
                else:
                    logger.warning(
                        "Skipping attachment with unexpected format: %s", attachment
                    )
                    continue

            if isinstance(content, str):
                content = content.encode()

            encoded_content = base64.b64encode(content).decode()
            serialized.append(
                {
                    "filename": filename,
                    "content": encoded_content,
                    "content_type": mime_type,
                }
            )
        return serialized

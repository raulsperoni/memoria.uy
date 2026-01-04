import pytest
from django.core import mail
from django.core.mail import EmailMessage

from core.email_backends.resend import ResendEmailBackend


def test_send_messages_with_resend(monkeypatch, settings):
    settings.RESEND_API_KEY = "test-key"
    backend = ResendEmailBackend()

    sent_payloads = []

    def fake_post(url, json, headers, timeout):
        sent_payloads.append({"url": url, "json": json, "headers": headers})

        class Response:
            status_code = 200

            @staticmethod
            def raise_for_status():
                return None

        return Response()

    monkeypatch.setattr("core.email_backends.resend.requests.post", fake_post)

    message = EmailMessage(
        subject="Hello",
        body="Plain body",
        from_email="sender@example.com",
        to=["dest@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
        reply_to=["reply@example.com"],
    )
    message.attach("hello.txt", "hi", "text/plain")

    assert backend.send_messages([message]) == 1
    assert len(sent_payloads) == 1
    payload = sent_payloads[0]["json"]
    assert payload["from"] == "sender@example.com"
    assert payload["to"] == ["dest@example.com"]
    assert payload["cc"] == ["cc@example.com"]
    assert payload["bcc"] == ["bcc@example.com"]
    assert payload["reply_to"] == ["reply@example.com"]
    assert payload["attachments"][0]["filename"] == "hello.txt"
    assert payload["attachments"][0]["content_type"] == "text/plain"
    assert payload["subject"] == "Hello"
    assert payload["text"] == "Plain body"


def test_missing_api_key_raises_error(settings):
    settings.RESEND_API_KEY = ""
    backend = ResendEmailBackend()

    with pytest.raises(ValueError):
        backend.send_messages([mail.EmailMessage(to=["dest@example.com"])])

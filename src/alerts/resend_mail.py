import os
import resend

resend.api_key = os.environ["RESEND_API_KEY"]


def send_email(subject: str, html: str):

    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": [os.environ["EMAIL_TO"]],
        "subject": subject,
        "html": html,
    })

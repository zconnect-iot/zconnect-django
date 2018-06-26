import logging

from django.core.mail import EmailMessage
from phonenumbers import PhoneNumberFormat, format_number
from sendsms.message import SmsMessage

logger = logging.getLogger(__name__)

def send_email(recipients, subject, template_id, substitutions):
    """
    Send an email to one or more recipients.
    """
    for recipient in recipients:
        logger.debug("Sending email to: %s", recipient)
        email = EmailMessage(
            to=[
                {
                    "address": recipient.email,
                    "substitution_data": substitutions
                }
            ],
            subject=subject,
        )
        email.template = template_id
        email.send()


def send_sms(recipients, body, from_phone="ZConnect"):
    """ Send an sms message to a set of users

    Args:
        recipients (list of zconnect.modesl.User): A list of users who should recieve
            this message
        body (str): The message content. Should be short!
        from_phone (str, optional): Either a phone number or up-to 11 Alphanumeric chars.

    Returns:
        None: This function fails silently

    Raises:
        django.core.exceptions.ImproperlyConfigured - when an SMS backend is not properly
            configured.

    """
    numbers = [format_number(recipient.phone_number, PhoneNumberFormat.INTERNATIONAL) \
                for recipient in recipients if recipient.phone_number]
    logger.debug("Sending SMS to: %s", numbers)
    sms = SmsMessage(
            to= numbers,
            body=body,
            from_phone=from_phone,
        )
    sms.send()

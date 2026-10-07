import os
import smtplib
import hashlib
import hmac
import json
from datetime import datetime
from email.message import EmailMessage

import requests

from database import get_connection


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def env_bool(name, default=False):

    value = os.getenv(
        name,
        str(default)
    ).strip().lower()

    return value in (
        "1",
        "true",
        "yes",
        "on"
    )


# ============================================================
# LOG NOTIFICATION
# ============================================================

def log_notification(
    record_id,
    channel,
    status,
    message
):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO notification_logs
        (
            record_id,
            channel,
            status,
            message,
            created_at
        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            record_id,
            channel,
            status,
            message,
            datetime.now().isoformat(
                timespec="seconds"
            )
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# LOG AUTOMATION
# ============================================================

def log_automation(
    record_id,
    action,
    status,
    message
):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO automation_logs
        (
            record_id,
            action,
            status,
            message,
            created_at
        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            record_id,
            action,
            status,
            message,
            datetime.now().isoformat(
                timespec="seconds"
            )
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# GMAIL
# ============================================================

def send_email(
    record,
    subject,
    body
):

    email = record["customer_email"]

    if not email:

        return False, "Customer email is empty."


    sender = os.getenv(
        "GMAIL_SENDER_EMAIL",
        ""
    ).strip()

    app_password = os.getenv(
        "GMAIL_APP_PASSWORD",
        ""
    ).strip()


    if not sender or not app_password:

        return False, (
            "Gmail is not configured. "
            "Add GMAIL_SENDER_EMAIL and "
            "GMAIL_APP_PASSWORD to .env."
        )


    message = EmailMessage()

    message["Subject"] = subject

    message["From"] = sender

    message["To"] = email

    message.set_content(body)


    try:

        with smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=30
        ) as server:

            server.starttls()

            server.login(
                sender,
                app_password
            )

            server.send_message(
                message
            )


        return True, "Email sent successfully."


    except Exception as error:

        return False, str(error)


# ============================================================
# WHATSAPP - META CLOUD API
# ============================================================

def send_whatsapp(
    record,
    template_parameters
):

    mobile = record["customer_mobile"]

    if not mobile:

        return False, "Customer mobile number is empty."


    token = os.getenv(
        "WHATSAPP_ACCESS_TOKEN",
        ""
    ).strip()

    phone_number_id = os.getenv(
        "WHATSAPP_PHONE_NUMBER_ID",
        ""
    ).strip()

    template_name = os.getenv(
        "WHATSAPP_TEMPLATE_NAME",
        ""
    ).strip()

    language = os.getenv(
        "WHATSAPP_TEMPLATE_LANGUAGE",
        "en_US"
    ).strip()


    if not token or not phone_number_id:

        return False, (
            "WhatsApp is not configured."
        )


    if not template_name:

        return False, (
            "WhatsApp template name is missing."
        )


    mobile = mobile.replace(
        " ",
        ""
    ).replace(
        "-",
        ""
    )


    if mobile.startswith("+"):

        mobile = mobile[1:]


    url = (
        "https://graph.facebook.com/v23.0/"
        + phone_number_id
        + "/messages"
    )


    parameters = []

    for value in template_parameters:

        parameters.append(
            {
                "type": "text",
                "text": str(value)
            }
        )


    payload = {

        "messaging_product": "whatsapp",

        "to": mobile,

        "type": "template",

        "template": {

            "name": template_name,

            "language": {
                "code": language
            },

            "components": [

                {
                    "type": "body",

                    "parameters": parameters
                }
            ]
        }
    }


    headers = {

        "Authorization": (
            "Bearer "
            + token
        ),

        "Content-Type":
            "application/json"
    }


    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )


        if response.status_code >= 400:

            return False, (
                response.text
            )


        return True, (
            "WhatsApp message sent."
        )


    except Exception as error:

        return False, str(error)


# ============================================================
# SMS
# ============================================================

def send_sms(
    record,
    message
):

    """
    SMS provider is intentionally left configurable.

    You have selected SMS for the project,
    but no SMS provider has been selected yet.

    Therefore this function does NOT pretend that
    an SMS was sent.

    Once a provider such as an Indian transactional
    SMS service is selected, connect its API here.
    """

    return False, (
        "SMS provider is not configured yet."
    )


# ============================================================
# CREATE RAZORPAY PAYMENT LINK
# ============================================================

def create_razorpay_payment_link(
    record
):

    key_id = os.getenv(
        "RAZORPAY_KEY_ID",
        ""
    ).strip()

    key_secret = os.getenv(
        "RAZORPAY_KEY_SECRET",
        ""
    ).strip()


    if not key_id or not key_secret:

        return False, (
            "Razorpay is not configured."
        ), None, None


    amount = float(
        record["payable_amount"]
        or 0
    )


    if amount <= 0:

        return False, (
            "No payable amount."
        ), None, None


    amount_paise = int(
        round(
            amount * 100
        )
    )


    reference_id = (
        "NACH-"
        + str(record["id"])
    )


    payload = {

        "amount":
            amount_paise,

        "currency":
            "INR",

        "accept_partial":
            False,

        "reference_id":
            reference_id,

        "description":
            (
                "NACH return recovery - "
                + str(record["customer_name"])
            ),

        "customer": {

            "name":
                record["customer_name"],

            "email":
                record["customer_email"]
                or "",

            "contact":
                record["customer_mobile"]
                or ""
        },

        "notify": {

            "email":
                bool(record["customer_email"]),

            "sms":
                False
        },

        "reminder_enable":
            True,

        "notes": {

            "nach_record_id":
                str(record["id"]),

            "mandate_number":
                str(record["mandate_number"])
        }
    }


    try:

        response = requests.post(

            "https://api.razorpay.com/v1/payment_links",

            auth=(
                key_id,
                key_secret
            ),

            json=payload,

            timeout=30
        )


        data = response.json()


        if response.status_code >= 400:

            return False, (
                data.get(
                    "error",
                    {}
                ).get(
                    "description",
                    response.text
                )
            ), None, None


        payment_link_id = data.get(
            "id",
            ""
        )

        short_url = data.get(
            "short_url",
            ""
        )


        return True, (
            "Razorpay Payment Link created."
        ), payment_link_id, short_url


    except Exception as error:

        return False, str(error), None, None


# ============================================================
# SAVE PAYMENT LINK
# ============================================================

def save_payment_link(
    record_id,
    payment_link_id,
    payment_link
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE nach_returns

        SET
            payment_link = ?,
            payment_link_id = ?,
            payment_status = 'Link Created'

        WHERE id = ?
        """,
        (
            payment_link,
            payment_link_id,
            record_id
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# GET RECORD
# ============================================================

def get_record(record_id):

    connection = get_connection()

    record = connection.execute(
        """
        SELECT *
        FROM nach_returns

        WHERE id = ?

        LIMIT 1
        """,
        (
            record_id,
        )
    ).fetchone()

    connection.close()

    return record


# ============================================================
# SEND NOTICE THROUGH AVAILABLE CHANNELS
# ============================================================

def send_customer_notice(
    record_id
):

    record = get_record(
        record_id
    )


    if not record:

        return {
            "email": False,
            "whatsapp": False,
            "sms": False
        }


    customer_name = record["customer_name"]

    amount = float(
        record["payable_amount"]
        or record["amount"]
        or 0
    )


    payment_link = (
        record["payment_link"]
        or "Not generated yet."
    )


    subject = (
        "NACH Return Notice - "
        + str(customer_name)
    )


    body = f"""
Dear {customer_name},

Your NACH transaction has been returned.

Return Reason:
{record["return_reason"]}

Return Code:
{record["return_code"]}

Return Amount:
₹{amount:,.2f}

Return Date:
{record["return_date"]}

Payment Link:
{payment_link}

Please complete the required payment or contact the concerned banking/loan service team.

Regards,
NACH Return Tracker
Banking Operations
"""


    result = {}


    # ========================================================
    # EMAIL
    # ========================================================

    email_ok, email_message = send_email(
        record,
        subject,
        body
    )


    result["email"] = email_ok

    log_notification(
        record_id,
        "EMAIL",
        "Sent" if email_ok else "Failed",
        email_message
    )


    # ========================================================
    # WHATSAPP
    # ========================================================

    whatsapp_ok, whatsapp_message = send_whatsapp(
        record,
        [
            customer_name,
            record["return_code"],
            record["return_reason"],
            f"₹{amount:,.2f}",
            payment_link
        ]
    )


    result["whatsapp"] = whatsapp_ok

    log_notification(
        record_id,
        "WHATSAPP",
        "Sent" if whatsapp_ok else "Failed",
        whatsapp_message
    )


    # ========================================================
    # SMS
    # ========================================================

    sms_ok, sms_message = send_sms(
        record,
        (
            "NACH return "
            + str(record["return_code"])
            + ". Amount ₹"
            + f"{amount:,.2f}"
            + ". Payment: "
            + payment_link
        )
    )


    result["sms"] = sms_ok

    log_notification(
        record_id,
        "SMS",
        "Sent" if sms_ok else "Failed",
        sms_message
    )


    connection = get_connection()

    connection.execute(
        """
        UPDATE nach_returns

        SET
            email_status = ?,
            whatsapp_status = ?,
            sms_status = ?,
            notice_status = ?,
            last_notification_at = ?,
            notification_error = ?

        WHERE id = ?
        """,
        (
            "Sent" if email_ok else "Failed",
            "Sent" if whatsapp_ok else "Failed",
            "Sent" if sms_ok else "Failed",

            "Sent" if (
                email_ok
                or whatsapp_ok
                or sms_ok
            ) else "Failed",

            datetime.now().isoformat(
                timespec="seconds"
            ),

            (
                email_message
                if not email_ok
                else ""
            ),

            record_id
        )
    )

    connection.commit()

    connection.close()


    return result


# ============================================================
# VERIFY RAZORPAY WEBHOOK
# ============================================================

def verify_razorpay_webhook(
    raw_body,
    received_signature
):

    secret = os.getenv(
        "RAZORPAY_WEBHOOK_SECRET",
        ""
    ).strip()


    if not secret:

        return False


    expected_signature = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()


    return hmac.compare_digest(
        expected_signature,
        received_signature
    )


# ============================================================
# PROCESS PAYMENT WEBHOOK
# ============================================================

def process_razorpay_webhook(
    event_data
):

    event_name = event_data.get(
        "event",
        ""
    )


    payload = event_data.get(
        "payload",
        {}
    )


    payment_link_data = payload.get(
        "payment_link",
        {}
    ).get(
        "entity",
        {}
    )


    reference_id = payment_link_data.get(
        "reference_id",
        ""
    )


    if not reference_id.startswith(
        "NACH-"
    ):

        return False, (
            "No NACH reference found."
        )


    try:

        record_id = int(
            reference_id.replace(
                "NACH-",
                ""
            )
        )

    except ValueError:

        return False, (
            "Invalid NACH reference."
        )


    connection = get_connection()


    if event_name in (
        "payment_link.paid",
        "payment.captured"
    ):

        connection.execute(
            """
            UPDATE nach_returns

            SET
                payment_status = 'Paid',
                payment_paid_at = ?,
                status = 'Recovered'

            WHERE id = ?
            """,
            (
                datetime.now().isoformat(
                    timespec="seconds"
                ),
                record_id
            )
        )


    elif event_name == "payment_link.partially_paid":

        connection.execute(
            """
            UPDATE nach_returns

            SET
                payment_status = 'Partially Paid'

            WHERE id = ?
            """,
            (
                record_id,
            )
        )


    elif event_name == "payment_link.expired":

        connection.execute(
            """
            UPDATE nach_returns

            SET
                payment_status = 'Expired'

            WHERE id = ?
            """,
            (
                record_id,
            )
        )


    elif event_name == "payment_link.cancelled":

        connection.execute(
            """
            UPDATE nach_returns

            SET
                payment_status = 'Cancelled'

            WHERE id = ?
            """,
            (
                record_id,
            )
        )


    else:

        connection.close()

        return True, (
            "Webhook received but no DB "
            "change was required."
        )


    connection.commit()

    connection.close()


    return True, (
        "Payment status updated."
    )

    import os
import requests
import razorpay
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# RAZORPAY SETTINGS
# ============================================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")


def get_razorpay_client():
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise Exception(
            "Razorpay credentials are missing in .env"
        )

    return razorpay.Client(
        auth=(
            RAZORPAY_KEY_ID,
            RAZORPAY_KEY_SECRET
        )
    )


# ============================================================
# CREATE RAZORPAY PAYMENT LINK
# ============================================================

def create_payment_link(
    amount,
    customer_name,
    customer_email="",
    customer_mobile="",
    description="NACH Return Payment"
):
    client = get_razorpay_client()

    amount_paise = int(
        round(float(amount) * 100)
    )

    data = {
        "amount": amount_paise,
        "currency": "INR",
        "description": description,
        "accept_partial": False,
        "reminder_enable": True
    }

    # Customer details
    customer = {}

    if customer_name:
        customer["name"] = customer_name

    if customer_email:
        customer["email"] = customer_email

    if customer_mobile:
        mobile = customer_mobile.strip()

        if mobile.startswith("+"):
            mobile = mobile[1:]

        if mobile.startswith("91") and len(mobile) == 12:
            customer["contact"] = "+" + mobile
        elif len(mobile) == 10:
            customer["contact"] = "+91" + mobile

    if customer:
        data["customer"] = customer

    payment_link = client.payment_link.create(data)

    return {
        "id": payment_link.get("id"),
        "short_url": payment_link.get("short_url"),
        "status": payment_link.get("status")
    }


# ============================================================
# WHATSAPP SETTINGS
# ============================================================

WHATSAPP_ACCESS_TOKEN = os.getenv(
    "WHATSAPP_ACCESS_TOKEN",
    ""
)

WHATSAPP_PHONE_NUMBER_ID = os.getenv(
    "WHATSAPP_PHONE_NUMBER_ID",
    ""
)

WHATSAPP_API_VERSION = os.getenv(
    "WHATSAPP_API_VERSION",
    "v23.0"
)


# ============================================================
# NORMALIZE MOBILE NUMBER
# ============================================================

def normalize_indian_mobile(mobile):
    if not mobile:
        return ""

    mobile = str(mobile).strip()

    mobile = mobile.replace(
        " ",
        ""
    ).replace(
        "-",
        ""
    )

    if mobile.startswith("+"):
        mobile = mobile[1:]

    if mobile.startswith("91") and len(mobile) == 12:
        return mobile

    if len(mobile) == 10:
        return "91" + mobile

    return mobile


# ============================================================
# SEND WHATSAPP TEMPLATE MESSAGE
# ============================================================

def send_whatsapp_template(
    mobile,
    template_name,
    parameters=None,
    language_code="en_US"
):
    if not WHATSAPP_ACCESS_TOKEN:
        raise Exception(
            "WhatsApp access token is missing in .env"
        )

    if not WHATSAPP_PHONE_NUMBER_ID:
        raise Exception(
            "WhatsApp phone number ID is missing in .env"
        )

    mobile = normalize_indian_mobile(
        mobile
    )

    if not mobile:
        raise Exception(
            "Customer mobile number is missing"
        )

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    components = []

    if parameters:
        body_parameters = []

        for value in parameters:
            body_parameters.append(
                {
                    "type": "text",
                    "text": str(value)
                }
            )

        components.append(
            {
                "type": "body",
                "parameters": body_parameters
            }
        )

    payload = {
        "messaging_product": "whatsapp",
        "to": mobile,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }

    if components:
        payload["template"]["components"] = components

    headers = {
        "Authorization":
            f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type":
            "application/json"
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30
    )

    if not response.ok:
        raise Exception(
            "WhatsApp API error: "
            + response.text
        )

    result = response.json()

    message_id = ""

    if result.get("messages"):
        message_id = result["messages"][0].get(
            "id",
            ""
        )

    return {
        "success": True,
        "message_id": message_id,
        "response": result
    }


# ============================================================
# PAYMENT LINK WHATSAPP MESSAGE
# ============================================================

def send_payment_link_whatsapp(
    mobile,
    customer_name,
    amount,
    payment_link
):
    template_name = os.getenv(
        "WHATSAPP_PAYMENT_TEMPLATE",
        "nach_payment_link"
    )

    return send_whatsapp_template(
        mobile=mobile,
        template_name=template_name,
        parameters=[
            customer_name,
            f"{float(amount):.2f}",
            payment_link
        ]
    )


# ============================================================
# 2-DAY ALERT WHATSAPP MESSAGE
# ============================================================

def send_debit_alert_whatsapp(
    mobile,
    customer_name,
    amount,
    debit_date
):
    template_name = os.getenv(
        "WHATSAPP_ALERT_TEMPLATE",
        "nach_debit_alert"
    )

    return send_whatsapp_template(
        mobile=mobile,
        template_name=template_name,
        parameters=[
            customer_name,
            f"{float(amount):.2f}",
            debit_date
        ]
    )
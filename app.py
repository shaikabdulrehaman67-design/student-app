from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from database import get_connection, create_database

from datetime import date

import csv
import io
from urllib.parse import quote


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = "college-project-secret-key"

create_database()


# ============================================================
# CONSTANTS
# ============================================================

BANKS = [
    "SBI",
    "HDFC",
    "ICICI",
    "AXIS",
    "Union Bank",
    "Canara Bank"
]

REASONS = {
    "R01": ("Insufficient Funds", 350),
    "R02": ("Account Closed", 500),
    "R03": ("Signature Mismatch", 350),
    "R04": ("Mandate Expired", 400)
}


# ============================================================
# LOGIN
# ============================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        ).strip()

        connection = get_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            AND password = ?
            """,
            (
                username,
                password
            )
        ).fetchone()

        connection.close()

        if user:

            session["username"] = username

            return redirect(
                url_for("dashboard")
            )

        return """
        <div style="
            max-width:500px;
            margin:80px auto;
            padding:35px;
            background:white;
            border-radius:18px;
            text-align:center;
            font-family:Arial;
            box-shadow:0 10px 30px rgba(0,0,0,.15);
        ">

            <h2 style="color:#5b2d70;">
                Invalid Login
            </h2>

            <p>
                Username or password is incorrect.
            </p>

            <a href="/"
               style="
               display:inline-block;
               padding:11px 20px;
               background:#5b2d70;
               color:white;
               text-decoration:none;
               border-radius:8px;
               ">
                Try Again
            </a>

        </div>
        """

    return render_template(
        "login.html"
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_connection()

    total_returns = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM nach_returns
        """
    ).fetchone()["count"]

    total_amount = connection.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        ) AS total
        FROM nach_returns
        """
    ).fetchone()["total"]

    total_charges = connection.execute(
        """
        SELECT COALESCE(
            SUM(bounce_charge),
            0
        ) AS total
        FROM nach_returns
        """
    ).fetchone()["total"]

    today_returns = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM nach_returns
        WHERE return_date = ?
        """,
        (
            date.today().isoformat(),
        )
    ).fetchone()["count"]

    connection.close()

    return render_template(
        "dashboard.html",
        total_returns=total_returns,
        total_amount=total_amount,
        total_charges=total_charges,
        today_returns=today_returns
    )


# ============================================================
# ADD RETURN
# ============================================================

@app.route(
    "/add-return",
    methods=["GET", "POST"]
)
def add_return():

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    error = ""

    if request.method == "POST":

        customer_name = request.form.get(
            "customer_name",
            ""
        ).strip()

        account_number = request.form.get(
            "account_number",
            ""
        ).strip()

        mandate_number = request.form.get(
            "mandate_number",
            ""
        ).strip().upper()

        amount_value = request.form.get(
            "amount",
            ""
        ).strip()

        bank_name = request.form.get(
            "bank_name",
            ""
        ).strip()

        return_code = request.form.get(
            "return_code",
            ""
        ).strip().upper()

        return_date = request.form.get(
            "return_date",
            ""
        ).strip()

        customer_email = request.form.get(
            "customer_email",
            ""
        ).strip()

        customer_mobile = request.form.get(
            "customer_mobile",
            ""
        ).strip()

        scheduled_debit_date = request.form.get(
            "scheduled_debit_date",
            ""
        ).strip()

        next_salary_date = request.form.get(
            "next_salary_date",
            ""
        ).strip()


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not customer_name:

            error = "Please enter Customer Name."

        elif not account_number:

            error = "Please enter Account Number."

        elif not mandate_number:

            error = "Please enter Mandate Number."

        elif not amount_value:

            error = "Please enter Return Amount."

        elif not bank_name:

            error = "Please select Bank Name."

        elif bank_name not in BANKS:

            error = "Invalid Bank Name."

        elif not return_code:

            error = "Please select Return Reason."

        elif return_code not in REASONS:

            error = "Please select a valid Return Reason."

        elif not return_date:

            error = "Please select Return Date."


        # ----------------------------------------------------
        # EMAIL VALIDATION
        # ----------------------------------------------------

        if not error and customer_email:

            if "@" not in customer_email:

                error = (
                    "Please enter a valid customer email."
                )


        # ----------------------------------------------------
        # MOBILE VALIDATION
        # ----------------------------------------------------

        if not error and customer_mobile:

            mobile_digits = "".join(
                c
                for c in customer_mobile
                if c.isdigit()
            )

            if len(mobile_digits) < 10:

                error = (
                    "Please enter a valid mobile number."
                )


        # ----------------------------------------------------
        # AMOUNT
        # ----------------------------------------------------

        amount = 0

        if not error:

            try:

                amount = float(
                    amount_value
                    .replace(",", "")
                    .replace("₹", "")
                    .replace("Rs.", "")
                    .replace("Rs", "")
                    .replace("INR", "")
                    .strip()
                )

                if amount <= 0:

                    error = (
                        "Amount must be greater than zero."
                    )

            except ValueError:

                error = (
                    "Please enter a valid amount."
                )


        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        if not error:

            return_reason, original_charge = REASONS[
                return_code
            ]

            # Signature mismatch = fee waived
            fee_waived = (
                1
                if return_code == "R03"
                else 0
            )

            bounce_charge = (
                0
                if fee_waived
                else original_charge
            )

            payable_amount = (
                amount + bounce_charge
            )

            mandate_status = "Active"

            account_debit_status = "Pending"

            # Account closed
            if return_code == "R02":

                mandate_status = "Stopped"

                account_debit_status = "Blocked"


            connection = get_connection()


            # ------------------------------------------------
            # DUPLICATE CHECK
            # ------------------------------------------------

            duplicate = connection.execute(
                """
                SELECT id
                FROM nach_returns
                WHERE UPPER(
                    TRIM(mandate_number)
                ) = ?

                AND return_date = ?

                LIMIT 1
                """,
                (
                    mandate_number,
                    return_date
                )
            ).fetchone()


            if duplicate:

                connection.close()

                error = (
                    "This mandate already has a return "
                    "record for the selected date."
                )

            else:

                connection.execute(
                    """
                    INSERT INTO nach_returns
                    (
                        customer_name,
                        account_number,
                        mandate_number,
                        amount,
                        bank_name,
                        return_code,
                        return_reason,
                        return_date,
                        bounce_charge,
                        status,

                        customer_email,
                        customer_mobile,
                        scheduled_debit_date,
                        next_salary_date,

                        payable_amount,
                        payment_status,
                        notice_status,
                        email_status,
                        whatsapp_status,
                        sms_status,
                        retry_status,
                        mandate_status,
                        account_debit_status,
                        fee_waived,
                        payment_link,
                        payment_link_id,
                        alert_sent_at,
                        retry_processed_at
                    )

                    VALUES
                    (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,

                    (
                        customer_name,
                        account_number,
                        mandate_number,
                        amount,
                        bank_name,
                        return_code,
                        return_reason,
                        return_date,
                        bounce_charge,
                        "Returned",

                        customer_email,
                        customer_mobile,
                        scheduled_debit_date,
                        next_salary_date,

                        payable_amount,
                        "Pending",
                        "Pending",
                        "Pending",
                        "Pending",
                        "Pending",
                        "Pending",

                        mandate_status,
                        account_debit_status,
                        fee_waived,

                        "",
                        "",
                        "",
                        ""
                    )
                )

                connection.commit()

                connection.close()

                flash(
                    "NACH Return saved successfully."
                )

                return redirect(
                    url_for("records")
                )


    return render_template(
        "add_return.html",
        error=error
    )


# ============================================================
# CSV IMPORT
# ============================================================

@app.route(
    "/import-csv",
    methods=["POST"]
)
def import_csv():

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    uploaded_file = request.files.get(
        "csv_file"
    )

    if (
        not uploaded_file
        or uploaded_file.filename == ""
    ):

        flash(
            "Please select a CSV file."
        )

        return redirect(
            url_for("add_return")
        )


    if not uploaded_file.filename.lower().endswith(
        ".csv"
    ):

        flash(
            "Only CSV files are allowed."
        )

        return redirect(
            url_for("add_return")
        )


    try:

        content = uploaded_file.read().decode(
            "utf-8-sig"
        )

        reader = csv.DictReader(
            io.StringIO(content)
        )

        connection = get_connection()

        imported = 0
        skipped = 0


        for row in reader:

            customer_name = (
                row.get("customer_name")
                or row.get("Customer Name")
                or ""
            ).strip()

            account_number = (
                row.get("account_number")
                or row.get("Account Number")
                or ""
            ).strip()

            mandate_number = (
                row.get("mandate_number")
                or row.get("Mandate Number")
                or ""
            ).strip().upper()

            amount_value = (
                row.get("amount")
                or row.get("Amount")
                or ""
            ).strip()

            bank_name = (
                row.get("bank_name")
                or row.get("Bank Name")
                or ""
            ).strip()

            return_code = (
                row.get("return_code")
                or row.get("Return Code")
                or ""
            ).strip().upper()

            return_date = (
                row.get("return_date")
                or row.get("Return Date")
                or ""
            ).strip()

            customer_email = (
                row.get("customer_email")
                or row.get("Customer Email")
                or row.get("email")
                or ""
            ).strip()

            customer_mobile = (
                row.get("customer_mobile")
                or row.get("Customer Mobile")
                or row.get("mobile")
                or ""
            ).strip()

            scheduled_debit_date = (
                row.get("scheduled_debit_date")
                or row.get("Scheduled Debit Date")
                or ""
            ).strip()

            next_salary_date = (
                row.get("next_salary_date")
                or row.get("Next Salary Date")
                or ""
            ).strip()


            if not all([
                customer_name,
                account_number,
                mandate_number,
                amount_value,
                bank_name,
                return_code,
                return_date
            ]):

                skipped += 1
                continue


            if bank_name not in BANKS:

                skipped += 1
                continue


            if return_code not in REASONS:

                skipped += 1
                continue


            try:

                amount = float(
                    amount_value
                    .replace(",", "")
                    .replace("₹", "")
                    .replace("Rs.", "")
                    .replace("Rs", "")
                    .replace("INR", "")
                    .strip()
                )

                if amount <= 0:

                    skipped += 1
                    continue

            except:

                skipped += 1
                continue


            return_reason, original_charge = REASONS[
                return_code
            ]


            fee_waived = (
                1
                if return_code == "R03"
                else 0
            )

            bounce_charge = (
                0
                if fee_waived
                else original_charge
            )

            payable_amount = (
                amount + bounce_charge
            )

            mandate_status = "Active"

            account_debit_status = "Pending"


            if return_code == "R02":

                mandate_status = "Stopped"

                account_debit_status = "Blocked"


            duplicate = connection.execute(
                """
                SELECT id
                FROM nach_returns
                WHERE UPPER(
                    TRIM(mandate_number)
                ) = ?

                AND return_date = ?

                LIMIT 1
                """,
                (
                    mandate_number,
                    return_date
                )
            ).fetchone()


            if duplicate:

                skipped += 1
                continue


            connection.execute(
                """
                INSERT INTO nach_returns
                (
                    customer_name,
                    account_number,
                    mandate_number,
                    amount,
                    bank_name,
                    return_code,
                    return_reason,
                    return_date,
                    bounce_charge,
                    status,

                    customer_email,
                    customer_mobile,
                    scheduled_debit_date,
                    next_salary_date,

                    payable_amount,
                    payment_status,
                    notice_status,
                    email_status,
                    whatsapp_status,
                    sms_status,
                    retry_status,
                    mandate_status,
                    account_debit_status,
                    fee_waived,
                    payment_link,
                    payment_link_id,
                    alert_sent_at,
                    retry_processed_at
                )

                VALUES
                (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,

                (
                    customer_name,
                    account_number,
                    mandate_number,
                    amount,
                    bank_name,
                    return_code,
                    return_reason,
                    return_date,
                    bounce_charge,
                    "Returned",

                    customer_email,
                    customer_mobile,
                    scheduled_debit_date,
                    next_salary_date,

                    payable_amount,
                    "Pending",
                    "Pending",
                    "Pending",
                    "Pending",
                    "Pending",
                    "Pending",

                    mandate_status,
                    account_debit_status,
                    fee_waived,

                    "",
                    "",
                    "",
                    ""
                )
            )

            imported += 1


        connection.commit()
        connection.close()


        flash(
            f"CSV Imported Successfully: "
            f"{imported} records. "
            f"Skipped: {skipped}."
        )


    except Exception as e:

        flash(
            "CSV Import Error: " + str(e)
        )


    return redirect(
        url_for("add_return")
    )


# ============================================================
# DELETE RECORD
# ============================================================

@app.route(
    "/delete-record/<int:record_id>",
    methods=["POST"]
)
def delete_record(record_id):

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM nach_returns
        WHERE id = ?
        """,
        (
            record_id,
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        url_for("records")
    )


# ============================================================
# RECORDS
# ============================================================

@app.route("/records")
def records():

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    search = request.args.get(
        "search",
        ""
    ).strip()

    bank = request.args.get(
        "bank",
        ""
    ).strip()

    connection = get_connection()

    query = """
        SELECT *
        FROM nach_returns
        WHERE 1 = 1
    """

    parameters = []

    if search:

        query += """
            AND
            (
                customer_name LIKE ?
                OR account_number LIKE ?
                OR mandate_number LIKE ?
            )
        """

        search_value = "%" + search + "%"

        parameters.extend([
            search_value,
            search_value,
            search_value
        ])


    if bank:

        query += """
            AND bank_name = ?
        """

        parameters.append(
            bank
        )


    query += """
        ORDER BY id DESC
    """


    records = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "records.html",
        records=records,
        search=search,
        bank=bank
    )


# ============================================================
# CUSTOMER NOTICES
# ============================================================

@app.route("/customer-notices")
def customer_notices():

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_connection()

    records = connection.execute(
        """
        SELECT *
        FROM nach_returns
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "customer_notices.html",
        records=records
    )


# ============================================================
# GENERATE NOTICE
# ============================================================

@app.route(
    "/generate-notice/<int:record_id>"
)
def generate_notice(record_id):

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_connection()

    record = connection.execute(
        """
        SELECT *
        FROM nach_returns
        WHERE id = ?
        """,
        (
            record_id,
        )
    ).fetchone()

    connection.close()

    if record is None:

        return "NACH record not found."

    return render_template(
        "notice.html",
        record=record
    )


# ============================================================
# HELPER: GET NACH RECORD
# ============================================================

def get_nach_record(record_id):

    connection = get_connection()

    record = connection.execute(
        """
        SELECT *
        FROM nach_returns
        WHERE id = ?
        """,
        (
            record_id,
        )
    ).fetchone()

    connection.close()

    return record


# ============================================================
# EMAIL NOTICE
# ============================================================

@app.route(
    "/email-notice/<int:record_id>"
)
def email_notice(record_id):

    if "username" not in session:

        return redirect(
            url_for("login")
        )


    record = get_nach_record(
        record_id
    )


    if record is None:

        flash(
            "NACH record not found."
        )

        return redirect(
            url_for("customer_notices")
        )


    # --------------------------------------------------------
    # USE SAVED CUSTOMER EMAIL FIRST
    # --------------------------------------------------------

    contact = (
        record["customer_email"]
        or ""
    ).strip()


    # If saved email does not exist,
    # use contact supplied by modal.

    if not contact:

        contact = request.args.get(
            "contact",
            ""
        ).strip()


    # Still no email -> return to notice page
    # and ask the user through modal.

    if not contact:

        flash(
            "Customer email is not saved. "
            "Please enter the email address."
        )

        return redirect(
            url_for("customer_notices")
        )


    # --------------------------------------------------------
    # CREATE EMAIL
    # --------------------------------------------------------

    subject = (
        "NACH Return Notice - "
        + record["mandate_number"]
    )


    message = f"""
Dear {record["customer_name"]},

This is a NACH Return Notice from the Banking Operations Department.

Customer Name: {record["customer_name"]}
Account Number: {record["account_number"]}
Mandate Number: {record["mandate_number"]}
Bank: {record["bank_name"]}
Return Amount: ₹{record["amount"]:.2f}
Return Reason: {record["return_reason"]}
Return Date: {record["return_date"]}
Bounce Charge: ₹{record["bounce_charge"]:.2f}

Please make the required payment or arrangement.

Payment Link:
Please use the payment link provided by the Banking Operations Department.

Regards,
Banking Operations Department
NACH Return Tracker
"""


    # --------------------------------------------------------
    # OPEN GMAIL COMPOSE
    # --------------------------------------------------------

    gmail_url = (
        "https://mail.google.com/mail/"
        "?view=cm"
        "&fs=1"
        "&tf=1"
        f"&to={quote(contact)}"
        f"&su={quote(subject)}"
        f"&body={quote(message)}"
    )


    # Update status

    connection = get_connection()

    connection.execute(
        """
        UPDATE nach_returns
        SET
            email_status = ?
        WHERE id = ?
        """,
        (
            "Opened",
            record_id
        )
    )

    connection.commit()

    connection.close()


    return redirect(
        gmail_url
    )


# ============================================================
# WHATSAPP NOTICE
# ============================================================

@app.route(
    "/whatsapp-notice/<int:record_id>"
)
def whatsapp_notice(record_id):

    if "username" not in session:

        return redirect(
            url_for("login")
        )


    record = get_nach_record(
        record_id
    )


    if record is None:

        flash(
            "NACH record not found."
        )

        return redirect(
            url_for("customer_notices")
        )


    # --------------------------------------------------------
    # USE SAVED MOBILE FIRST
    # --------------------------------------------------------

    contact = (
        record["customer_mobile"]
        or ""
    ).strip()


    # If no saved mobile, use modal contact.

    if not contact:

        contact = request.args.get(
            "contact",
            ""
        ).strip()


    if not contact:

        flash(
            "Customer mobile number is not saved. "
            "Please enter the mobile number."
        )

        return redirect(
            url_for("customer_notices")
        )


    digits = "".join(
        character
        for character in contact
        if character.isdigit()
    )


    # --------------------------------------------------------
    # INDIA NUMBER
    # --------------------------------------------------------

    if len(digits) == 10:

        digits = "91" + digits


    if len(digits) < 12:

        flash(
            "Please enter a valid WhatsApp mobile number."
        )

        return redirect(
            url_for("customer_notices")
        )


    # --------------------------------------------------------
    # WHATSAPP MESSAGE
    # --------------------------------------------------------

    message = f"""Dear {record["customer_name"]},

NACH Return Notice

Customer Name: {record["customer_name"]}
Account Number: {record["account_number"]}
Mandate Number: {record["mandate_number"]}
Bank: {record["bank_name"]}
Return Amount: ₹{record["amount"]:.2f}
Return Reason: {record["return_reason"]}
Return Date: {record["return_date"]}
Bounce Charge: ₹{record["bounce_charge"]:.2f}

Please make the required payment or arrangement.

Payment Link:
Please use the payment link provided by the Banking Operations Department.

Regards,
NACH Return Tracker
Banking Operations Department
"""


    whatsapp_url = (
        "https://wa.me/"
        + digits
        + "?text="
        + quote(message)
    )


    connection = get_connection()

    connection.execute(
        """
        UPDATE nach_returns
        SET
            whatsapp_status = ?
        WHERE id = ?
        """,
        (
            "Opened",
            record_id
        )
    )

    connection.commit()

    connection.close()


    return redirect(
        whatsapp_url
    )


# ============================================================
# REPORTS
# ============================================================

@app.route("/reports")
def reports():

    if "username" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_connection()

    total_returns = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM nach_returns
        """
    ).fetchone()["count"]

    total_amount = connection.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        ) AS total
        FROM nach_returns
        """
    ).fetchone()["total"]

    total_charges = connection.execute(
        """
        SELECT COALESCE(
            SUM(bounce_charge),
            0
        ) AS total
        FROM nach_returns
        """
    ).fetchone()["total"]

    today_returns = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM nach_returns
        WHERE return_date = ?
        """,
        (
            date.today().isoformat(),
        )
    ).fetchone()["count"]


    bank_report = connection.execute(
        """
        SELECT
            bank_name,
            COUNT(*) AS return_count,
            COALESCE(
                SUM(amount),
                0
            ) AS total_amount
        FROM nach_returns
        GROUP BY bank_name
        ORDER BY return_count DESC
        """
    ).fetchall()


    reason_report = connection.execute(
        """
        SELECT
            return_reason,
            COUNT(*) AS return_count
        FROM nach_returns
        GROUP BY return_reason
        ORDER BY return_count DESC
        """
    ).fetchall()


    connection.close()


    return render_template(
        "reports.html",
        total_returns=total_returns,
        total_amount=total_amount,
        total_charges=total_charges,
        today_returns=today_returns,
        bank_report=bank_report,
        reason_report=reason_report
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
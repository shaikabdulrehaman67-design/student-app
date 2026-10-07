import sqlite3
import os


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE_FOLDER = os.path.join(
    BASE_DIR,
    "database"
)

DATABASE_PATH = os.path.join(
    DATABASE_FOLDER,
    "nach_tracker.db"
)


# ============================================================
# CONNECTION
# ============================================================

def get_connection():

    os.makedirs(
        DATABASE_FOLDER,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# ADD COLUMN IF MISSING
# ============================================================

def add_column_if_missing(
    cursor,
    table_name,
    column_name,
    column_definition
):

    columns = cursor.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    existing_columns = [
        column["name"]
        for column in columns
    ]

    if column_name not in existing_columns:

        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_definition}
            """
        )


# ============================================================
# CREATE DATABASE
# ============================================================

def create_database():

    connection = get_connection()

    cursor = connection.cursor()


    # ========================================================
    # NACH RETURNS
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nach_returns
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            customer_name TEXT NOT NULL,

            account_number TEXT NOT NULL,

            mandate_number TEXT NOT NULL,

            amount REAL NOT NULL,

            bank_name TEXT NOT NULL,

            return_code TEXT NOT NULL,

            return_reason TEXT NOT NULL,

            return_date TEXT NOT NULL,

            bounce_charge REAL NOT NULL,

            status TEXT DEFAULT 'Returned'
        )
        """
    )


    # ========================================================
    # CUSTOMER CONTACT
    # ========================================================

    add_column_if_missing(
        cursor,
        "nach_returns",
        "customer_email",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "customer_mobile",
        "TEXT DEFAULT ''"
    )


    # ========================================================
    # SCHEDULE INFORMATION
    # ========================================================

    add_column_if_missing(
        cursor,
        "nach_returns",
        "scheduled_debit_date",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "next_salary_date",
        "TEXT DEFAULT ''"
    )


    # ========================================================
    # PAYMENT
    # ========================================================

    add_column_if_missing(
        cursor,
        "nach_returns",
        "payable_amount",
        "REAL DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "payment_status",
        "TEXT DEFAULT 'Pending'"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "payment_link",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "payment_link_id",
        "TEXT DEFAULT ''"
    )


    # ========================================================
    # NOTICE / COMMUNICATION
    # ========================================================

    add_column_if_missing(
        cursor,
        "nach_returns",
        "notice_status",
        "TEXT DEFAULT 'Pending'"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "email_status",
        "TEXT DEFAULT 'Pending'"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "whatsapp_status",
        "TEXT DEFAULT 'Pending'"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "sms_status",
        "TEXT DEFAULT 'Pending'"
    )


    # ========================================================
    # AUTOMATION
    # ========================================================

    add_column_if_missing(
        cursor,
        "nach_returns",
        "retry_status",
        "TEXT DEFAULT 'Pending'"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "mandate_status",
        "TEXT DEFAULT 'Active'"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "account_debit_status",
        "TEXT DEFAULT 'Pending'"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "fee_waived",
        "INTEGER DEFAULT 0"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "alert_sent_at",
        "TEXT DEFAULT ''"
    )

    add_column_if_missing(
        cursor,
        "nach_returns",
        "retry_processed_at",
        "TEXT DEFAULT ''"
    )


    # ========================================================
    # USERS
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT NOT NULL UNIQUE,

            password TEXT NOT NULL
        )
        """
    )


    # ========================================================
    # REASON CODES
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reason_codes
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            bank_name TEXT NOT NULL,

            return_code TEXT NOT NULL,

            return_reason TEXT NOT NULL,

            bounce_charge REAL NOT NULL
        )
        """
    )


    # ========================================================
    # LOGIN
    # ========================================================

    existing_user = cursor.execute(
        """
        SELECT id
        FROM users
        WHERE username = ?
        """,
        (
            "Abdul Rehman",
        )
    ).fetchone()


    if existing_user:

        cursor.execute(
            """
            UPDATE users

            SET password = ?

            WHERE username = ?
            """,
            (
                "Abdul 2005",
                "Abdul Rehman"
            )
        )

    else:

        cursor.execute(
            """
            INSERT INTO users
            (
                username,
                password
            )

            VALUES
            (?, ?)
            """,
            (
                "Abdul Rehman",
                "Abdul 2005"
            )
        )


    # ========================================================
    # REASONS
    # ========================================================

    reasons = [

        ("SBI", "R01", "Insufficient Funds", 350),
        ("SBI", "R02", "Account Closed", 500),
        ("SBI", "R03", "Signature Mismatch", 350),
        ("SBI", "R04", "Mandate Expired", 400),

        ("HDFC", "R01", "Insufficient Funds", 350),
        ("HDFC", "R02", "Account Closed", 500),
        ("HDFC", "R03", "Signature Mismatch", 350),
        ("HDFC", "R04", "Mandate Expired", 400),

        ("ICICI", "R01", "Insufficient Funds", 350),
        ("ICICI", "R02", "Account Closed", 500),
        ("ICICI", "R03", "Signature Mismatch", 350),
        ("ICICI", "R04", "Mandate Expired", 400),

        ("AXIS", "R01", "Insufficient Funds", 350),
        ("AXIS", "R02", "Account Closed", 500),
        ("AXIS", "R03", "Signature Mismatch", 350),
        ("AXIS", "R04", "Mandate Expired", 400),

        ("Union Bank", "R01", "Insufficient Funds", 350),
        ("Union Bank", "R02", "Account Closed", 500),
        ("Union Bank", "R03", "Signature Mismatch", 350),
        ("Union Bank", "R04", "Mandate Expired", 400),

        ("Canara Bank", "R01", "Insufficient Funds", 350),
        ("Canara Bank", "R02", "Account Closed", 500),
        ("Canara Bank", "R03", "Signature Mismatch", 350),
        ("Canara Bank", "R04", "Mandate Expired", 400)
    ]


    for (
        bank_name,
        return_code,
        return_reason,
        bounce_charge
    ) in reasons:

        existing = cursor.execute(
            """
            SELECT id
            FROM reason_codes

            WHERE bank_name = ?
            AND return_code = ?
            """,
            (
                bank_name,
                return_code
            )
        ).fetchone()


        if existing:

            cursor.execute(
                """
                UPDATE reason_codes

                SET
                    return_reason = ?,
                    bounce_charge = ?

                WHERE bank_name = ?
                AND return_code = ?
                """,
                (
                    return_reason,
                    bounce_charge,
                    bank_name,
                    return_code
                )
            )

        else:

            cursor.execute(
                """
                INSERT INTO reason_codes
                (
                    bank_name,
                    return_code,
                    return_reason,
                    bounce_charge
                )

                VALUES
                (?, ?, ?, ?)
                """,
                (
                    bank_name,
                    return_code,
                    return_reason,
                    bounce_charge
                )
            )


    # ========================================================
    # OLD RECORD FIX
    # ========================================================

    cursor.execute(
        """
        UPDATE nach_returns

        SET payable_amount =
            CASE

                WHEN payable_amount IS NULL
                OR payable_amount = 0

                THEN amount + bounce_charge

                ELSE payable_amount

            END

        WHERE
            payable_amount IS NULL
            OR payable_amount = 0
        """
    )


    # ========================================================
    # INDEXES
    # ========================================================

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_mandate_number

        ON nach_returns(mandate_number)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_return_date

        ON nach_returns(return_date)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_bank_name

        ON nach_returns(bank_name)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_customer_email

        ON nach_returns(customer_email)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_customer_mobile

        ON nach_returns(customer_mobile)
        """
    )


    connection.commit()

    connection.close()

    print(
        "Database created/migrated successfully!"
    )


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    create_database()
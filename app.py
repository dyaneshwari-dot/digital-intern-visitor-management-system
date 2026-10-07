from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_file
)

import mysql.connector
from mysql.connector import Error

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

from functools import wraps

from datetime import datetime, timedelta, date

import os

from openpyxl import Workbook


app = Flask(__name__)

app.secret_key = "change-this-secret-key"


# ---------------- DATABASE SETTINGS ----------------

DB_CONFIG = {
    "host": os.getenv("MYSQLHOST"),
    "port": int(os.getenv("MYSQLPORT", "3306")),
    "user": os.getenv("MYSQLUSER"),
    "password": os.getenv("MYSQLPASSWORD"),
    "database": os.getenv("MYSQLDATABASE")
}


SLOTS = [
    ("09:00", "10:00"),
    ("10:00", "11:00"),
    ("11:00", "12:00"),
    ("12:00", "13:00"),
    ("13:00", "14:00"),
    ("14:00", "15:00"),
    ("15:00", "16:00"),
]


# ---------------- PHOTO UPLOAD SETTINGS ----------------

UPLOAD_FOLDER = os.path.join(
    "static",
    "uploads",
    "attendance"
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ---------------- TIME FORMAT HELPER ----------------

def format_time_value(time_value):
    """
    Converts MySQL TIME value into HH:MM format.

    Handles both:
    - datetime.timedelta
    - string values
    """

    if isinstance(time_value, timedelta):

        total_seconds = int(
            time_value.total_seconds()
        )

        hours = total_seconds // 3600

        minutes = (
            total_seconds % 3600
        ) // 60

        return f"{hours:02d}:{minutes:02d}"

    return str(time_value)[:5]


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def init_db():

    """Create database tables."""

    conn = get_db()
    cur = conn.cursor()

    # Users table

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INT AUTO_INCREMENT PRIMARY KEY,

            name VARCHAR(100) NOT NULL,

            mobile VARCHAR(20) NOT NULL UNIQUE,

            email VARCHAR(120),

            password_hash VARCHAR(255) NOT NULL,

            college VARCHAR(150),

            purpose VARCHAR(100),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # Visits table

    cur.execute("""
        CREATE TABLE IF NOT EXISTS visits (

            id INT AUTO_INCREMENT PRIMARY KEY,

            user_id INT NOT NULL,

            visit_date DATE NOT NULL,

            start_time TIME NOT NULL,

            end_time TIME NOT NULL,

            purpose VARCHAR(100),

            status ENUM(
                'Booked',
                'Present',
                'Completed',
                'Cancelled'
            ) DEFAULT 'Booked',

            check_in DATETIME NULL,

            check_out DATETIME NULL,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            UNIQUE KEY unique_slot (
                visit_date,
                start_time,
                end_time
            )
        )
    """)


    # Admin table

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (

            id INT AUTO_INCREMENT PRIMARY KEY,

            username VARCHAR(50) NOT NULL UNIQUE,

            password_hash VARCHAR(255) NOT NULL
        )
    """)


    # Attendance table

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (

            attendance_id INT AUTO_INCREMENT PRIMARY KEY,

            user_id INT NOT NULL,

            attendance_date DATE NOT NULL,

            status VARCHAR(20) DEFAULT 'Present',

            photo VARCHAR(255),

            marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE KEY unique_daily_attendance (
                user_id,
                attendance_date
            ),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)


    # Create default admin if not available

    cur.execute(
        "SELECT id FROM admins WHERE username=%s",
        ("admin",)
    )

    if not cur.fetchone():

        cur.execute(
            """
            INSERT INTO admins
            (username, password_hash)
            VALUES (%s, %s)
            """,
            (
                "admin",
                generate_password_hash("admin123")
            )
        )


    conn.commit()

    cur.close()
    conn.close()


# ---------------- LOGIN PROTECTION ----------------

def login_required(f):

    @wraps(f)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return wrapped


def admin_required(f):

    @wraps(f)
    def wrapped(*args, **kwargs):

        if "admin_id" not in session:

            flash(
                "Admin login required.",
                "warning"
            )

            return redirect(
                url_for("admin_login")
            )

        return f(*args, **kwargs)

    return wrapped


# ---------------- HOME ----------------

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ---------------- REGISTRATION ----------------

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form["name"].strip()

        mobile = request.form["mobile"].strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form["password"]

        college = request.form.get(
            "college",
            ""
        ).strip()

        purpose = request.form.get(
            "purpose",
            "Internship"
        )


        if not name or not mobile or not password:

            flash(
                "Name, mobile number and password are required.",
                "danger"
            )

            return render_template(
                "register.html"
            )


        conn = get_db()

        cur = conn.cursor()

        try:

            cur.execute(
                "SELECT id FROM users WHERE mobile=%s",
                (mobile,)
            )

            if cur.fetchone():

                flash(
                    "This mobile number is already registered. "
                    "Please use Existing User Login.",
                    "warning"
                )

                return render_template(
                    "register.html"
                )


            cur.execute("""
                INSERT INTO users
                (
                    name,
                    mobile,
                    email,
                    password_hash,
                    college,
                    purpose
                )
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                name,
                mobile,
                email,
                generate_password_hash(password),
                college,
                purpose
            ))


            conn.commit()


            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        finally:

            cur.close()
            conn.close()


    return render_template(
        "register.html"
    )


# ---------------- LOGIN ----------------

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        mobile = request.form["mobile"].strip()

        password = request.form["password"]

        conn = get_db()

        cur = conn.cursor(
            dictionary=True
        )

        cur.execute(
            "SELECT * FROM users WHERE mobile=%s",
            (mobile,)
        )

        user = cur.fetchone()

        cur.close()
        conn.close()


        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            return redirect(
                url_for("dashboard")
            )


        flash(
            "Invalid mobile number or password.",
            "danger"
        )


    return render_template(
        "login.html"
    )


# ---------------- USER LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# ---------------- USER DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():

    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    # User details

    cur.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cur.fetchone()


    # Visit records

    cur.execute("""
        SELECT *
        FROM visits
        WHERE user_id=%s
        ORDER BY visit_date DESC, start_time DESC
    """, (
        session["user_id"],
    ))

    visits = cur.fetchall()


    # Attendance records

    cur.execute("""
        SELECT *
        FROM attendance
        WHERE user_id=%s
        ORDER BY attendance_date DESC
    """, (
        session["user_id"],
    ))

    attendance = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "dashboard.html",
        user=user,
        visits=visits,
        attendance=attendance,
        now_date=date.today()
    )


# ---------------- ATTENDANCE ----------------

@app.route(
    "/attendance",
    methods=["POST"]
)
@login_required
def mark_attendance():

    user_id = session["user_id"]

    today = date.today()

    photo = request.files.get("photo")


    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    # Check whether attendance is already marked today

    cur.execute("""
        SELECT *
        FROM attendance
        WHERE user_id=%s
        AND attendance_date=%s
    """, (
        user_id,
        today
    ))

    existing = cur.fetchone()


    if existing:

        cur.close()
        conn.close()

        flash(
            "Today's attendance is already marked.",
            "warning"
        )

        return redirect(
            url_for("dashboard")
        )


    # Photo is required

    if not photo or photo.filename == "":

        cur.close()
        conn.close()

        flash(
            "Please upload a photo before marking attendance.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    # Check file type

    if not allowed_file(
        photo.filename
    ):

        cur.close()
        conn.close()

        flash(
            "Please upload a valid image "
            "(JPG, JPEG, PNG or WEBP).",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    # Create safe filename

    original_filename = secure_filename(
        photo.filename
    )

    extension = original_filename.rsplit(
        ".",
        1
    )[1].lower()


    filename = (
        f"user_{user_id}_"
        f"{today.strftime('%Y%m%d')}_"
        f"{datetime.now().strftime('%H%M%S')}"
        f".{extension}"
    )


    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )


    # Save photo

    photo.save(filepath)


    # Save attendance in database

    cur.execute("""
        INSERT INTO attendance
        (
            user_id,
            attendance_date,
            status,
            photo
        )
        VALUES (%s,%s,%s,%s)
    """, (
        user_id,
        today,
        "Present",
        filename
    ))


    conn.commit()

    cur.close()
    conn.close()


    flash(
        "Today's attendance marked successfully!",
        "success"
    )


    return redirect(
        url_for("dashboard")
    )


# ---------------- BOOK SLOT ----------------

@app.route(
    "/book",
    methods=["GET", "POST"]
)
@login_required
def book():

    selected_date = request.values.get(
        "visit_date",
        date.today().isoformat()
    )


    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    # IMPORTANT:
    # Both Booked and Present slots are blocked
    # for every user.

    cur.execute("""
        SELECT
            start_time,
            end_time,
            status,
            u.name
        FROM visits v
        JOIN users u
            ON u.id = v.user_id
        WHERE v.visit_date=%s
        AND v.status IN ('Booked','Present')
    """, (
        selected_date,
    ))


    booked_rows = cur.fetchall()


    booked = {}


    # Convert MySQL TIME correctly to HH:MM

    for row in booked_rows:

        start = format_time_value(
            row["start_time"]
        )

        booked[start] = row


    # ---------------- POST BOOKING ----------------

    if request.method == "POST":

        start = request.form["start_time"]

        end = request.form["end_time"]

        purpose = request.form.get(
            "purpose",
            "Internship"
        )


        if selected_date < date.today().isoformat():

            cur.close()
            conn.close()

            flash(
                "Please select today or a future date.",
                "danger"
            )

            return redirect(
                url_for(
                    "book",
                    visit_date=selected_date
                )
            )


        try:

            # Extra server-side check
            # so users cannot manually submit a booked slot.

            cur.execute("""
                SELECT id
                FROM visits
                WHERE visit_date=%s
                AND start_time=%s
                AND end_time=%s
                AND status IN ('Booked','Present')
            """, (
                selected_date,
                start,
                end
            ))


            already_booked = cur.fetchone()


            if already_booked:

                conn.rollback()

                cur.close()
                conn.close()

                flash(
                    "This slot is already booked. "
                    "Please select another slot.",
                    "warning"
                )

                return redirect(
                    url_for(
                        "book",
                        visit_date=selected_date
                    )
                )


            cur.execute("""
                INSERT INTO visits
                (
                    user_id,
                    visit_date,
                    start_time,
                    end_time,
                    purpose,
                    status
                )
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                session["user_id"],
                selected_date,
                start,
                end,
                purpose,
                "Booked"
            ))


            conn.commit()


            visit_id = cur.lastrowid


            cur.close()
            conn.close()


            return redirect(
                url_for(
                    "confirmation",
                    visit_id=visit_id
                )
            )


        except Error as e:

            conn.rollback()

            cur.close()
            conn.close()


            if "Duplicate entry" in str(e):

                flash(
                    "Sorry, that slot was just booked. "
                    "Please select another slot.",
                    "warning"
                )

            else:

                flash(
                    "Could not book the slot. "
                    "Please try again.",
                    "danger"
                )


            return redirect(
                url_for(
                    "book",
                    visit_date=selected_date
                )
            )


    cur.close()
    conn.close()


    return render_template(
        "book.html",
        selected_date=selected_date,
        slots=SLOTS,
        booked=booked
    )


# ---------------- BOOKING CONFIRMATION ----------------

@app.route(
    "/confirmation/<int:visit_id>"
)
@login_required
def confirmation(visit_id):

    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    cur.execute("""
        SELECT
            v.*,
            u.name,
            u.mobile,
            u.college
        FROM visits v
        JOIN users u
            ON v.user_id=u.id
        WHERE v.id=%s
        AND v.user_id=%s
    """, (
        visit_id,
        session["user_id"]
    ))


    visit = cur.fetchone()


    cur.close()
    conn.close()


    if not visit:

        flash(
            "Booking not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "confirmation.html",
        visit=visit
    )


# ---------------- CHECK-IN ----------------

@app.route(
    "/checkin/<int:visit_id>",
    methods=["POST"]
)
@login_required
def checkin(visit_id):

    conn = get_db()

    cur = conn.cursor()


    cur.execute("""
        UPDATE visits
        SET
            status='Present',
            check_in=NOW()
        WHERE id=%s
        AND user_id=%s
        AND status='Booked'
    """, (
        visit_id,
        session["user_id"]
    ))


    conn.commit()

    cur.close()
    conn.close()


    flash(
        "Check-in recorded successfully.",
        "success"
    )


    return redirect(
        url_for("dashboard")
    )


# ---------------- CHECK-OUT ----------------

@app.route(
    "/checkout/<int:visit_id>",
    methods=["POST"]
)
@login_required
def checkout(visit_id):

    conn = get_db()

    cur = conn.cursor()


    cur.execute("""
        UPDATE visits
        SET
            status='Completed',
            check_out=NOW()
        WHERE id=%s
        AND user_id=%s
        AND status='Present'
    """, (
        visit_id,
        session["user_id"]
    ))


    conn.commit()

    cur.close()
    conn.close()


    flash(
        "Check-out recorded successfully.",
        "success"
    )


    return redirect(
        url_for("dashboard")
    )


# ---------------- SLOT API ----------------

@app.route("/api/slots")
def api_slots():

    visit_date = request.args.get(
        "date",
        date.today().isoformat()
    )


    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    cur.execute("""
        SELECT
            start_time,
            end_time,
            status,
            u.name
        FROM visits v
        JOIN users u
            ON u.id=v.user_id
        WHERE v.visit_date=%s
        AND v.status IN ('Booked','Present')
    """, (
        visit_date,
    ))


    rows = cur.fetchall()


    cur.close()
    conn.close()


    booked = {}


    for row in rows:

        start = format_time_value(
            row["start_time"]
        )

        booked[start] = row


    result = []


    for start, end in SLOTS:

        row = booked.get(start)


        result.append({

            "start": start,

            "end": end,

            "available": row is None,

            "name": (
                row["name"]
                if row
                else None
            ),

            "status": (
                row["status"]
                if row
                else "Available"
            )
        })


    return jsonify(result)


# ==========================================================
# ADMIN
# ==========================================================


# ---------------- ADMIN LOGIN ----------------

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]


        conn = get_db()

        cur = conn.cursor(
            dictionary=True
        )


        cur.execute(
            "SELECT * FROM admins WHERE username=%s",
            (username,)
        )


        admin = cur.fetchone()


        cur.close()
        conn.close()


        if admin and check_password_hash(
            admin["password_hash"],
            password
        ):

            session.clear()

            session["admin_id"] = admin["id"]

            session["admin_username"] = (
                admin["username"]
            )


            return redirect(
                url_for("admin_dashboard")
            )


        flash(
            "Invalid admin username or password.",
            "danger"
        )


    return render_template(
        "admin_login.html"
    )


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    today = date.today().isoformat()


    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    # Total users

    cur.execute(
        "SELECT COUNT(*) AS total FROM users"
    )

    total_users = cur.fetchone()["total"]


    # Booked today

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM visits
        WHERE visit_date=%s
        AND status IN ('Booked','Present')
    """, (
        today,
    ))

    booked_today = cur.fetchone()["total"]


    # Present today

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM visits
        WHERE visit_date=%s
        AND status='Present'
    """, (
        today,
    ))

    present_today = cur.fetchone()["total"]


    # Total visits today

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM visits
        WHERE visit_date=%s
    """, (
        today,
    ))

    today_visits = cur.fetchone()["total"]


    # Today's schedule

    cur.execute("""
        SELECT
            v.*,
            u.name,
            u.mobile,
            u.college
        FROM visits v
        JOIN users u
            ON v.user_id=u.id
        WHERE v.visit_date=%s
        ORDER BY v.start_time
    """, (
        today,
    ))


    schedule = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        booked_today=booked_today,
        present_today=present_today,
        today_visits=today_visits,
        schedule=schedule
    )


# ---------------- ADMIN ALL VISITS ----------------

@app.route("/admin/visits")
@admin_required
def admin_visits():

    selected_month = request.args.get(
        "month",
        ""
    )


    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    if selected_month:

        # Selected month's first date

        start_date = datetime.strptime(
            selected_month + "-01",
            "%Y-%m-%d"
        ).date()


        # Calculate next month

        if start_date.month == 12:

            next_month = date(
                start_date.year + 1,
                1,
                1
            )

        else:

            next_month = date(
                start_date.year,
                start_date.month + 1,
                1
            )


        cur.execute("""
            SELECT
                v.*,
                u.name,
                u.mobile,
                u.email,
                u.college,
                a.photo AS attendance_photo
            FROM visits v
            JOIN users u
                ON v.user_id = u.id
            LEFT JOIN attendance a
                ON v.user_id = a.user_id
                AND v.visit_date = a.attendance_date
            WHERE v.visit_date >= %s
              AND v.visit_date < %s
            ORDER BY
                v.visit_date DESC,
                v.start_time DESC
        """, (
            start_date,
            next_month
        ))


    else:

        cur.execute("""
            SELECT
                v.*,
                u.name,
                u.mobile,
                u.email,
                u.college,
                a.photo AS attendance_photo
            FROM visits v
            JOIN users u
                ON v.user_id = u.id
            LEFT JOIN attendance a
                ON v.user_id = a.user_id
                AND v.visit_date = a.attendance_date
            ORDER BY
                v.visit_date DESC,
                v.start_time DESC
        """)


    visits = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "admin_visits.html",
        visits=visits,
        selected_month=selected_month
    )


# ---------------- ADMIN MONTHLY RECORDS ----------------

@app.route("/admin/monthly-records")
@admin_required
def admin_monthly_records():

    selected_month = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )


    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    cur.execute("""
        SELECT
            v.visit_date,
            v.start_time,
            v.end_time,
            v.purpose,
            v.check_in,
            v.check_out,
            v.status,
            u.name,
            u.mobile,
            u.email,
            u.college,
            a.status AS attendance_status,
            a.photo AS attendance_photo
        FROM visits v
        JOIN users u
            ON v.user_id = u.id
        LEFT JOIN attendance a
            ON v.user_id = a.user_id
            AND v.visit_date = a.attendance_date
        WHERE DATE_FORMAT(
            v.visit_date,
            '%%Y-%%m'
        ) = %s
        ORDER BY
            v.visit_date DESC,
            v.start_time DESC
    """, (
        selected_month,
    ))


    records = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "admin_monthly_records.html",
        records=records,
        selected_month=selected_month
    )


# ---------------- DOWNLOAD MONTHLY EXCEL ----------------

@app.route(
    "/admin/monthly-records/download"
)
@admin_required
def download_monthly_records():

    selected_month = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )


    # Selected month's first date

    start_date = datetime.strptime(
        selected_month + "-01",
        "%Y-%m-%d"
    ).date()


    # Calculate next month

    if start_date.month == 12:

        next_month = date(
            start_date.year + 1,
            1,
            1
        )

    else:

        next_month = date(
            start_date.year,
            start_date.month + 1,
            1
        )


    conn = get_db()

    cur = conn.cursor(
        dictionary=True
    )


    cur.execute("""
        SELECT
            v.visit_date,
            v.start_time,
            v.end_time,
            v.purpose,
            v.check_in,
            v.check_out,
            v.status,
            u.name,
            u.mobile,
            u.email,
            u.college,
            a.status AS attendance_status
        FROM visits v
        JOIN users u
            ON v.user_id = u.id
        LEFT JOIN attendance a
            ON v.user_id = a.user_id
            AND v.visit_date = a.attendance_date
        WHERE v.visit_date >= %s
          AND v.visit_date < %s
        ORDER BY
            v.visit_date ASC,
            v.start_time ASC
    """, (
        start_date,
        next_month
    ))


    records = cur.fetchall()


    cur.close()
    conn.close()


    # Create Excel workbook

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = "Monthly Records"


    # Heading

    sheet.append([
        "Date",
        "Name",
        "Mobile",
        "Email",
        "College / Organisation",
        "Purpose",
        "Time",
        "Check-in",
        "Check-out",
        "Status",
        "Attendance"
    ])


    # Add records

    for record in records:

        start_time = format_time_value(
            record["start_time"]
        )

        end_time = format_time_value(
            record["end_time"]
        )


        check_in = (
            record["check_in"].strftime(
                "%d-%m-%Y %H:%M"
            )
            if record["check_in"]
            else "—"
        )


        check_out = (
            record["check_out"].strftime(
                "%d-%m-%Y %H:%M"
            )
            if record["check_out"]
            else "—"
        )


        sheet.append([
            str(record["visit_date"]),
            record["name"],
            record["mobile"],
            record["email"] or "—",
            record["college"] or "—",
            record["purpose"] or "—",
            f"{start_time} - {end_time}",
            check_in,
            check_out,
            record["status"],
            record["attendance_status"]
            or "Not Marked"
        ])


    # Make columns wider

    column_widths = {

        "A": 14,

        "B": 22,

        "C": 16,

        "D": 28,

        "E": 25,

        "F": 18,

        "G": 18,

        "H": 20,

        "I": 20,

        "J": 15,

        "K": 18
    }


    for column, width in column_widths.items():

        sheet.column_dimensions[
            column
        ].width = width


    # Save Excel file

    filename = (
        f"monthly_records_{selected_month}.xlsx"
    )


    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )


    workbook.save(filepath)


    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename
    )


# ---------------- ADMIN LOGOUT ----------------

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_username",
        None
    )


    return redirect(
        url_for("admin_login")
    )


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    try:

        init_db()

        app.run(
            debug=True
        )

    except Error as e:

        print(
            "\nMySQL connection failed."
        )

        print(
            "Make sure MySQL is running and "
            "the database 'jeevan_ankur_db' exists."
        )

        print(
            "Error:",
            e
        )
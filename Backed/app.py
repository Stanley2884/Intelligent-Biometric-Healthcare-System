from flask import Flask, request, jsonify, render_template, redirect, session
import mysql.connector
import os
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from werkzeug.utils import secure_filename

# Optional DeepFace
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception:
    DeepFace = None
    DEEPFACE_AVAILABLE = False


# ============================================================
# APPLICATION
# ============================================================

app = Flask(__name__, template_folder="Templetes")

app.secret_key = "intelligent-biometric-healthcare-secret-key"


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "..",
    "Uploads"
)

BIOMETRIC_FOLDER = os.path.join(
    UPLOAD_FOLDER,
    "biometric_faces"
)

BACKUP_FOLDER = os.path.join(
    BASE_DIR,
    "..",
    "Database",
    "Backups"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BIOMETRIC_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "biometric_healthcare"
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ============================================================
# JSON SAFE CONVERSION
# ============================================================

def make_json_safe(value):

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")

    if isinstance(value, dict):
        return {
            key: make_json_safe(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            make_json_safe(item)
            for item in value
        ]

    return value


def safe_jsonify(data):

    return jsonify(make_json_safe(data))


# ============================================================
# DATABASE TABLE HELPERS
# ============================================================

def get_table_columns(table_name):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            f"SHOW COLUMNS FROM `{table_name}`"
        )

        rows = cursor.fetchall()

        return [
            row[0]
            for row in rows
        ]

    except Exception:

        return []

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


def find_column(table_name, possible_names):

    columns = get_table_columns(table_name)

    for name in possible_names:

        if name in columns:
            return name

    return None


# ============================================================
# SUPPORT TABLES
# ============================================================

def create_support_tables():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prediction_history (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Patient_number VARCHAR(50) NOT NULL,
                Full_name VARCHAR(150) NOT NULL,
                Symptoms TEXT NULL,
                Prediction_disease VARCHAR(150) NULL,
                Risk_level VARCHAR(50) NULL,
                Confidence_score DECIMAL(5,2) NULL,
                Prediction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                Recommendations TEXT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Setting_name VARCHAR(100) UNIQUE,
                Setting_value TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_audit_logs (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Action VARCHAR(255),
                Username VARCHAR(100),
                Details TEXT,
                Created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()

    except Exception as error:

        print("Support table error:", error)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# AUDIT LOG
# ============================================================

def add_audit_log(action, details=""):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        username = session.get(
            "username",
            "System"
        )

        cursor.execute("""
            INSERT INTO system_audit_logs
            (Action, Username, Details)
            VALUES (%s, %s, %s)
        """, (
            action,
            username,
            details
        ))

        connection.commit()

    except Exception as error:

        print("Audit log error:", error)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return """
    <h1>Intelligent Biometric Healthcare Action System</h1>

    <p>Backend is running successfully.</p>

    <a href="/test-db">
        Click here to Test Database Connection
    </a>

    <br><br>

    <a href="/dashboard.html">
        Open Dashboard
    </a>
    """


# ============================================================
# TEST DATABASE
# ============================================================

@app.route("/test-db")
def test_db():

    connection = None

    try:

        connection = get_db_connection()

        if connection.is_connected():

            return """
            <h2>Database connection successful!</h2>

            <p>
            Flask is successfully connected to the
            <strong>biometric_healthcare</strong> database.
            </p>

            <a href="/">Back to Home</a>

            <br><br>

            <a href="/dashboard.html">
                Open Dashboard
            </a>
            """

    except mysql.connector.Error as error:

        return f"""
        <h2>Database connection failed</h2>

        <p>{error}</p>

        <a href="/">Back to Home</a>
        """

    finally:

        if connection:
            connection.close()


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":

        return render_template("login.html")


    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()


    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM users
            WHERE Username = %s
            LIMIT 1
        """, (username,))

        user = cursor.fetchone()


        if not user:

            return render_template(
                "login.html",
                error="Invalid username or password"
            )


        stored_password = user.get("Password", "")


        password_correct = (
            password == stored_password
        )


        if not password_correct:

            try:

                from werkzeug.security import check_password_hash

                password_correct = check_password_hash(
                    stored_password,
                    password
                )

            except Exception:

                password_correct = False


        if not password_correct:

            return render_template(
                "login.html",
                error="Invalid username or password"
            )


        session["logged_in"] = True
        session["user_id"] = user.get("Id")
        session["username"] = user.get("Username")
        session["user_name"] = user.get("Full_name")
        session["user_role"] = user.get("Role", "User")


        add_audit_log(
            "User Login",
            f"User {username} logged into the system"
        )


        return redirect("/dashboard.html")


    except Exception as error:

        return render_template(
            "login.html",
            error=str(error)
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    username = session.get(
        "username",
        "Unknown"
    )

    session.clear()

    return redirect("/login")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)


        # ----------------------------------------------------
        # TOTAL PATIENTS
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM patients
        """)

        total_patients = cursor.fetchone()["total"]


        # ----------------------------------------------------
        # BIOMETRIC RECORDS
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM biometric_records
        """)

        total_biometric_records = cursor.fetchone()["total"]


        # ----------------------------------------------------
        # APPOINTMENTS
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM appointments
        """)

        total_appointments = cursor.fetchone()["total"]


        # ----------------------------------------------------
        # AI PREDICTIONS
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM prediction_history
        """)

        total_predictions = cursor.fetchone()["total"]


        # ----------------------------------------------------
        # RECENT PATIENTS
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                Id,
                Patient_number,
                Full_name,
                Date_of_birth,
                Gender,
                Phone,
                Address,
                Biometric_id,
                Medical_history
            FROM patients
            ORDER BY Id DESC
            LIMIT 5
        """)

        patients = cursor.fetchall()


        statistics = {

            "total_patients":
                total_patients,

            "total_biometric_records":
                total_biometric_records,

            "total_appointments":
                total_appointments,

            "total_predictions":
                total_predictions
        }


        return render_template(
            "dashboard.html",
            statistics=statistics,
            patients=patients
        )


    except Exception as error:

        print("DASHBOARD ERROR:", error)

        return render_template(
            "dashboard.html",
            statistics={
                "total_patients": 0,
                "total_biometric_records": 0,
                "total_appointments": 0,
                "total_predictions": 0
            },
            patients=[]
        )


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DASHBOARD DATA
# ============================================================

@app.route("/dashboard-data")
def dashboard_data():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)


        cursor.execute(
            "SELECT COUNT(*) AS total FROM patients"
        )

        total_patients = cursor.fetchone()["total"]


        cursor.execute(
            "SELECT COUNT(*) AS total FROM biometric_records"
        )

        total_biometric_records = cursor.fetchone()["total"]


        cursor.execute(
            "SELECT COUNT(*) AS total FROM appointments"
        )

        total_appointments = cursor.fetchone()["total"]


        cursor.execute(
            "SELECT COUNT(*) AS total FROM prediction_history"
        )

        total_predictions = cursor.fetchone()["total"]


        cursor.execute("""
            SELECT
                Id,
                Patient_number,
                Full_name,
                Date_of_birth,
                Gender,
                Phone,
                Address,
                Biometric_id,
                Medical_history
            FROM patients
            ORDER BY Id DESC
            LIMIT 5
        """)

        patients = cursor.fetchall()


        return safe_jsonify({

            "status": "success",

            "statistics": {

                "total_patients":
                    total_patients,

                "total_biometric_records":
                    total_biometric_records,

                "total_appointments":
                    total_appointments,

                "total_predictions":
                    total_predictions
            },

            "patients": patients

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# PATIENTS PAGE
# ============================================================

@app.route("/patients")
@app.route("/patients.html")
def patients_page():

    return render_template("patients.html")


# ============================================================
# GET PATIENTS
# ============================================================

@app.route("/get-patients")
def get_patients():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM patients
            ORDER BY Id DESC
        """)

        patients = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "patients": patients
        })


    except Exception as error:

        return safe_jsonify({
            "status": "error",
            "message": str(error)
        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# PATIENT REGISTRATION PAGE
# ============================================================

@app.route("/patient-registration")
@app.route("/patient_registration.html")
def patient_registration():

    return render_template(
        "patient_registration.html"
    )


# ============================================================
# REGISTER PATIENT
# ============================================================

@app.route("/register-patient", methods=["POST"])
def register_patient():

    connection = None
    cursor = None

    try:

        patient_number = request.form.get(
            "patient_number",
            ""
        ).strip()

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        date_of_birth = request.form.get(
            "date_of_birth",
            ""
        ).strip()

        gender = request.form.get(
            "gender",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        biometric_id = request.form.get(
            "biometric_id",
            ""
        ).strip()

        medical_history = request.form.get(
            "medical_history",
            ""
        ).strip()


        if not patient_number or not full_name:

            return safe_jsonify({
                "status": "error",
                "message":
                    "Patient number and full name are required."
            }), 400


        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute("""
            INSERT INTO patients
            (
                Patient_number,
                Full_name,
                Date_of_birth,
                Gender,
                Phone,
                Address,
                Biometric_id,
                Medical_history
            )
            VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            patient_number,
            full_name,
            date_of_birth,
            gender,
            phone,
            address,
            biometric_id,
            medical_history
        ))


        connection.commit()

        patient_id = cursor.lastrowid


        add_audit_log(
            "Patient Registration",
            f"Patient {patient_number} registered"
        )


        return safe_jsonify({

            "status": "success",

            "message":
                "Patient successfully registered.",

            "patient_id":
                patient_id

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# BIOMETRIC PAGE
# ============================================================

@app.route("/biometric")
@app.route("/biometric.html")
def biometric_page():

    return render_template("biometric.html")


# ============================================================
# GET BIOMETRIC RECORDS
# ============================================================

@app.route("/get-biometric-records")
def get_biometric_records():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM biometric_records
            ORDER BY Id DESC
        """)

        records = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "records": records
        })


    except Exception as error:

        return safe_jsonify({
            "status": "error",
            "message": str(error)
        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# BIOMETRIC REGISTRATION
# ============================================================

@app.route("/register-biometric", methods=["POST"])
def register_biometric():

    connection = None
    cursor = None

    try:

        patient_number = request.form.get(
            "patient_number",
            ""
        ).strip()

        biometric_type = request.form.get(
            "biometric_type",
            "Face"
        ).strip()

        biometric_id = request.form.get(
            "biometric_id",
            ""
        ).strip()


        uploaded_file = request.files.get(
            "face_image"
        )


        if not patient_number:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number is required."
            }), 400


        filename = None


        if uploaded_file and uploaded_file.filename:

            original_name = secure_filename(
                uploaded_file.filename
            )

            filename = (
                str(uuid.uuid4())
                + "_"
                + original_name
            )

            file_path = os.path.join(
                BIOMETRIC_FOLDER,
                filename
            )

            uploaded_file.save(file_path)


        connection = get_db_connection()

        cursor = connection.cursor()


        columns = get_table_columns(
            "biometric_records"
        )


        possible_patient_column = find_column(
            "biometric_records",
            [
                "Patient_number",
                "patient_number"
            ]
        )


        possible_type_column = find_column(
            "biometric_records",
            [
                "Biometric_type",
                "biometric_type",
                "Type"
            ]
        )


        possible_id_column = find_column(
            "biometric_records",
            [
                "Biometric_id",
                "biometric_id"
            ]
        )


        possible_image_column = find_column(
            "biometric_records",
            [
                "Image_path",
                "image_path",
                "Face_image",
                "face_image",
                "Image"
            ]
        )


        insert_columns = []
        insert_values = []


        if possible_patient_column:

            insert_columns.append(
                possible_patient_column
            )

            insert_values.append(
                patient_number
            )


        if possible_type_column:

            insert_columns.append(
                possible_type_column
            )

            insert_values.append(
                biometric_type
            )


        if possible_id_column:

            insert_columns.append(
                possible_id_column
            )

            insert_values.append(
                biometric_id
            )


        if possible_image_column:

            insert_columns.append(
                possible_image_column
            )

            insert_values.append(
                filename or ""
            )


        if not insert_columns:

            return safe_jsonify({
                "status": "error",
                "message":
                    "Unable to identify biometric table columns."
            }), 500


        placeholders = ", ".join(
            ["%s"] * len(insert_columns)
        )

        column_string = ", ".join(
            f"`{column}`"
            for column in insert_columns
        )


        sql = f"""
            INSERT INTO biometric_records
            ({column_string})
            VALUES ({placeholders})
        """


        cursor.execute(
            sql,
            tuple(insert_values)
        )


        connection.commit()


        add_audit_log(
            "Biometric Registration",
            f"Biometric record registered for {patient_number}"
        )


        return safe_jsonify({

            "status": "success",

            "message":
                "Biometric record registered successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# FACE RECOGNITION
# ============================================================

@app.route("/recognize-face", methods=["POST"])
def recognize_face():

    if not DEEPFACE_AVAILABLE:

        return safe_jsonify({

            "status": "error",

            "message":
                "DeepFace is not currently available. "
                "Biometric registration can still be used."

        }), 503


    uploaded_file = request.files.get(
        "face_image"
    )


    if not uploaded_file:

        return safe_jsonify({

            "status": "error",

            "message": "No face image uploaded."

        }), 400


    filename = (
        str(uuid.uuid4())
        + "_recognition_"
        + secure_filename(
            uploaded_file.filename
        )
    )


    image_path = os.path.join(
        BIOMETRIC_FOLDER,
        filename
    )


    uploaded_file.save(image_path)


    try:

        result = DeepFace.find(
            img_path=image_path,
            db_path=BIOMETRIC_FOLDER,
            enforce_detection=False
        )


        return safe_jsonify({

            "status": "success",

            "message":
                "Face recognition completed.",

            "result":
                result

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message":
                str(error)

        }), 500


# ============================================================
# MEDICAL RECORDS PAGE
# ============================================================

@app.route("/medical-records")
@app.route("/medical_records.html")
def medical_records_page():

    return render_template(
        "medical_records.html"
    )


# ============================================================
# GET MEDICAL RECORDS
# ============================================================

@app.route("/get-medical-records")
def get_medical_records():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        cursor.execute("""
            SELECT *
            FROM medical_records
            ORDER BY Id DESC
        """)


        records = cursor.fetchall()


        return safe_jsonify({

            "status": "success",

            "records": records

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# ADD MEDICAL RECORD
# ============================================================

@app.route("/add-medical-record", methods=["POST"])
def add_medical_record():

    connection = None
    cursor = None

    try:

        patient_number = request.form.get(
            "patient_number",
            ""
        ).strip()

        visit_date = request.form.get(
            "visit_date",
            request.form.get(
                "visit_dates",
                ""
            )
        ).strip()

        symptoms = request.form.get(
            "symptoms",
            request.form.get(
                "symtoms",
                ""
            )
        ).strip()

        diagnosis = request.form.get(
            "diagnosis",
            ""
        ).strip()

        doctor_name = request.form.get(
            "doctor_name",
            ""
        ).strip()

        treatment = request.form.get(
            "treatment",
            ""
        ).strip()

        notes = request.form.get(
            "notes",
            ""
        ).strip()


        connection = get_db_connection()

        cursor = connection.cursor()


        columns = get_table_columns(
            "medical_records"
        )


        patient_col = find_column(
            "medical_records",
            [
                "Patient_number",
                "patient_number"
            ]
        )


        date_col = find_column(
            "medical_records",
            [
                "Visit_dates",
                "Visit_date",
                "visit_date"
            ]
        )


        symptoms_col = find_column(
            "medical_records",
            [
                "Symtoms",
                "Symptoms",
                "symptoms"
            ]
        )


        diagnosis_col = find_column(
            "medical_records",
            [
                "Diagnosis",
                "diagnosis"
            ]
        )


        doctor_col = find_column(
            "medical_records",
            [
                "Doctor_name",
                "doctor_name"
            ]
        )


        treatment_col = find_column(
            "medical_records",
            [
                "Treatment",
                "treatment"
            ]
        )


        notes_col = find_column(
            "medical_records",
            [
                "Notes",
                "notes"
            ]
        )


        insert_columns = []
        insert_values = []


        mappings = [

            (patient_col, patient_number),

            (date_col, visit_date),

            (symptoms_col, symptoms),

            (diagnosis_col, diagnosis),

            (doctor_col, doctor_name),

            (treatment_col, treatment),

            (notes_col, notes)

        ]


        for column, value in mappings:

            if column:

                insert_columns.append(column)

                insert_values.append(value)


        column_string = ", ".join(
            f"`{column}`"
            for column in insert_columns
        )


        placeholders = ", ".join(
            ["%s"] * len(insert_columns)
        )


        sql = f"""
            INSERT INTO medical_records
            ({column_string})
            VALUES ({placeholders})
        """


        cursor.execute(
            sql,
            tuple(insert_values)
        )


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "message":
                "Medical record added successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# APPOINTMENTS PAGE
# ============================================================

@app.route("/appointments")
@app.route("/appointments.html")
def appointments_page():

    return render_template(
        "appointments.html"
    )


# ============================================================
# GET APPOINTMENTS
# ============================================================

@app.route("/get-appointments")
def get_appointments():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        cursor.execute("""
            SELECT *
            FROM appointments
            ORDER BY Appointment_date DESC,
                     Appointment_time DESC
        """)


        appointments = cursor.fetchall()


        today = date.today()


        for appointment in appointments:

            appointment_date = (
                appointment.get("Appointment_date")
                or appointment.get("appointment_date")
            )


            if isinstance(
                appointment_date,
                datetime
            ):

                appointment_date = (
                    appointment_date.date()
                )


            appointment["is_today"] = (
                appointment_date == today
            )


        total = len(appointments)

        today_count = sum(
            1
            for appointment in appointments
            if appointment.get("is_today")
        )


        pending_count = sum(

            1

            for appointment in appointments

            if str(
                appointment.get("Status", "")
            ).lower() == "pending"

        )


        return safe_jsonify({

            "status": "success",

            "appointments":
                appointments,

            "total":
                total,

            "today":
                today_count,

            "pending":
                pending_count

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# SCHEDULE APPOINTMENT
# ============================================================

@app.route("/schedule-appointment", methods=["POST"])
def schedule_appointment():

    connection = None
    cursor = None

    try:

        patient_number = request.form.get(
            "patient_number",
            ""
        ).strip()

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        appointment_date = request.form.get(
            "appointment_date",
            ""
        ).strip()

        appointment_time = request.form.get(
            "appointment_time",
            ""
        ).strip()

        doctor_name = request.form.get(
            "doctor_name",
            ""
        ).strip()

        department = request.form.get(
            "department",
            "General Medicine"
        ).strip()

        status = request.form.get(
            "status",
            "Pending"
        ).strip()


        connection = get_db_connection()

        cursor = connection.cursor()


        columns = get_table_columns(
            "appointments"
        )


        patient_col = find_column(
            "appointments",
            [
                "Patient_number",
                "patient_number"
            ]
        )


        name_col = find_column(
            "appointments",
            [
                "Full_name",
                "full_name"
            ]
        )


        date_col = find_column(
            "appointments",
            [
                "Appointment_date",
                "appointment_date"
            ]
        )


        time_col = find_column(
            "appointments",
            [
                "Appointment_time",
                "appointment_time"
            ]
        )


        doctor_col = find_column(
            "appointments",
            [
                "Doctor_name",
                "doctor_name"
            ]
        )


        department_col = find_column(
            "appointments",
            [
                "Department",
                "department"
            ]
        )


        status_col = find_column(
            "appointments",
            [
                "Status",
                "status"
            ]
        )


        insert_columns = []
        insert_values = []


        mappings = [

            (patient_col, patient_number),

            (name_col, full_name),

            (date_col, appointment_date),

            (time_col, appointment_time),

            (doctor_col, doctor_name),

            (department_col, department),

            (status_col, status)

        ]


        for column, value in mappings:

            if column:

                insert_columns.append(column)

                insert_values.append(value)


        column_string = ", ".join(
            f"`{column}`"
            for column in insert_columns
        )


        placeholders = ", ".join(
            ["%s"] * len(insert_columns)
        )


        sql = f"""
            INSERT INTO appointments
            ({column_string})
            VALUES ({placeholders})
        """


        cursor.execute(
            sql,
            tuple(insert_values)
        )


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "message":
                "Appointment scheduled successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# UPDATE APPOINTMENT
# ============================================================

@app.route("/update-appointment/<int:appointment_id>", methods=["POST"])
def update_appointment(appointment_id):

    connection = None
    cursor = None

    try:

        status = request.form.get(
            "status",
            request.json.get("status")
            if request.is_json
            else "Pending"
        )


        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute("""
            UPDATE appointments
            SET Status = %s
            WHERE Id = %s
        """, (
            status,
            appointment_id
        ))


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "message":
                "Appointment updated successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# CANCEL APPOINTMENT
# ============================================================

@app.route("/cancel-appointment/<int:appointment_id>", methods=["POST"])
def cancel_appointment(appointment_id):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute("""
            UPDATE appointments
            SET Status = 'Cancelled'
            WHERE Id = %s
        """, (appointment_id,))


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "message":
                "Appointment cancelled successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# AI PREDICTION PAGE
# ============================================================

@app.route("/ai-prediction")
@app.route("/ai_prediction.html")
def ai_prediction_page():

    return render_template(
        "ai_prediction.html"
    )


# ============================================================
# AI DISEASE PREDICTION
# ============================================================

@app.route("/ai-predict", methods=["POST"])
def ai_predict():

    connection = None
    cursor = None

    try:

        patient_number = request.form.get(
            "patient_number",
            ""
        ).strip()

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        symptoms = request.form.get(
            "symptoms",
            ""
        ).strip().lower()


        if not symptoms:

            return safe_jsonify({

                "status": "error",

                "message":
                    "Please enter patient symptoms."

            }), 400


        # ----------------------------------------------------
        # SIMPLE AI DEMONSTRATION MODEL
        # ----------------------------------------------------

        disease = "General Infection"
        risk_level = "Low"
        confidence = 68
        recommendations = (
            "Monitor the patient and seek medical "
            "review if symptoms persist."
        )


        if (
            "chest pain" in symptoms
            or "difficulty breathing" in symptoms
        ):

            disease = "Cardiovascular Risk"
            risk_level = "High"
            confidence = 88

            recommendations = (
                "Seek medical assessment promptly "
                "and monitor vital signs."
            )


        elif (
            "diabetes" in symptoms
            or "excessive thirst" in symptoms
            or "frequent urination" in symptoms
        ):

            disease = "Diabetes Risk"
            risk_level = "High"
            confidence = 86

            recommendations = (
                "Consider blood glucose testing "
                "and professional medical evaluation."
            )


        elif (
            "fever" in symptoms
            and (
                "cough" in symptoms
                or "cold" in symptoms
            )
        ):

            disease = "Respiratory Infection"
            risk_level = "Medium"
            confidence = 82

            recommendations = (
                "Monitor temperature and respiratory "
                "symptoms and seek medical advice."
            )


        elif (
            "fever" in symptoms
            or "headache" in symptoms
            or "pain" in symptoms
        ):

            disease = "General Infection"
            risk_level = "Medium"
            confidence = 76

            recommendations = (
                "Monitor symptoms and consult a "
                "healthcare professional if they persist."
            )


        # ----------------------------------------------------
        # SAVE PREDICTION
        # ----------------------------------------------------

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute("""
            INSERT INTO prediction_history
            (
                Patient_number,
                Full_name,
                Symptoms,
                Prediction_disease,
                Risk_level,
                Confidence_score,
                Recommendations
            )
            VALUES
            (%s, %s, %s, %s, %s, %s, %s)
        """, (
            patient_number,
            full_name,
            symptoms,
            disease,
            risk_level,
            confidence,
            recommendations
        ))


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "prediction": {

                "disease":
                    disease,

                "risk_level":
                    risk_level,

                "confidence_score":
                    confidence,

                "recommendations":
                    recommendations

            }

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# AI HISTORY
# ============================================================

@app.route("/prediction-history")
def prediction_history():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        cursor.execute("""
            SELECT
                Id,
                Patient_number,
                Full_name,
                Symptoms,
                Prediction_disease,
                Risk_level,
                Confidence_score,
                Prediction_date,
                Recommendations
            FROM prediction_history
            ORDER BY Id DESC
        """)


        records = cursor.fetchall()


        return safe_jsonify({

            "status": "success",

            "records":
                records

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# REPORTS PAGE
# ============================================================

@app.route("/reports")
@app.route("/reports.html")
def reports_page():

    return render_template(
        "reports.html"
    )


# ============================================================
# REPORT DATA
# ============================================================

@app.route("/reports-data")
def reports_data():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        cursor.execute("""
            SELECT
                Id,
                Patient_number,
                Full_name,
                Symptoms,
                Prediction_disease,
                Risk_level,
                Confidence_score,
                Prediction_date,
                Recommendations
            FROM prediction_history
            ORDER BY Prediction_date DESC
        """)


        predictions = cursor.fetchall()


        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM patients
        """)

        total_patients = cursor.fetchone()["total"]


        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM medical_records
        """)

        total_medical_records = cursor.fetchone()["total"]


        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM appointments
        """)

        total_appointments = cursor.fetchone()["total"]


        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM prediction_history
        """)

        total_predictions = cursor.fetchone()["total"]


        return safe_jsonify({

            "status": "success",

            "statistics": {

                "total_patients":
                    total_patients,

                "total_medical_records":
                    total_medical_records,

                "total_appointments":
                    total_appointments,

                "total_predictions":
                    total_predictions
            },

            "predictions":
                predictions

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# USERS PAGE
# ============================================================

@app.route("/users")
@app.route("/users.html")
def users_page():

    return render_template(
        "users.html"
    )


# ============================================================
# GET USERS
# ============================================================

@app.route("/get-users")
def get_users():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        cursor.execute("""
            SELECT
                Id,
                Full_name,
                Username,
                Email,
                Role
            FROM users
            ORDER BY Id DESC
        """)


        users = cursor.fetchall()


        return safe_jsonify({

            "status": "success",

            "users":
                users

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# CREATE USER
# ============================================================

@app.route("/create-user", methods=["POST"])
def create_user():

    connection = None
    cursor = None

    try:

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        role = request.form.get(
            "role",
            "User"
        ).strip()


        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute("""
            INSERT INTO users
            (
                Full_name,
                Username,
                Email,
                Password,
                Role
            )
            VALUES
            (%s, %s, %s, %s, %s)
        """, (
            full_name,
            username,
            email,
            password,
            role
        ))


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "message":
                "User created successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# SETTINGS PAGE
# ============================================================

@app.route("/settings")
@app.route("/settings.html")
def settings_page():

    return render_template(
        "settings.html"
    )


# ============================================================
# SETTINGS DATA
# ============================================================

@app.route("/settings-data")
def settings_data():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        cursor.execute("""
            SELECT *
            FROM system_settings
            ORDER BY Id
        """)


        settings = cursor.fetchall()


        return safe_jsonify({

            "status": "success",

            "settings":
                settings

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# SAVE SETTING
# ============================================================

@app.route("/save-setting", methods=["POST"])
def save_setting():

    connection = None
    cursor = None

    try:

        setting_name = request.form.get(
            "setting_name",
            ""
        ).strip()

        setting_value = request.form.get(
            "setting_value",
            ""
        ).strip()


        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute("""
            INSERT INTO system_settings
            (
                Setting_name,
                Setting_value
            )
            VALUES
            (%s, %s)
            ON DUPLICATE KEY UPDATE
            Setting_value = VALUES(Setting_value)
        """, (
            setting_name,
            setting_value
        ))


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "message":
                "Setting saved successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# SYSTEM STATUS
# ============================================================

@app.route("/system-status")
def system_status():

    connection = None

    try:

        connection = get_db_connection()

        database_status = (
            "Connected"
            if connection.is_connected()
            else "Disconnected"
        )


        return safe_jsonify({

            "status": "success",

            "database":
                database_status,

            "deepface":
                "Available"
                if DEEPFACE_AVAILABLE
                else "Not Available",

            "server":
                "Running"

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "database":
                "Disconnected",

            "message":
                str(error)

        })


    finally:

        if connection:
            connection.close()


# ============================================================
# AUDIT LOGS
# ============================================================

@app.route("/audit-logs")
def audit_logs():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )


        cursor.execute("""
            SELECT *
            FROM system_audit_logs
            ORDER BY Id DESC
            LIMIT 200
        """)


        logs = cursor.fetchall()


        return safe_jsonify({

            "status": "success",

            "logs":
                logs

        })


    except Exception as error:

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# CLEAR AUDIT LOGS
# ============================================================

@app.route("/clear-audit-logs", methods=["POST"])
def clear_audit_logs():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(
            "DELETE FROM system_audit_logs"
        )


        connection.commit()


        return safe_jsonify({

            "status": "success",

            "message":
                "Audit logs cleared successfully."

        })


    except Exception as error:

        if connection:
            connection.rollback()

        return safe_jsonify({

            "status": "error",

            "message": str(error)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DATABASE BACKUP
# ============================================================

@app.route("/database-backup")
def database_backup():

    return safe_jsonify({

        "status": "success",

        "message":
            "Database backup function is available."

    })


# ============================================================
# 404 HANDLER
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    if request.path.startswith("/api"):

        return safe_jsonify({

            "status": "error",

            "message":
                "Requested endpoint was not found."

        }), 404


    return """
    <h2>Page Not Found</h2>
    <p>The requested page does not exist.</p>
    <a href="/dashboard.html">Back to Dashboard</a>
    """, 404


# ============================================================
# 500 HANDLER
# ============================================================

@app.errorhandler(500)
def internal_server_error(error):

    return safe_jsonify({

        "status": "error",

        "message":
            "Internal server error."

    }), 500


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":

    print("")
    print("==============================================")
    print("  INTELLIGENT BIOMETRIC HEALTHCARE SYSTEM")
    print("==============================================")
    print("Database: biometric_healthcare")
    print("Server: http://localhost:5000")
    print("Dashboard: http://localhost:5000/dashboard.html")
    print("==============================================")
    print("")


    create_support_tables()


    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
from flask import Flask, request, jsonify, render_template, redirect, session, send_file
import mysql.connector
import os
import uuid
import json
import subprocess
from datetime import datetime, date, timedelta
from decimal import Decimal
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash

# ============================================================
# OPTIONAL DEEPFACE
# ============================================================

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception:
    DeepFace = None
    DEEPFACE_AVAILABLE = False


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__, template_folder="Templetes")
app.secret_key = "intelligent-biometric-healthcare-secret-key"


# ============================================================
# PROJECT DIRECTORIES
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "Uploads")
BIOMETRIC_FOLDER = os.path.join(UPLOAD_FOLDER, "biometric_faces")
BACKUP_FOLDER = os.path.join(BASE_DIR, "..", "Database", "Backups")

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
# FIXES:
# - datetime
# - date
# - timedelta from MySQL TIME
# - Decimal from MySQL DECIMAL
# - bytes
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

    if isinstance(value, (list, tuple)):
        return [
            make_json_safe(item)
            for item in value
        ]

    return value


def safe_jsonify(data, status_code=None):
    response = jsonify(make_json_safe(data))

    if status_code is not None:
        response.status_code = status_code

    return response


# ============================================================
# DATABASE COLUMN HELPERS
# ============================================================

def get_table_columns(table_name):

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (DB_CONFIG["database"], table_name)
        )

        return [row[0] for row in cursor.fetchall()]

    except Exception:
        return []

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()


def find_column(columns, possible_names):

    lower_columns = {
        column.lower(): column
        for column in columns
    }

    for name in possible_names:

        if name.lower() in lower_columns:
            return lower_columns[name.lower()]

    return None


# ============================================================
# AUDIT LOG
# ============================================================

def add_audit_log(action, description="", username="System"):

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        columns = get_table_columns("system_audit_logs")

        if not columns:
            return

        action_column = find_column(
            columns,
            ["Action", "action"]
        )

        description_column = find_column(
            columns,
            ["Description", "description"]
        )

        username_column = find_column(
            columns,
            ["Username", "username", "User_name"]
        )

        if not action_column:
            return

        insert_columns = []
        values = []

        insert_columns.append(action_column)
        values.append(action)

        if description_column:
            insert_columns.append(description_column)
            values.append(description)

        if username_column:
            insert_columns.append(username_column)
            values.append(username)

        column_sql = ", ".join(
            f"`{column}`"
            for column in insert_columns
        )

        placeholders = ", ".join(
            ["%s"] * len(values)
        )

        cursor.execute(
            f"""
            INSERT INTO system_audit_logs
            ({column_sql})
            VALUES ({placeholders})
            """,
            tuple(values)
        )

        conn.commit()

    except Exception as e:
        print("Audit log error:", e)

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# SUPPORT TABLES
# ============================================================

def create_support_tables():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Setting_name VARCHAR(100) NOT NULL UNIQUE,
                Setting_value TEXT NULL,
                Updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS system_audit_logs (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Action VARCHAR(150) NOT NULL,
                Description TEXT NULL,
                Username VARCHAR(100) NULL,
                Created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
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
            """
        )

        conn.commit()

    except Exception as e:
        print("Support table error:", e)

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if "username" in session:
        return redirect("/dashboard.html")

    return redirect("/login")


# ============================================================
# TEST DATABASE
# ============================================================

@app.route("/test-db")
def test_db():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DATABASE()")
        database_name = cursor.fetchone()[0]

        return safe_jsonify({
            "status": "success",
            "message": "Database Connection Successful",
            "database": database_name
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:

        return render_template(
            "login.html",
            error="Please enter username and password."
        )

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE Username = %s
            LIMIT 1
            """,
            (username,)
        )

        user = cursor.fetchone()

        if not user:

            return render_template(
                "login.html",
                error="Invalid username or password."
            )

        stored_password = user.get("Password", "")

        password_valid = False

        try:
            password_valid = check_password_hash(
                stored_password,
                password
            )
        except Exception:
            password_valid = False

        if not password_valid and stored_password == password:
            password_valid = True

        if not password_valid:

            return render_template(
                "login.html",
                error="Invalid username or password."
            )

        session["username"] = user.get("Username", username)
        session["full_name"] = user.get("Full_name", username)
        session["role"] = user.get("Role", "User")

        add_audit_log(
            "Login",
            "User logged into the system",
            session["username"]
        )

        return redirect("/dashboard.html")

    except Exception as e:

        return render_template(
            "login.html",
            error=str(e)
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    username = session.get("username", "Unknown")

    add_audit_log(
        "Logout",
        "User logged out of the system",
        username
    )

    session.clear()

    return redirect("/login")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard():
    return render_template("dashboard.html")


@app.route("/dashboard-data")
def dashboard_data():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT COUNT(*) AS total FROM patients"
        )
        total_patients = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM medical_records"
        )
        total_medical_records = cursor.fetchone()["total"]

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

        return safe_jsonify({
            "status": "success",
            "statistics": {
                "total_patients": total_patients,
                "total_medical_records": total_medical_records,
                "total_biometric_records": total_biometric_records,
                "total_appointments": total_appointments,
                "total_predictions": total_predictions
            }
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# PATIENT REGISTRATION
# ============================================================

@app.route("/patient-registration")
@app.route("/patient_registration.html")
def patient_registration():
    return render_template("patient_registration.html")


@app.route("/register-patient", methods=["POST"])
def register_patient():

    conn = None
    cursor = None

    try:

        data = request.form

        patient_number = data.get("patient_number", "").strip()
        full_name = data.get("full_name", "").strip()
        date_of_birth = data.get("date_of_birth", "").strip()
        gender = data.get("gender", "").strip()
        phone = data.get("phone", "").strip()
        address = data.get("address", "").strip()
        biometric_id = data.get("biometric_id", "").strip()
        medical_history = data.get("medical_history", "").strip()

        if not patient_number or not full_name or not date_of_birth:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number, full name and date of birth are required."
            }, 400)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT Id
            FROM patients
            WHERE Patient_number = %s
            LIMIT 1
            """,
            (patient_number,)
        )

        existing = cursor.fetchone()

        if existing:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number already exists."
            }, 400)

        cursor.execute(
            """
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
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                patient_number,
                full_name,
                date_of_birth,
                gender,
                phone,
                address,
                biometric_id,
                medical_history
            )
        )

        conn.commit()

        add_audit_log(
            "Patient Registration",
            f"Registered patient {patient_number} - {full_name}",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Patient successfully registered.",
            "patient_number": patient_number
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# PATIENTS
# ============================================================

@app.route("/patients")
@app.route("/patients.html")
def patients():
    return render_template("patients.html")


@app.route("/get-patients")
def get_patients():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM patients ORDER BY Id DESC"
        )

        patients_data = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "patients": patients_data,
            "total": len(patients_data)
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "patients": []
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# BIOMETRIC PAGE
# ============================================================

@app.route("/biometric")
@app.route("/biometric.html")
def biometric():
    return render_template("biometric.html")


# ============================================================
# BIOMETRIC REGISTRATION
# ============================================================

@app.route("/register-biometric", methods=["POST"])
def register_biometric():

    conn = None
    cursor = None

    try:

        patient_number = request.form.get(
            "patient_number",
            ""
        ).strip()

        biometric_id = request.form.get(
            "biometric_id",
            ""
        ).strip()

        image = request.files.get("face_image")

        if not patient_number:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number is required."
            }, 400)

        if not image:

            return safe_jsonify({
                "status": "error",
                "message": "Face image is required."
            }, 400)

        filename = secure_filename(image.filename)

        if not filename:

            return safe_jsonify({
                "status": "error",
                "message": "Invalid image file."
            }, 400)

        unique_filename = (
            str(uuid.uuid4()) + "_" + filename
        )

        file_path = os.path.join(
            BIOMETRIC_FOLDER,
            unique_filename
        )

        image.save(file_path)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM patients
            WHERE Patient_number = %s
            LIMIT 1
            """,
            (patient_number,)
        )

        patient = cursor.fetchone()

        if not patient:

            return safe_jsonify({
                "status": "error",
                "message": "Patient not found."
            }, 404)

        biometric_columns = get_table_columns(
            "biometric_records"
        )

        if biometric_columns:

            patient_column = find_column(
                biometric_columns,
                ["Patient_number", "patient_number"]
            )

            image_column = find_column(
                biometric_columns,
                [
                    "Image_path",
                    "image_path",
                    "Face_image",
                    "face_image",
                    "Image",
                    "image"
                ]
            )

            biometric_column = find_column(
                biometric_columns,
                [
                    "Biometric_id",
                    "biometric_id"
                ]
            )

            if patient_column:

                insert_columns = [patient_column]
                values = [patient_number]

                if biometric_column:

                    insert_columns.append(
                        biometric_column
                    )

                    values.append(
                        biometric_id or str(uuid.uuid4())
                    )

                if image_column:

                    insert_columns.append(
                        image_column
                    )

                    values.append(
                        file_path
                    )

                sql_columns = ", ".join(
                    f"`{column}`"
                    for column in insert_columns
                )

                placeholders = ", ".join(
                    ["%s"] * len(values)
                )

                cursor.execute(
                    f"""
                    INSERT INTO biometric_records
                    ({sql_columns})
                    VALUES ({placeholders})
                    """,
                    tuple(values)
                )

                conn.commit()

        # Update patient biometric ID
        if biometric_id:

            cursor.execute(
                """
                UPDATE patients
                SET Biometric_id = %s
                WHERE Patient_number = %s
                """,
                (
                    biometric_id,
                    patient_number
                )
            )

            conn.commit()

        add_audit_log(
            "Biometric Registration",
            f"Registered biometric record for {patient_number}",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Biometric record successfully registered.",
            "patient_number": patient_number,
            "image": unique_filename
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# GET BIOMETRIC RECORDS
# ============================================================

@app.route("/get-biometric-records")
def get_biometric_records():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM biometric_records
            ORDER BY Id DESC
            """
        )

        records = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "records": records
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "records": []
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# FACE RECOGNITION
# ============================================================

@app.route("/recognize-face", methods=["POST"])
def recognize_face():

    if not DEEPFACE_AVAILABLE:

        return safe_jsonify({
            "status": "error",
            "message": "DeepFace is not currently available."
        }, 500)

    image = request.files.get("face_image")

    if not image:

        return safe_jsonify({
            "status": "error",
            "message": "Face image is required."
        }, 400)

    filename = secure_filename(image.filename)

    if not filename:

        return safe_jsonify({
            "status": "error",
            "message": "Invalid image."
        }, 400)

    temporary_filename = (
        "scan_" + str(uuid.uuid4()) + "_" + filename
    )

    temporary_path = os.path.join(
        BIOMETRIC_FOLDER,
        temporary_filename
    )

    image.save(temporary_path)

    try:

        results = DeepFace.find(
            img_path=temporary_path,
            db_path=BIOMETRIC_FOLDER,
            enforce_detection=False
        )

        matches = []

        if isinstance(results, list):

            for result in results:

                if hasattr(result, "to_dict"):

                    matches.extend(
                        result.to_dict(
                            orient="records"
                        )
                    )

        return safe_jsonify({
            "status": "success",
            "matches": matches
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "matches": []
        }, 500)

    finally:

        if os.path.exists(temporary_path):

            try:
                os.remove(temporary_path)
            except Exception:
                pass


# ============================================================
# MEDICAL RECORDS
# ============================================================

@app.route("/medical-records")
@app.route("/medical_records.html")
def medical_records():
    return render_template("medical_records.html")


@app.route("/get-medical-records")
def get_medical_records():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM medical_records
            ORDER BY Id DESC
            """
        )

        records = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "records": records
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "records": []
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


@app.route("/add-medical-record", methods=["POST"])
def add_medical_record():

    conn = None
    cursor = None

    try:

        data = request.get_json(silent=True) or request.form

        patient_number = data.get(
            "patient_number",
            ""
        ).strip()

        diagnosis = data.get(
            "diagnosis",
            ""
        ).strip()

        doctor_name = data.get(
            "doctor_name",
            ""
        ).strip()

        treatment = data.get(
            "treatment",
            ""
        ).strip()

        notes = data.get(
            "notes",
            ""
        ).strip()

        if not patient_number:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number is required."
            }, 400)

        conn = get_db_connection()
        cursor = conn.cursor()

        columns = get_table_columns(
            "medical_records"
        )

        patient_column = find_column(
            columns,
            ["Patient_number", "patient_number"]
        )

        diagnosis_column = find_column(
            columns,
            ["Diagnosis", "diagnosis"]
        )

        doctor_column = find_column(
            columns,
            ["Doctor_name", "doctor_name"]
        )

        treatment_column = find_column(
            columns,
            ["Treatment", "treatment"]
        )

        notes_column = find_column(
            columns,
            ["Notes", "notes"]
        )

        insert_columns = []
        values = []

        if patient_column:
            insert_columns.append(patient_column)
            values.append(patient_number)

        if diagnosis_column:
            insert_columns.append(diagnosis_column)
            values.append(diagnosis)

        if doctor_column:
            insert_columns.append(doctor_column)
            values.append(doctor_name)

        if treatment_column:
            insert_columns.append(treatment_column)
            values.append(treatment)

        if notes_column:
            insert_columns.append(notes_column)
            values.append(notes)

        if not insert_columns:

            return safe_jsonify({
                "status": "error",
                "message": "Medical records table columns could not be identified."
            }, 500)

        sql_columns = ", ".join(
            f"`{column}`"
            for column in insert_columns
        )

        placeholders = ", ".join(
            ["%s"] * len(values)
        )

        cursor.execute(
            f"""
            INSERT INTO medical_records
            ({sql_columns})
            VALUES ({placeholders})
            """,
            tuple(values)
        )

        conn.commit()

        add_audit_log(
            "Medical Record Added",
            f"Medical record added for {patient_number}",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Medical record successfully added."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# APPOINTMENTS PAGE
# ============================================================

@app.route("/appointments")
@app.route("/appointments.html")
def appointments():
    return render_template("appointments.html")


# ============================================================
# GET APPOINTMENTS
# ============================================================

@app.route("/get-appointments")
def get_appointments():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        appointment_columns = get_table_columns(
            "appointments"
        )

        patient_column = find_column(
            appointment_columns,
            [
                "Patient_number",
                "patient_number",
                "PatientNumber"
            ]
        )

        id_column = find_column(
            appointment_columns,
            [
                "Id",
                "id"
            ]
        )

        if not patient_column:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number column was not found in appointments table.",
                "appointments": []
            }, 500)

        if not id_column:

            id_column = appointment_columns[0]

        cursor.execute(
            f"""
            SELECT
                a.*,
                p.Full_name
            FROM appointments a
            LEFT JOIN patients p
                ON a.`{patient_column}` = p.Patient_number
            ORDER BY a.`{id_column}` DESC
            """
        )

        raw_appointments = cursor.fetchall()

        date_column = find_column(
            appointment_columns,
            [
                "Appointment_date",
                "appointment_date",
                "Date",
                "date"
            ]
        )

        time_column = find_column(
            appointment_columns,
            [
                "Appointment_time",
                "appointment_time",
                "Time",
                "time"
            ]
        )

        doctor_column = find_column(
            appointment_columns,
            [
                "Doctor_name",
                "doctor_name",
                "Doctor",
                "doctor"
            ]
        )

        department_column = find_column(
            appointment_columns,
            [
                "Department",
                "department"
            ]
        )

        status_column = find_column(
            appointment_columns,
            [
                "Status",
                "status",
                "Stutus",
                "stutus"
            ]
        )

        appointments_data = []

        today = date.today()

        today_count = 0
        pending_count = 0
        confirmed_count = 0
        completed_count = 0
        cancelled_count = 0

        for row in raw_appointments:

            # FIRST make the entire MySQL row JSON-safe.
            # This is what fixes MySQL TIME/timedelta.
            normalized = make_json_safe(dict(row))

            appointment_id = (
                row.get(id_column)
                if id_column
                else None
            )

            appointment_date = (
                row.get(date_column)
                if date_column
                else None
            )

            appointment_time = (
                row.get(time_column)
                if time_column
                else None
            )

            doctor = (
                row.get(doctor_column, "")
                if doctor_column
                else ""
            )

            department = (
                row.get(department_column, "")
                if department_column
                else ""
            )

            status = (
                row.get(status_column, "Pending")
                if status_column
                else "Pending"
            )

            full_name = row.get(
                "Full_name",
                ""
            )

            patient_number = row.get(
                patient_column,
                ""
            )

            # Date formatting
            if isinstance(
                appointment_date,
                datetime
            ):
                date_for_frontend = (
                    appointment_date.strftime(
                        "%Y-%m-%d"
                    )
                )

            elif isinstance(
                appointment_date,
                date
            ):
                date_for_frontend = (
                    appointment_date.strftime(
                        "%Y-%m-%d"
                    )
                )

            elif appointment_date:
                date_for_frontend = str(
                    appointment_date
                )[:10]

            else:
                date_for_frontend = ""

            # Time formatting
            if isinstance(
                appointment_time,
                timedelta
            ):

                total_seconds = int(
                    appointment_time.total_seconds()
                )

                hours = (
                    total_seconds // 3600
                ) % 24

                minutes = (
                    total_seconds % 3600
                ) // 60

                time_for_frontend = (
                    f"{hours:02d}:{minutes:02d}"
                )

            elif appointment_time:

                time_for_frontend = str(
                    appointment_time
                )[:5]

            else:

                time_for_frontend = ""

            # Status
            status_text = str(
                status or "Pending"
            )

            status_lower = (
                status_text.lower()
            )

            if status_lower == "pending":
                pending_count += 1

            elif status_lower == "confirmed":
                confirmed_count += 1

            elif status_lower == "completed":
                completed_count += 1

            elif status_lower == "cancelled":
                cancelled_count += 1

            # Today's appointments
            if date_for_frontend == today.strftime(
                "%Y-%m-%d"
            ):
                today_count += 1

            # Frontend-friendly fields
            normalized["id"] = appointment_id
            normalized["patient_number"] = patient_number
            normalized["patient_name"] = full_name
            normalized["full_name"] = full_name
            normalized["appointment_date"] = date_for_frontend
            normalized["appointment_time"] = time_for_frontend
            normalized["doctor"] = doctor
            normalized["doctor_name"] = doctor
            normalized["department"] = department
            normalized["status"] = status_text

            appointments_data.append(
                normalized
            )

        # Upcoming appointments
        upcoming_appointments = []

        for appointment in appointments_data:

            appointment_date = appointment.get(
                "appointment_date",
                ""
            )

            status = str(
                appointment.get(
                    "status",
                    ""
                )
            ).lower()

            if (
                appointment_date
                and appointment_date >= today.strftime("%Y-%m-%d")
                and status != "cancelled"
                and status != "completed"
            ):
                upcoming_appointments.append(
                    appointment
                )

        return safe_jsonify({
            "status": "success",
            "appointments": appointments_data,
            "upcoming_appointments": upcoming_appointments,
            "statistics": {
                "total_appointments": len(
                    appointments_data
                ),
                "today": today_count,
                "today_appointments": today_count,
                "pending": pending_count,
                "confirmed": confirmed_count,
                "completed": completed_count,
                "cancelled": cancelled_count
            }
        })

    except Exception as e:

        print(
            "GET APPOINTMENTS ERROR:",
            str(e)
        )

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "appointments": [],
            "upcoming_appointments": [],
            "statistics": {
                "total_appointments": 0,
                "today": 0,
                "today_appointments": 0,
                "pending": 0,
                "confirmed": 0,
                "completed": 0,
                "cancelled": 0
            }
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# SCHEDULE APPOINTMENT
# ============================================================

@app.route("/schedule-appointment", methods=["POST"])
def schedule_appointment():

    conn = None
    cursor = None

    try:

        data = request.get_json(
            silent=True
        ) or request.form

        patient_number = data.get(
            "patient_number",
            ""
        ).strip()

        appointment_date = data.get(
            "appointment_date",
            ""
        ).strip()

        appointment_time = data.get(
            "appointment_time",
            ""
        ).strip()

        doctor_name = data.get(
            "doctor_name",
            ""
        ).strip()

        department = data.get(
            "department",
            ""
        ).strip()

        status = data.get(
            "status",
            "Pending"
        ).strip()

        if not patient_number:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number is required."
            }, 400)

        if not appointment_date:

            return safe_jsonify({
                "status": "error",
                "message": "Appointment date is required."
            }, 400)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify patient
        cursor.execute(
            """
            SELECT Id
            FROM patients
            WHERE Patient_number = %s
            LIMIT 1
            """,
            (patient_number,)
        )

        patient = cursor.fetchone()

        if not patient:

            return safe_jsonify({
                "status": "error",
                "message": "Patient not found."
            }, 404)

        columns = get_table_columns(
            "appointments"
        )

        patient_column = find_column(
            columns,
            [
                "Patient_number",
                "patient_number"
            ]
        )

        date_column = find_column(
            columns,
            [
                "Appointment_date",
                "appointment_date"
            ]
        )

        time_column = find_column(
            columns,
            [
                "Appointment_time",
                "appointment_time"
            ]
        )

        doctor_column = find_column(
            columns,
            [
                "Doctor_name",
                "doctor_name"
            ]
        )

        department_column = find_column(
            columns,
            [
                "Department",
                "department"
            ]
        )

        status_column = find_column(
            columns,
            [
                "Status",
                "status",
                "Stutus",
                "stutus"
            ]
        )

        insert_columns = []
        values = []

        if patient_column:
            insert_columns.append(patient_column)
            values.append(patient_number)

        if date_column:
            insert_columns.append(date_column)
            values.append(appointment_date)

        if time_column:
            insert_columns.append(time_column)
            values.append(appointment_time or None)

        if doctor_column:
            insert_columns.append(doctor_column)
            values.append(doctor_name)

        if department_column:
            insert_columns.append(department_column)
            values.append(department)

        if status_column:
            insert_columns.append(status_column)
            values.append(status or "Pending")

        sql_columns = ", ".join(
            f"`{column}`"
            for column in insert_columns
        )

        placeholders = ", ".join(
            ["%s"] * len(values)
        )

        cursor.execute(
            f"""
            INSERT INTO appointments
            ({sql_columns})
            VALUES ({placeholders})
            """,
            tuple(values)
        )

        conn.commit()

        add_audit_log(
            "Appointment Scheduled",
            f"Appointment scheduled for {patient_number}",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Appointment successfully scheduled."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# UPDATE APPOINTMENT
# ============================================================

@app.route("/update-appointment", methods=["POST"])
def update_appointment():

    conn = None
    cursor = None

    try:

        data = request.get_json(
            silent=True
        ) or request.form

        appointment_id = data.get("id")

        if not appointment_id:

            return safe_jsonify({
                "status": "error",
                "message": "Appointment ID is required."
            }, 400)

        conn = get_db_connection()
        cursor = conn.cursor()

        columns = get_table_columns(
            "appointments"
        )

        id_column = find_column(
            columns,
            ["Id", "id"]
        )

        if not id_column:
            id_column = columns[0]

        updates = []
        values = []

        fields = [
            (
                "patient_number",
                [
                    "Patient_number",
                    "patient_number"
                ]
            ),
            (
                "appointment_date",
                [
                    "Appointment_date",
                    "appointment_date"
                ]
            ),
            (
                "appointment_time",
                [
                    "Appointment_time",
                    "appointment_time"
                ]
            ),
            (
                "doctor_name",
                [
                    "Doctor_name",
                    "doctor_name"
                ]
            ),
            (
                "department",
                [
                    "Department",
                    "department"
                ]
            ),
            (
                "status",
                [
                    "Status",
                    "status",
                    "Stutus",
                    "stutus"
                ]
            )
        ]

        for data_key, possible_columns in fields:

            if data_key in data:

                column = find_column(
                    columns,
                    possible_columns
                )

                if column:

                    updates.append(
                        f"`{column}` = %s"
                    )

                    values.append(
                        data.get(data_key)
                    )

        if not updates:

            return safe_jsonify({
                "status": "error",
                "message": "No appointment information was supplied."
            }, 400)

        values.append(appointment_id)

        cursor.execute(
            f"""
            UPDATE appointments
            SET {", ".join(updates)}
            WHERE `{id_column}` = %s
            """,
            tuple(values)
        )

        conn.commit()

        add_audit_log(
            "Appointment Updated",
            f"Appointment {appointment_id} was updated",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Appointment successfully updated."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# CANCEL APPOINTMENT
# ============================================================

@app.route("/cancel-appointment", methods=["POST"])
def cancel_appointment():

    conn = None
    cursor = None

    try:

        data = request.get_json(
            silent=True
        ) or request.form

        appointment_id = data.get("id")

        if not appointment_id:

            return safe_jsonify({
                "status": "error",
                "message": "Appointment ID is required."
            }, 400)

        conn = get_db_connection()
        cursor = conn.cursor()

        columns = get_table_columns(
            "appointments"
        )

        id_column = find_column(
            columns,
            ["Id", "id"]
        )

        status_column = find_column(
            columns,
            [
                "Status",
                "status",
                "Stutus",
                "stutus"
            ]
        )

        cursor.execute(
            f"""
            UPDATE appointments
            SET `{status_column}` = %s
            WHERE `{id_column}` = %s
            """,
            (
                "Cancelled",
                appointment_id
            )
        )

        conn.commit()

        add_audit_log(
            "Appointment Cancelled",
            f"Appointment {appointment_id} was cancelled",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Appointment successfully cancelled."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# AI PREDICTION PAGE
# ============================================================

@app.route("/ai-prediction")
@app.route("/ai_prediction.html")
def ai_prediction():
    return render_template("ai_prediction.html")


# ============================================================
# AI PREDICTION
# ============================================================

@app.route("/ai-predict", methods=["POST"])
def ai_predict():

    conn = None
    cursor = None

    try:

        data = request.get_json(
            silent=True
        ) or request.form

        patient_number = data.get(
            "patient_number",
            ""
        ).strip()

        symptoms = data.get(
            "symptoms",
            ""
        ).strip()

        if not patient_number:

            return safe_jsonify({
                "status": "error",
                "message": "Patient number is required."
            }, 400)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM patients
            WHERE Patient_number = %s
            LIMIT 1
            """,
            (patient_number,)
        )

        patient = cursor.fetchone()

        if not patient:

            return safe_jsonify({
                "status": "error",
                "message": "Patient not found."
            }, 404)

        # ----------------------------------------------------
        # Simple rule-based demonstration prediction
        # ----------------------------------------------------

        text = symptoms.lower()

        if (
            "fever" in text
            and (
                "cough" in text
                or "cold" in text
            )
        ):

            prediction = "Respiratory Infection"
            risk_level = "Medium"
            confidence = 82.00

        elif (
            "fever" in text
            or "headache" in text
            or "pain" in text
        ):

            prediction = "General Infection"
            risk_level = "Medium"
            confidence = 76.00

        elif (
            "chest pain" in text
            or "difficulty breathing" in text
        ):

            prediction = "Cardiovascular Risk"
            risk_level = "High"
            confidence = 88.00

        elif (
            "diabetes" in text
            or "excessive thirst" in text
            or "frequent urination" in text
        ):

            prediction = "Diabetes Risk"
            risk_level = "High"
            confidence = 86.00

        else:

            prediction = "General Infection"
            risk_level = "Low"
            confidence = 68.00

        if risk_level == "High":

            recommendations = (
                "Clinical review is recommended. "
                "Further medical assessment should be considered."
            )

        elif risk_level == "Medium":

            recommendations = (
                "Monitor symptoms and seek medical "
                "assessment if symptoms persist or worsen."
            )

        else:

            recommendations = (
                "Continue monitoring the patient's "
                "symptoms and maintain appropriate care."
            )

        # ----------------------------------------------------
        # Save prediction using ACTUAL table columns
        # ----------------------------------------------------

        cursor.close()

        columns = get_table_columns(
            "prediction_history"
        )

        conn.close()

        conn = get_db_connection()
        cursor = conn.cursor()

        patient_column = find_column(
            columns,
            [
                "Patient_number",
                "patient_number"
            ]
        )

        full_name_column = find_column(
            columns,
            [
                "Full_name",
                "full_name"
            ]
        )

        symptoms_column = find_column(
            columns,
            [
                "Symptoms",
                "symptoms"
            ]
        )

        disease_column = find_column(
            columns,
            [
                "Prediction_disease",
                "prediction_disease"
            ]
        )

        risk_column = find_column(
            columns,
            [
                "Risk_level",
                "risk_level"
            ]
        )

        confidence_column = find_column(
            columns,
            [
                "Confidence_score",
                "confidence_score"
            ]
        )

        recommendations_column = find_column(
            columns,
            [
                "Recommendations",
                "recommendations"
            ]
        )

        insert_columns = []
        values = []

        if patient_column:
            insert_columns.append(patient_column)
            values.append(patient_number)

        if full_name_column:
            insert_columns.append(full_name_column)
            values.append(patient.get("Full_name", ""))

        if symptoms_column:
            insert_columns.append(symptoms_column)
            values.append(symptoms)

        if disease_column:
            insert_columns.append(disease_column)
            values.append(prediction)

        if risk_column:
            insert_columns.append(risk_column)
            values.append(risk_level)

        if confidence_column:
            insert_columns.append(confidence_column)
            values.append(confidence)

        if recommendations_column:
            insert_columns.append(
                recommendations_column
            )
            values.append(recommendations)

        sql_columns = ", ".join(
            f"`{column}`"
            for column in insert_columns
        )

        placeholders = ", ".join(
            ["%s"] * len(values)
        )

        cursor.execute(
            f"""
            INSERT INTO prediction_history
            ({sql_columns})
            VALUES ({placeholders})
            """,
            tuple(values)
        )

        conn.commit()

        add_audit_log(
            "AI Prediction",
            f"AI prediction generated for {patient_number}",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "patient_number": patient_number,
            "patient_name": patient.get(
                "Full_name",
                ""
            ),
            "prediction": prediction,
            "prediction_disease": prediction,
            "risk_level": risk_level,
            "confidence": confidence,
            "confidence_score": confidence,
            "recommendations": recommendations
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# AI PREDICTION HISTORY
# ============================================================

@app.route("/ai-prediction-history")
def ai_prediction_history():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM prediction_history
            ORDER BY Id DESC
            """
        )

        records = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "records": records,
            "history": records
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "records": []
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# AI PREDICTION STATISTICS
# ============================================================

@app.route("/ai-prediction-stats")
def ai_prediction_stats():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                AVG(Confidence_score) AS average_confidence
            FROM prediction_history
            """
        )

        statistics = cursor.fetchone()

        cursor.execute(
            """
            SELECT
                Risk_level,
                COUNT(*) AS total
            FROM prediction_history
            GROUP BY Risk_level
            """
        )

        risk_distribution = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "statistics": statistics,
            "risk_distribution": risk_distribution
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# REPORTS PAGE
# ============================================================

@app.route("/reports")
@app.route("/reports.html")
def reports():
    return render_template("reports.html")


# ============================================================
# REPORTS DATA
# THIS IS THE CORRECTED VERSION
# ============================================================

@app.route("/reports-data")
def reports_data():

    conn = None
    cursor = None

    try:

        # Make sure support tables exist
        create_support_tables()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ----------------------------------------------------
        # TOTAL PATIENTS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM patients
            """
        )

        total_patients = (
            cursor.fetchone()["total"]
        )

        # ----------------------------------------------------
        # TOTAL MEDICAL RECORDS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM medical_records
            """
        )

        total_medical_records = (
            cursor.fetchone()["total"]
        )

        # ----------------------------------------------------
        # BIOMETRIC RECORDS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM biometric_records
            """
        )

        biometric_records = (
            cursor.fetchone()["total"]
        )

        # ----------------------------------------------------
        # AI RISK ASSESSMENTS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM prediction_history
            """
        )

        ai_risk_assessments = (
            cursor.fetchone()["total"]
        )

        # ----------------------------------------------------
        # BIOMETRIC VERIFICATIONS
        # ----------------------------------------------------

        biometric_verifications = biometric_records

        # ----------------------------------------------------
        # COMMON DIAGNOSES
        # Uses medical_records Diagnosis
        # ----------------------------------------------------

        medical_columns = get_table_columns(
            "medical_records"
        )

        diagnosis_column = find_column(
            medical_columns,
            [
                "Diagnosis",
                "diagnosis"
            ]
        )

        diagnoses = []

        if diagnosis_column:

            cursor.execute(
                f"""
                SELECT
                    `{diagnosis_column}` AS diagnosis,
                    COUNT(*) AS total
                FROM medical_records
                WHERE `{diagnosis_column}` IS NOT NULL
                AND `{diagnosis_column}` <> ''
                GROUP BY `{diagnosis_column}`
                ORDER BY total DESC
                """
            )

            diagnoses = cursor.fetchall()

        # ----------------------------------------------------
        # AI RISK DISTRIBUTION
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                Risk_level,
                COUNT(*) AS total
            FROM prediction_history
            WHERE Risk_level IS NOT NULL
            AND Risk_level <> ''
            GROUP BY Risk_level
            ORDER BY total DESC
            """
        )

        ai_risk_distribution = (
            cursor.fetchall()
        )

        # ----------------------------------------------------
        # APPOINTMENT PERFORMANCE
        # ----------------------------------------------------

        appointment_columns = get_table_columns(
            "appointments"
        )

        status_column = find_column(
            appointment_columns,
            [
                "Status",
                "status",
                "Stutus",
                "stutus"
            ]
        )

        appointments = {
            "Completed": 0,
            "Confirmed": 0,
            "Pending": 0,
            "Cancelled": 0
        }

        if status_column:

            cursor.execute(
                f"""
                SELECT
                    `{status_column}` AS status,
                    COUNT(*) AS total
                FROM appointments
                GROUP BY `{status_column}`
                """
            )

            appointment_rows = (
                cursor.fetchall()
            )

            for row in appointment_rows:

                status = str(
                    row.get("status", "")
                ).strip().lower()

                total = int(
                    row.get("total", 0)
                )

                if status == "completed":

                    appointments[
                        "Completed"
                    ] = total

                elif status == "confirmed":

                    appointments[
                        "Confirmed"
                    ] = total

                elif status == "pending":

                    appointments[
                        "Pending"
                    ] = total

                elif status == "cancelled":

                    appointments[
                        "Cancelled"
                    ] = total

        # ----------------------------------------------------
        # HIGH-RISK PATIENTS
        #
        # IMPORTANT:
        # The correct column is Prediction_disease,
        # NOT Disease_prediction.
        # ----------------------------------------------------

        cursor.execute(
            """
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
            WHERE LOWER(Risk_level) = 'high'
            ORDER BY Prediction_date DESC
            """
        )

        high_risk_patients = (
            cursor.fetchall()
        )

        # ----------------------------------------------------
        # AVERAGE AI CONFIDENCE
        # Correct column:
        # Confidence_score
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                AVG(Confidence_score) AS average_confidence
            FROM prediction_history
            WHERE Confidence_score IS NOT NULL
            """
        )

        average_result = (
            cursor.fetchone()
        )

        average_ai_confidence = (
            average_result.get(
                "average_confidence"
            )
            if average_result
            else 0
        )

        if average_ai_confidence is None:
            average_ai_confidence = 0

        average_ai_confidence = float(
            average_ai_confidence
        )

        # ----------------------------------------------------
        # APPOINTMENT COMPLETION RATE
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM appointments
            """
        )

        appointment_total = int(
            cursor.fetchone()["total"]
        )

        completed_appointments = (
            appointments["Completed"]
        )

        if appointment_total > 0:

            appointment_completion_rate = (
                completed_appointments
                / appointment_total
            ) * 100

        else:

            appointment_completion_rate = 0

        # ----------------------------------------------------
        # RETURN REPORT DATA
        # ----------------------------------------------------

        return safe_jsonify({

            "status": "success",

            "statistics": {
                "total_patients": total_patients,
                "total_medical_records": total_medical_records,
                "biometric_verifications": biometric_verifications,
                "ai_risk_assessments": ai_risk_assessments
            },

            "diagnoses": diagnoses,

            "ai_risk_distribution":
                ai_risk_distribution,

            "appointments":
                appointments,

            "high_risk_patients":
                high_risk_patients,

            "performance": {
                "biometric_records":
                    biometric_records,

                "average_ai_confidence":
                    average_ai_confidence,

                "appointment_completion_rate":
                    round(
                        appointment_completion_rate,
                        2
                    )
            }

        })

    except Exception as e:

        print(
            "REPORTS DATA ERROR:",
            str(e)
        )

        return safe_jsonify({

            "status": "error",

            "message": str(e),

            "statistics": {
                "total_patients": 0,
                "total_medical_records": 0,
                "biometric_verifications": 0,
                "ai_risk_assessments": 0
            },

            "diagnoses": [],

            "ai_risk_distribution": [],

            "appointments": {
                "Completed": 0,
                "Confirmed": 0,
                "Pending": 0,
                "Cancelled": 0
            },

            "high_risk_patients": [],

            "performance": {
                "biometric_records": 0,
                "average_ai_confidence": 0,
                "appointment_completion_rate": 0
            }

        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# USERS PAGE
# ============================================================

@app.route("/users")
@app.route("/users.html")
def users():
    return render_template("users.html")


# ============================================================
# GET USERS
# ============================================================

@app.route("/get-users")
def get_users():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                Id,
                Full_name,
                Username,
                Email,
                Role
            FROM users
            ORDER BY Id DESC
            """
        )

        users_data = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "users": users_data
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "users": []
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# CREATE USER
# ============================================================

@app.route("/create-user", methods=["POST"])
def create_user():

    conn = None
    cursor = None

    try:

        data = request.get_json(
            silent=True
        ) or request.form

        full_name = data.get(
            "full_name",
            ""
        ).strip()

        username = data.get(
            "username",
            ""
        ).strip()

        email = data.get(
            "email",
            ""
        ).strip()

        password = data.get(
            "password",
            ""
        )

        role = data.get(
            "role",
            "User"
        ).strip()

        if not full_name or not username or not password:

            return safe_jsonify({
                "status": "error",
                "message": "Full name, username and password are required."
            }, 400)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users
            (
                Full_name,
                Username,
                Email,
                Password,
                Role
            )
            VALUES (%s,%s,%s,%s,%s)
            """,
            (
                full_name,
                username,
                email,
                password,
                role
            )
        )

        conn.commit()

        add_audit_log(
            "User Created",
            f"Created system user {username}",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "User successfully created."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# SETTINGS PAGE
# ============================================================

@app.route("/settings")
@app.route("/settings.html")
def settings():
    return render_template("settings.html")


# ============================================================
# SETTINGS DATA
# ============================================================

@app.route("/settings-data")
def settings_data():

    conn = None
    cursor = None

    try:

        create_support_tables()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM system_settings
            ORDER BY Id ASC
            """
        )

        settings_data = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "settings": settings_data
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "settings": []
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# SAVE SETTINGS
# ============================================================

@app.route("/save-settings", methods=["POST"])
def save_settings():

    conn = None
    cursor = None

    try:

        create_support_tables()

        data = request.get_json(
            silent=True
        ) or request.form

        conn = get_db_connection()
        cursor = conn.cursor()

        if hasattr(data, "items"):

            for setting_name, setting_value in data.items():

                cursor.execute(
                    """
                    INSERT INTO system_settings
                    (
                        Setting_name,
                        Setting_value
                    )
                    VALUES (%s,%s)
                    ON DUPLICATE KEY UPDATE
                    Setting_value = VALUES(Setting_value)
                    """,
                    (
                        setting_name,
                        setting_value
                    )
                )

        conn.commit()

        add_audit_log(
            "Settings Updated",
            "System settings were updated",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Settings successfully saved."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# SYSTEM STATUS
# ============================================================

@app.route("/system-status")
def system_status():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1"
        )

        cursor.fetchone()

        return safe_jsonify({
            "status": "success",
            "database": "Operational",
            "flask": "Operational",
            "deepface": (
                "Available"
                if DEEPFACE_AVAILABLE
                else "Not Available"
            )
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "database": "Unavailable",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# AUDIT LOGS
# ============================================================

@app.route("/audit-logs")
def audit_logs():

    conn = None
    cursor = None

    try:

        create_support_tables()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM system_audit_logs
            ORDER BY Id DESC
            LIMIT 200
            """
        )

        logs = cursor.fetchall()

        return safe_jsonify({
            "status": "success",
            "logs": logs
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e),
            "logs": []
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# CLEAR AUDIT LOGS
# ============================================================

@app.route("/clear-audit-logs", methods=["POST"])
def clear_audit_logs():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM system_audit_logs"
        )

        conn.commit()

        return safe_jsonify({
            "status": "success",
            "message": "Audit logs successfully cleared."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# DATABASE BACKUP
# ============================================================

@app.route("/create-backup", methods=["POST", "GET"])
def create_backup():

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"biometric_healthcare_backup_{timestamp}.sql"
    )

    backup_path = os.path.join(
        BACKUP_FOLDER,
        filename
    )

    try:

        command = [
            "mysqldump",
            "-h",
            DB_CONFIG["host"],
            "-u",
            DB_CONFIG["user"],
            DB_CONFIG["database"]
        ]

        with open(
            backup_path,
            "w",
            encoding="utf-8"
        ) as backup_file:

            result = subprocess.run(
                command,
                stdout=backup_file,
                stderr=subprocess.PIPE,
                text=True
            )

        if result.returncode != 0:

            return safe_jsonify({
                "status": "error",
                "message": result.stderr
            }, 500)

        add_audit_log(
            "Database Backup",
            f"Created database backup {filename}",
            session.get("username", "System")
        )

        return safe_jsonify({
            "status": "success",
            "message": "Database backup successfully created.",
            "filename": filename
        })

    except Exception as e:

        return safe_jsonify({
            "status": "error",
            "message": str(e)
        }, 500)


# ============================================================
# DOWNLOAD BACKUP
# ============================================================

@app.route("/download-backup/<filename>")
def download_backup(filename):

    safe_filename = secure_filename(
        filename
    )

    backup_path = os.path.join(
        BACKUP_FOLDER,
        safe_filename
    )

    if not os.path.exists(backup_path):

        return safe_jsonify({
            "status": "error",
            "message": "Backup file not found."
        }, 404)

    return send_file(
        backup_path,
        as_attachment=True
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return safe_jsonify({
        "status": "error",
        "message": "Page or endpoint not found."
    }, 404)


@app.errorhandler(500)
def internal_server_error(error):

    return safe_jsonify({
        "status": "error",
        "message": "Internal server error."
    }, 500)


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("INTELLIGENT BIOMETRIC HEALTHCARE SYSTEM")
    print("=" * 60)
    print("Database: biometric_healthcare")
    print("Server: http://localhost:5000")
    print("Debug: OFF")
    print("=" * 60)

    try:
        create_support_tables()
        print("Database support tables checked successfully.")
    except Exception as e:
        print("Startup database check:", e)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
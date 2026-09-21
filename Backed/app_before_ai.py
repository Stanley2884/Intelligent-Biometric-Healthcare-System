from flask import Flask, request, jsonify, render_template
import mysql.connector
import os
from werkzeug.utils import secure_filename


# ============================================================
# INTELLIGENT BIOMETRIC HEALTHCARE SYSTEM
# MASTER FLASK BACKEND
# ============================================================

app = Flask(__name__, template_folder="Templetes")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="biometric_healthcare"
    )


# ============================================================
# UPLOAD CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Main project folder:
# C:\xampp\htdocs\Biometric System
PROJECT_DIR = os.path.dirname(BASE_DIR)

# Photos will be stored here:
# C:\xampp\htdocs\Biometric System\Uploads
UPLOAD_FOLDER = os.path.join(PROJECT_DIR, "Uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Intelligent Biometric Healthcare System</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                text-align: center;
                padding-top: 80px;
            }

            h1 {
                color: #1f2937;
            }

            p {
                color: #555;
            }

            a {
                display: inline-block;
                margin: 10px;
                padding: 12px 20px;
                background: #2563eb;
                color: white;
                text-decoration: none;
                border-radius: 6px;
            }

            a:hover {
                background: #1d4ed8;
            }
        </style>
    </head>

    <body>

        <h1>Intelligent Biometric Healthcare System</h1>

        <p>Backend is Running Successfully</p>

        <a href="/patient-registration">
            Patient Registration
        </a>

        <a href="/biometric">
            Biometric Registration
        </a>

    </body>
    </html>
    """


# ============================================================
# DATABASE TEST
# ============================================================

@app.route("/test-db")
def test_db():

    try:

        connection = get_db_connection()

        connection.close()

        return jsonify({
            "success": True,
            "message": "Database connection successful."
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        })


# ============================================================
# PATIENT REGISTRATION PAGE
# ============================================================

@app.route("/patient-registration")
def patient_registration():

    return render_template("patient_registration.html")


# ============================================================
# REGISTER PATIENT
# ============================================================

@app.route("/register-patient", methods=["POST"])
def register_patient():

    connection = None
    cursor = None

    try:

        patient_number = request.form.get("patient_number")
        full_name = request.form.get("full_name")
        date_of_birth = request.form.get("date_of_birth")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        address = request.form.get("address")
        biometric_id = request.form.get("biometric_id")
        medical_history = request.form.get("medical_history")


        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        if not patient_number or not full_name:

            return jsonify({
                "success": False,
                "message": "Patient number and full name are required."
            })


        connection = get_db_connection()

        cursor = connection.cursor()


        # ----------------------------------------------------
        # Insert patient
        # ----------------------------------------------------

        query = """
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """


        values = (
            patient_number,
            full_name,
            date_of_birth,
            gender,
            phone,
            address,
            biometric_id,
            medical_history
        )


        cursor.execute(query, values)

        connection.commit()


        return jsonify({
            "success": True,
            "message": "Patient successfully registered."
        })


    except mysql.connector.Error as e:

        if connection:
            connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error: " + str(e)
        })


    except Exception as e:

        if connection:
            connection.rollback()

        return jsonify({
            "success": False,
            "message": "Error: " + str(e)
        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# BIOMETRIC PAGE
# ============================================================

@app.route("/biometric")
def biometric():

    return render_template("biometric.html")


# ============================================================
# GET ALL REGISTERED PATIENTS
# ============================================================

@app.route("/get-patients")
def get_patients():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)


        query = """
        SELECT
            Patient_number,
            Full_name
        FROM patients
        ORDER BY Id ASC
        """


        cursor.execute(query)

        patients = cursor.fetchall()


        return jsonify({
            "success": True,
            "patients": patients
        })


    except mysql.connector.Error as e:

        return jsonify({
            "success": False,
            "message": "Database error: " + str(e)
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Error: " + str(e)
        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# REGISTER FACIAL BIOMETRIC
# ============================================================

@app.route("/register-biometric", methods=["POST"])
def register_biometric():

    connection = None
    cursor = None

    try:

        # ----------------------------------------------------
        # Get selected patient
        # ----------------------------------------------------

        patient_number = request.form.get("patient_number")


        if not patient_number:

            return jsonify({
                "success": False,
                "message": "Please select a patient."
            })


        # ----------------------------------------------------
        # Get uploaded photo
        # ----------------------------------------------------

        if "face_image" not in request.files:

            return jsonify({
                "success": False,
                "message": "Please select a facial photo."
            })


        file = request.files["face_image"]


        if file.filename == "":

            return jsonify({
                "success": False,
                "message": "Please select a facial photo."
            })


        # ----------------------------------------------------
        # Check image type
        # ----------------------------------------------------

        if not allowed_file(file.filename):

            return jsonify({
                "success": False,
                "message": "Only JPG, JPEG and PNG images are allowed."
            })


        # ----------------------------------------------------
        # Database connection
        # ----------------------------------------------------

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)


        # ----------------------------------------------------
        # Check patient exists
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                Patient_number,
                Full_name
            FROM patients
            WHERE Patient_number = %s
            """,
            (patient_number,)
        )


        patient = cursor.fetchone()


        if not patient:

            return jsonify({
                "success": False,
                "message": "Selected patient does not exist."
            })


        # ----------------------------------------------------
        # Create safe filename
        # ----------------------------------------------------

        original_filename = secure_filename(file.filename)

        extension = original_filename.rsplit(".", 1)[1].lower()

        filename = patient_number + "_face." + extension


        # ----------------------------------------------------
        # Full photo path
        # ----------------------------------------------------

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )


        # ----------------------------------------------------
        # Save photo
        # ----------------------------------------------------

        file.save(filepath)


        # ----------------------------------------------------
        # Check existing biometric record
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT Id
            FROM biometric_records
            WHERE Patient_number = %s
            AND Biometric_type = %s
            """,
            (patient_number, "Face")
        )


        existing_record = cursor.fetchone()


        # ----------------------------------------------------
        # Update existing FACE record
        # ----------------------------------------------------

        if existing_record:

            cursor.execute(
                """
                UPDATE biometric_records
                SET
                    Biometric_data = %s,
                    Capture_dates = CURRENT_TIMESTAMP,
                    Verification_status = %s,
                    Notes = %s
                WHERE Id = %s
                """,
                (
                    filename,
                    "Registered",
                    "Facial biometric updated successfully.",
                    existing_record["Id"]
                )
            )


        # ----------------------------------------------------
        # Create new FACE record
        # ----------------------------------------------------

        else:

            cursor.execute(
                """
                INSERT INTO biometric_records
                (
                    Patient_number,
                    Biometric_type,
                    Biometric_data,
                    Capture_dates,
                    Verification_status,
                    Notes
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    CURRENT_TIMESTAMP,
                    %s,
                    %s
                )
                """,
                (
                    patient_number,
                    "Face",
                    filename,
                    "Registered",
                    "Facial biometric registered successfully."
                )
            )


        connection.commit()


        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        return jsonify({
            "success": True,
            "message": "Facial biometric registered successfully.",
            "patient_number": patient_number,
            "full_name": patient["Full_name"],
            "filename": filename
        })


    except mysql.connector.Error as e:

        if connection:
            connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error: " + str(e)
        })


    except Exception as e:

        if connection:
            connection.rollback()

        return jsonify({
            "success": False,
            "message": "Error: " + str(e)
        })


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# START FLASK SERVER
# ============================================================

if __name__ == "__main__":

    print("--------------------------------------------")
    print(" INTELLIGENT BIOMETRIC HEALTHCARE SYSTEM")
    print("--------------------------------------------")
    print("Database : biometric_healthcare")
    print("Server   : http://localhost:5000")
    print("--------------------------------------------")

    app.run(
        host="localhost",
        port=5000,
        debug=False
    )
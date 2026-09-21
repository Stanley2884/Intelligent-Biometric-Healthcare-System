from flask import Flask, request, jsonify, render_template
import mysql.connector
import os
import uuid
from werkzeug.utils import secure_filename
from deepface import DeepFace


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__, template_folder="Templetes")


# =========================================================
# CONFIGURATION
# =========================================================

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# MYSQL DATABASE CONNECTION
# =========================================================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="biometric_healthcare"
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return """
    <h1>Intelligent Biometric Healthcare System</h1>
    <p>Backend is Running Successfully</p>
    <p>AI Facial Recognition: Ready</p>
    """


# =========================================================
# DATABASE TEST
# =========================================================

@app.route("/test-db")
def test_db():

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        cursor.close()
        db.close()

        return jsonify({
            "status": "success",
            "message": "MySQL database connected successfully",
            "result": result
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard():
    return render_template("dashboard.html")


# =========================================================
# PATIENT REGISTRATION PAGE
# =========================================================

@app.route("/patient-registration")
@app.route("/patient_registration.html")
def patient_registration():
    return render_template("patient_registration.html")


# =========================================================
# REGISTER PATIENT
# =========================================================

@app.route("/register-patient", methods=["POST"])
def register_patient():

    db = None
    cursor = None

    try:

        # Accept JSON or normal form submission
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form

        # Read submitted information
        patient_number = str(
            data.get("Patient_number", "")
        ).strip()

        full_name = str(
            data.get("Full_name", "")
        ).strip()

        date_of_birth = str(
            data.get("Date_of_birth", "")
        ).strip()

        gender = str(
            data.get("Gender", "")
        ).strip()

        phone = str(
            data.get("Phone", "")
        ).strip()

        biometric_id = str(
            data.get("Biometric_id", "")
        ).strip()

        address = str(
            data.get("Address", "")
        ).strip()

        medical_history = str(
            data.get("Medical_history", "")
        ).strip()


        # =================================================
        # VALIDATION
        # =================================================

        if not patient_number:

            return jsonify({
                "status": "error",
                "success": False,
                "message": "Patient number is required."
            }), 400


        if not full_name:

            return jsonify({
                "status": "error",
                "success": False,
                "message": "Full name is required."
            }), 400


        if not date_of_birth:

            return jsonify({
                "status": "error",
                "success": False,
                "message": "Date of birth is required."
            }), 400


        if not gender:

            return jsonify({
                "status": "error",
                "success": False,
                "message": "Gender is required."
            }), 400


        # =================================================
        # CONNECT TO MYSQL
        # =================================================

        db = get_db_connection()

        cursor = db.cursor()


        # =================================================
        # CHECK DUPLICATE PATIENT NUMBER
        # =================================================

        cursor.execute(
            """
            SELECT Id
            FROM patients
            WHERE Patient_number = %s
            """,
            (patient_number,)
        )

        existing_patient = cursor.fetchone()


        if existing_patient:

            cursor.close()
            db.close()

            return jsonify({
                "status": "error",
                "success": False,
                "message": "Patient number already exists."
            }), 409


        # =================================================
        # INSERT PATIENT
        # =================================================

        sql = """
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
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
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


        cursor.execute(sql, values)


        # =================================================
        # SAVE PERMANENTLY
        # =================================================

        db.commit()


        inserted_id = cursor.lastrowid


        cursor.close()
        db.close()


        # =================================================
        # SUCCESS
        # =================================================

        return jsonify({
            "status": "success",
            "success": True,
            "message": "Patient successfully registered.",
            "patient": {
                "id": inserted_id,
                "patient_number": patient_number,
                "full_name": full_name
            }
        })


    except Exception as e:

        if db:

            try:
                db.rollback()
            except:
                pass


        if cursor:

            try:
                cursor.close()
            except:
                pass


        if db:

            try:
                db.close()
            except:
                pass


        print(
            "PATIENT REGISTRATION ERROR:",
            str(e)
        )


        return jsonify({
            "status": "error",
            "success": False,
            "message": "Patient registration failed.",
            "error": str(e)
        }), 500


# =========================================================
# PATIENTS PAGE
# =========================================================

@app.route("/patients")
@app.route("/patients.html")
def patients():
    return render_template("patients.html")


# =========================================================
# GET PATIENTS FROM MYSQL
# =========================================================

@app.route("/get-patients", methods=["GET"])
def get_patients():

    db = None
    cursor = None

    try:

        db = get_db_connection()

        cursor = db.cursor(
            dictionary=True
        )


        cursor.execute(
            """
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
            """
        )


        patients_data = cursor.fetchall()


        cursor.close()
        db.close()


        return jsonify(patients_data)


    except Exception as e:

        if cursor:

            cursor.close()

        if db:

            db.close()


        return jsonify({
            "status": "error",
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# BIOMETRIC PAGE
# =========================================================

@app.route("/biometric")
@app.route("/biometric.html")
def biometric():
    return render_template("biometric.html")


# =========================================================
# REGISTER BIOMETRIC
# =========================================================

@app.route("/register-biometric", methods=["POST"])
def register_biometric():

    db = None
    cursor = None
    saved_file = None

    try:

        patient_number = request.form.get(
            "patient_number",
            ""
        ).strip()

        biometric_type = request.form.get(
            "biometric_type",
            "Face"
        ).strip()

        notes = request.form.get(
            "notes",
            ""
        ).strip()

        uploaded_file = request.files.get(
            "biometric_file"
        )


        if not patient_number:

            return jsonify({
                "status": "error",
                "message": "Patient number is required."
            }), 400


        if not uploaded_file:

            return jsonify({
                "status": "error",
                "message": "Biometric image is required."
            }), 400


        # =================================================
        # FIND PATIENT
        # =================================================

        db = get_db_connection()

        cursor = db.cursor(
            dictionary=True
        )


        cursor.execute(
            """
            SELECT *
            FROM patients
            WHERE Patient_number = %s
            """,
            (patient_number,)
        )


        patient = cursor.fetchone()


        if not patient:

            cursor.close()
            db.close()

            return jsonify({
                "status": "error",
                "message": "Patient not found."
            }), 404


        # =================================================
        # SAVE IMAGE
        # =================================================

        original_name = secure_filename(
            uploaded_file.filename
        )

        extension = os.path.splitext(
            original_name
        )[1]


        if not extension:
            extension = ".jpg"


        filename = (
            patient_number
            + "_face_"
            + uuid.uuid4().hex
            + extension
        )


        saved_file = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )


        uploaded_file.save(saved_file)


        # =================================================
        # AI FACE PROCESSING
        # =================================================

        if biometric_type.lower() == "face":

            DeepFace.represent(
                img_path=saved_file,
                model_name="Facenet512",
                detector_backend="retinaface",
                enforce_detection=True
            )


        # =================================================
        # SAVE BIOMETRIC RECORD
        # =================================================

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
                NOW(),
                %s,
                %s
            )
            """,
            (
                patient_number,
                biometric_type,
                filename,
                "Verified",
                notes
            )
        )


        # =================================================
        # UPDATE PATIENT BIOMETRIC ID
        # =================================================

        cursor.execute(
            """
            UPDATE patients
            SET Biometric_id = %s
            WHERE Patient_number = %s
            """,
            (
                filename,
                patient_number
            )
        )


        db.commit()


        cursor.close()
        db.close()


        return jsonify({
            "status": "success",
            "message": "Biometric registered successfully.",
            "patient_number": patient_number,
            "biometric_file": filename
        })


    except Exception as e:

        if db:

            try:
                db.rollback()
            except:
                pass


        if cursor:

            try:
                cursor.close()
            except:
                pass


        if db:

            try:
                db.close()
            except:
                pass


        if saved_file and os.path.exists(
            saved_file
        ):

            try:
                os.remove(saved_file)
            except:
                pass


        print(
            "BIOMETRIC ERROR:",
            str(e)
        )


        return jsonify({
            "status": "error",
            "message": "Biometric registration failed.",
            "error": str(e)
        }), 500


# =========================================================
# AI FACIAL RECOGNITION
# =========================================================

@app.route("/recognize-face", methods=["POST"])
def recognize_face():

    db = None
    cursor = None
    temporary_file = None

    try:

        uploaded_file = request.files.get("face")


        if not uploaded_file:

            return jsonify({
                "status": "error",
                "message": "Face image is required."
            }), 400


        extension = os.path.splitext(
            secure_filename(
                uploaded_file.filename
            )
        )[1]


        if not extension:
            extension = ".jpg"


        temporary_filename = (
            "recognition_"
            + uuid.uuid4().hex
            + extension
        )


        temporary_file = os.path.join(
            app.config["UPLOAD_FOLDER"],
            temporary_filename
        )


        uploaded_file.save(
            temporary_file
        )


        # =================================================
        # GET REGISTERED FACE RECORDS
        # =================================================

        db = get_db_connection()

        cursor = db.cursor(
            dictionary=True
        )


        cursor.execute(
            """
            SELECT
                b.Patient_number,
                b.Biometric_data,
                p.Full_name,
                p.Date_of_birth,
                p.Gender,
                p.Phone,
                p.Address,
                p.Medical_history
            FROM biometric_records b
            INNER JOIN patients p
                ON b.Patient_number =
                   p.Patient_number
            WHERE b.Biometric_type = 'Face'
            """
        )


        records = cursor.fetchall()


        if not records:

            return jsonify({
                "status": "error",
                "message": "No registered face biometrics found."
            }), 404


        matches = []


        # =================================================
        # COMPARE FACES
        # =================================================

        for record in records:

            registered_filename = (
                record["Biometric_data"]
            )


            registered_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                registered_filename
            )


            if not os.path.exists(
                registered_path
            ):
                continue


            try:

                verification = DeepFace.verify(
                    img1_path=temporary_file,
                    img2_path=registered_path,
                    model_name="Facenet512",
                    detector_backend="retinaface",
                    enforce_detection=False
                )


                distance = verification.get(
                    "distance",
                    999
                )


                threshold = verification.get(
                    "threshold",
                    0.3
                )


                verified = verification.get(
                    "verified",
                    False
                )


                matches.append({
                    "verified": verified,
                    "distance": distance,
                    "threshold": threshold,
                    "patient": record
                })


            except Exception as comparison_error:

                print(
                    "FACE COMPARISON ERROR:",
                    comparison_error
                )


        if not matches:

            return jsonify({
                "status": "error",
                "message": "No face could be compared."
            }), 404


        matches.sort(
            key=lambda x: x["distance"]
        )


        best_match = matches[0]

        patient = best_match["patient"]


        if not best_match["verified"]:

            return jsonify({
                "status": "error",
                "message": "Patient could not be identified.",
                "distance": best_match["distance"],
                "threshold": best_match["threshold"]
            }), 404


        result = {
            "patient_number":
                patient["Patient_number"],

            "full_name":
                patient["Full_name"],

            "date_of_birth":
                patient["Date_of_birth"],

            "gender":
                patient["Gender"],

            "phone":
                patient["Phone"],

            "address":
                patient["Address"],

            "medical_history":
                patient["Medical_history"],

            "distance":
                best_match["distance"],

            "threshold":
                best_match["threshold"]
        }


        return jsonify({
            "status": "success",
            "message": "Patient identified successfully.",
            "patient": result
        })


    except Exception as e:

        print(
            "FACE RECOGNITION ERROR:",
            str(e)
        )


        return jsonify({
            "status": "error",
            "message": "Face recognition failed.",
            "error": str(e)
        }), 500


    finally:

        if cursor:

            try:
                cursor.close()
            except:
                pass


        if db:

            try:
                db.close()
            except:
                pass


        if temporary_file and os.path.exists(
            temporary_file
        ):

            try:
                os.remove(
                    temporary_file
                )
            except:
                pass


# =========================================================
# OTHER SYSTEM PAGES
# =========================================================

@app.route("/medical-records")
@app.route("/medical_records.html")
def medical_records():
    return render_template(
        "medical_records.html"
    )


@app.route("/appointments")
@app.route("/appointments.html")
def appointments():
    return render_template(
        "appointments.html"
    )


@app.route("/ai-prediction")
@app.route("/ai_prediction.html")
def ai_prediction():
    return render_template(
        "ai_prediction.html"
    )


@app.route("/reports")
@app.route("/reports.html")
def reports():
    return render_template(
        "reports.html"
    )


@app.route("/users")
@app.route("/users.html")
def users():
    return render_template(
        "users.html"
    )


@app.route("/settings")
@app.route("/settings.html")
def settings():
    return render_template(
        "settings.html"
    )


@app.route("/login")
@app.route("/login.html")
def login():
    return render_template(
        "login.html"
    )


# =========================================================
# START FLASK
# =========================================================

if __name__ == "__main__":

    print("=" * 60)
    print(
        "INTELLIGENT BIOMETRIC HEALTHCARE SYSTEM"
    )
    print(
        "Flask Backend Starting..."
    )
    print(
        "AI Facial Recognition: Ready"
    )
    print("=" * 60)


    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
from flask import Flask, request, jsonify, render_template
import mysql.connector

app = Flask(__name__)


# -------------------------------------------------
# MYSQL DATABASE CONNECTION
# -------------------------------------------------

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="biometric_healthcare"
    )


# -------------------------------------------------
# HOME PAGE
# -------------------------------------------------

@app.route("/")
def home():
    return """
    <h1>Intelligent Biometric Healthcare System</h1>
    <p>Patient Registration Backend is Running Successfully.</p>
    """


# -------------------------------------------------
# PATIENT REGISTRATION PAGE
# -------------------------------------------------

@app.route("/patient-registration")
def patient_registration():
    return render_template("patient_registration.html")


# -------------------------------------------------
# SAVE PATIENT TO MYSQL
# -------------------------------------------------

@app.route("/register-patient", methods=["POST"])
def register_patient():

    try:

        patient_number = request.form.get("patient_number")
        full_name = request.form.get("full_name")
        date_of_birth = request.form.get("date_of_birth")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        address = request.form.get("address")
        biometric_id = request.form.get("biometric_id")
        medical_history = request.form.get("medical_history")

        # Check required fields
        if not all([
            patient_number,
            full_name,
            date_of_birth,
            gender,
            phone,
            address,
            biometric_id,
            medical_history
        ]):
            return jsonify({
                "success": False,
                "message": "Please fill in all required fields."
            }), 400

        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()

        # Insert patient
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

        cursor.execute(sql, values)

        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            "success": True,
            "message": "Patient registered successfully."
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error: " + str(error)
        }), 500

    except Exception as error:

        return jsonify({
            "success": False,
            "message": "Error: " + str(error)
        }), 500


# -------------------------------------------------
# RUN APPLICATION
# -------------------------------------------------

if __name__ == "__main__":

    print("----------------------------------------")
    print("Patient Registration Backend")
    print("Database: biometric_healthcare")
    print("Server: http://localhost:5000")
    print("----------------------------------------")

    app.run(
        host="localhost",
        port=5000,
        debug=False
    )
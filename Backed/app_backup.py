from flask import Flask
import mysql.connector

app = Flask(__name__)


# ==============================
# DATABASE CONNECTION
# ==============================
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="biometric_healthcare"
    )


# ==============================
# HOME PAGE
# ==============================
@app.route("/")
def home():
    return """
    <h1>Intelligent Biometric Healthcare Action System</h1>
    <p>Backend is running successfully.</p>

    <a href="/test-db">
        Click here to Test Database Connection
    </a>
    """


# ==============================
# TEST DATABASE CONNECTION
# ==============================
@app.route("/test-db")
def test_db():
    try:
        connection = get_db_connection()

        if connection.is_connected():
            connection.close()
            return """
            <h2>Database connection successful!</h2>
            <p>Flask is successfully connected to the
            <strong>biometric_healthcare</strong> database.</p>

            <a href="/">Back to Home</a>
            """

    except mysql.connector.Error as error:
        return f"""
        <h2>Database connection failed</h2>
        <p>{error}</p>

        <a href="/">Back to Home</a>
        """


# ==============================
# RUN FLASK APPLICATION
# ==============================
if __name__ == "__main__":
    app.run(debug=True)
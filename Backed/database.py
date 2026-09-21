import pymysql

def get_database_connection():
    return pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="",
        database="biometric_healthcare",
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor
    )

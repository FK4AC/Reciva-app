import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG


def get_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"Error de conexión: {e}")
        return None

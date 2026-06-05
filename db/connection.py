import pymysql
import time
from config import DB_CONFIG

# Si una conexión falló, no reintentamos hasta pasado este tiempo (segundos).
# Evita esperar 10s por pantalla cuando ya sabemos que no hay internet.
_last_failure = 0.0
_COOLDOWN = 30.0


def get_connection():
    global _last_failure
    now = time.time()
    if _last_failure and (now - _last_failure) < _COOLDOWN:
        return None
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            ssl=DB_CONFIG['ssl'],
            connect_timeout=10,
        )
        _last_failure = 0.0
        return conn
    except Exception as e:
        _last_failure = time.time()
        print(f"Error de conexión: {e}")
        return None


def reset_cooldown():
    """Fuerza un reintento real en la siguiente llamada a get_connection()."""
    global _last_failure
    _last_failure = 0.0

from db.connection import get_connection

conn = get_connection()
if conn:
    print("Conexión exitosa a reciva_db")
    conn.close()
else:
    print("Error al conectar")

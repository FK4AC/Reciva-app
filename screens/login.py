from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
import hashlib

class LoginScreen(Screen):
    error_msg = StringProperty('')

    def do_login(self, email, password):
        if not email or not password:
            self.error_msg = 'Completa todos los campos'
            return

        from db.connection import get_connection
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_connection()

        if not conn:
            self.error_msg = 'Error de conexión'
            return

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM usuarios WHERE email=%s AND password=%s AND activo=1",
            (email, password_hash)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            self.error_msg = ''
            self.manager.app.current_user = user
            self.manager.current = 'dashboard'
        else:
            self.error_msg = 'Correo o contraseña incorrectos'
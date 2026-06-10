from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.app import App
import hashlib
import threading
import pymysql.cursors
import utils.overlay as overlay


class LoginScreen(Screen):
    error_msg = StringProperty('')

    def do_login(self, email, password):
        if not email or not password:
            self.error_msg = 'Completa todos los campos'
            return
        overlay.show('Iniciando sesión…')

        def _tarea():
            from db.connection import get_connection
            conn = get_connection()
            if not conn:
                Clock.schedule_once(lambda *_: self._sin_conexion(), 0)
                return
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            try:
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                cursor.execute(
                    "SELECT * FROM usuarios WHERE email=%s AND password=%s AND activo=1",
                    (email, password_hash)
                )
                user = cursor.fetchone()
            except Exception:
                user = None
            finally:
                cursor.close()
                conn.close()
            Clock.schedule_once(lambda *_: self._aplicar(user), 0)

        threading.Thread(target=_tarea, daemon=True).start()

    def _aplicar(self, user):
        overlay.hide()
        if user:
            self.error_msg = ''
            app = self.manager.app
            app.current_user = user
            app.user_rol = user.get('rol', 'operador')
            app.usuario_nombre = user.get('nombre', '')
            # operador va directo a tickets, los demás al dashboard
            app.root.current = 'tickets' if app.user_rol == 'operador' else 'dashboard'
        else:
            self.error_msg = 'Correo o contraseña incorrectos'

    def _sin_conexion(self):
        overlay.hide()
        App.get_running_app().ir_sin_conexion('login')

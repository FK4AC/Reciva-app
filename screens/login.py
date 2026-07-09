from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.app import App
import hashlib
import threading
import pymysql.cursors
import utils.overlay as overlay
from utils.permisos import setup_tablas_roles, cargar_permisos
from utils.session import guardar_sesion, cargar_sesion


class LoginScreen(Screen):
    error_msg = StringProperty('')

    def on_enter(self):
        Clock.schedule_once(self._check_sesion, 0)

    def _check_sesion(self, *_):
        sesion = cargar_sesion()
        if sesion:
            overlay.show('Reanudando sesión…')
            threading.Thread(
                target=lambda: self._auto_login(sesion), daemon=True
            ).start()

    def _auto_login(self, sesion):
        from db.connection import get_connection
        conn = get_connection()
        if not conn:
            Clock.schedule_once(lambda *_: overlay.hide(), 0)
            return
        user, permisos = None, None
        try:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            setup_tablas_roles(conn)
            cursor.execute(
                "SELECT * FROM usuarios WHERE id=%s AND activo=1",
                (sesion['id'],)
            )
            user = cursor.fetchone()
            if user:
                permisos = cargar_permisos(conn, user.get('rol', 'operador'))
            cursor.close()
        except Exception:
            user = None
        finally:
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar(user, permisos, auto=True), 0)

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
            user = None
            permisos = None
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            try:
                setup_tablas_roles(conn)
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                cursor.execute(
                    "SELECT * FROM usuarios WHERE email=%s AND password=%s AND activo=1",
                    (email, password_hash)
                )
                user = cursor.fetchone()
                if user:
                    permisos = cargar_permisos(conn, user.get('rol', 'operador'))
            except Exception:
                user = None
            finally:
                cursor.close()
                conn.close()
            Clock.schedule_once(lambda *_: self._aplicar(user, permisos), 0)

        threading.Thread(target=_tarea, daemon=True).start()

    def _aplicar(self, user, permisos=None, auto=False):
        overlay.hide()
        if user:
            self.error_msg = ''
            app = self.manager.app
            app.current_user = user
            app.user_rol = user.get('rol', 'operador')
            app.usuario_nombre = user.get('nombre', '')
            if permisos:
                app.aplicar_permisos(permisos)
            if not auto:
                guardar_sesion(user)
            if user.get('must_change_password', 0):
                app.root.current = 'cambiar_password'
            elif permisos and permisos.get('dashboard', (False,))[0]:
                app.root.current = 'dashboard'
            else:
                app.root.current = 'tickets'
            from utils.updater import iniciar_verificacion
            iniciar_verificacion()
        else:
            if not auto:
                self.error_msg = 'Correo o contraseña incorrectos'

    def _sin_conexion(self):
        overlay.hide()
        App.get_running_app().ir_sin_conexion('login')

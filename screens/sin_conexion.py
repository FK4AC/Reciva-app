from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.clock import Clock
import threading
import utils.overlay as overlay


class SinConexionScreen(Screen):
    origen = StringProperty('login')

    def reintentar(self):
        from db.connection import reset_cooldown, get_connection
        reset_cooldown()
        overlay.show('Verificando conexión…')

        def _tarea():
            conn = get_connection()
            if conn:
                conn.close()
                Clock.schedule_once(lambda *_: self._conectado(), 0)
            else:
                Clock.schedule_once(lambda *_: self._fallido(), 0)

        threading.Thread(target=_tarea, daemon=True).start()

    def _conectado(self):
        overlay.hide()
        self.manager.current = self.origen

    def _fallido(self):
        overlay.hide()

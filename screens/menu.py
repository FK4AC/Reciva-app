from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty


class MenuLateral(BoxLayout):
    pantalla_actual = StringProperty('')
    rol             = StringProperty('operador')

    def ir_a(self, pantalla):
        from kivy.app import App
        App.get_running_app().root.current = pantalla

    def cerrar_sesion(self):
        from kivy.app import App
        app = App.get_running_app()
        app.current_user = None
        app.user_rol = 'operador'
        app.root.current = 'login'

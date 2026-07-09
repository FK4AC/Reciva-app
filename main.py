import sys
import os

from kivy.config import Config

BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

Config.set('kivy', 'window_icon', os.path.join(BASE_DIR, 'logo_png', '08-app-icon.ico'))

from kivy.core.window import Window
Window.clearcolor = (0.082, 0.063, 0.055, 1)

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.core.text import LabelBase
from kivy.resources import resource_add_path
from kivy.properties import StringProperty, BooleanProperty
from kivy.clock import Clock

resource_add_path(BASE_DIR)
from screens.splash import SplashScreen
from screens.login import LoginScreen
from screens.dashboard import DashboardScreen
from screens.importar import ImportarScreen
from screens.suscriptores import SuscriptoresScreen
from screens.facturacion import FacturacionScreen
from screens.tickets import TicketsScreen
from screens.sin_conexion import SinConexionScreen
from screens.usuarios import UsuariosScreen
from screens.estadisticas import EstadisticasScreen
from screens.volcado import VolcadoScreen
from screens.roles import RolesScreen
from screens.setup import SetupScreen
from screens.cambiar_password import CambiarPasswordScreen
from screens.menu import MenuLateral  # noqa: F401
import widgets.components  # noqa: F401

LabelBase.register(
    name='Sora',
    fn_regular=os.path.join(BASE_DIR, 'fonts', 'Sora-SemiBold2.ttf'),
    fn_bold=os.path.join(BASE_DIR, 'fonts', 'Sora-Bold2.ttf'),
)
LabelBase.register(
    name='Jakarta',
    fn_regular=os.path.join(BASE_DIR, 'fonts', 'Jakarta-Regular.ttf'),
    fn_italic=os.path.join(BASE_DIR, 'fonts', 'Jakarta-Medium.ttf'),
    fn_bold=os.path.join(BASE_DIR, 'fonts', 'Jakarta-SemiBold.ttf'),
)


class RecivaApp(App):
    current_user   = None
    user_rol       = StringProperty('operador')
    usuario_nombre = StringProperty('')
    empresa_nombre = StringProperty('Reciva')

    # Etiquetas configurables por cliente
    label_clientes   = StringProperty('Clientes')
    label_cobros     = StringProperty('Cobros')
    label_pagos      = StringProperty('Pagos')
    label_soporte    = StringProperty('Soporte')
    label_id_cliente = StringProperty('Código')

    # Permisos por pantalla
    perm_dashboard      = BooleanProperty(False)
    perm_suscriptores   = BooleanProperty(False)
    perm_facturacion    = BooleanProperty(False)
    perm_tickets        = BooleanProperty(False)
    perm_importar       = BooleanProperty(False)
    perm_estadisticas   = BooleanProperty(False)
    perm_volcado        = BooleanProperty(False)
    perm_usuarios       = BooleanProperty(False)
    perm_roles          = BooleanProperty(False)
    perm_configuracion  = BooleanProperty(False)

    def aplicar_permisos(self, permisos_dict):
        self.perm_dashboard    = permisos_dict.get('dashboard',    (False, False))[0]
        self.perm_suscriptores = permisos_dict.get('suscriptores', (False, False))[0]
        self.perm_facturacion  = permisos_dict.get('facturacion',  (False, False))[0]
        self.perm_tickets      = permisos_dict.get('tickets',      (False, False))[0]
        self.perm_importar     = permisos_dict.get('importar',     (False, False))[0]
        self.perm_estadisticas = permisos_dict.get('estadisticas', (False, False))[0]
        self.perm_volcado      = permisos_dict.get('volcado',      (False, False))[0]
        self.perm_usuarios     = permisos_dict.get('usuarios',     (False, False))[0]
        self.perm_roles        = permisos_dict.get('roles',        (False, False))[0]
        # Configuracion solo para superadmin, ademas modulada por config_sistema
        self.perm_configuracion = (self.user_rol in ('superadmin', 'admin'))
        # Filtrar volcado por modulos activos
        self._aplicar_modulos()

    def _aplicar_modulos(self):
        try:
            from utils.config_sistema import modulos_activos
            activos = modulos_activos()
            if 'volcado' not in activos:
                self.perm_volcado = False
        except Exception:
            pass

    def _cargar_empresa(self):
        try:
            from utils.config_sistema import get_all
            cfg = get_all()
            nombre = cfg.get('empresa_nombre', '')
            if nombre:
                self.empresa_nombre = nombre
            self.label_clientes   = cfg.get('label_clientes',   'Clientes')
            self.label_cobros     = cfg.get('label_cobros',     'Cobros')
            self.label_pagos      = cfg.get('label_pagos',      'Pagos')
            self.label_soporte    = cfg.get('label_soporte',    'Soporte')
            self.label_id_cliente = cfg.get('label_id_cliente', 'Código')
        except Exception:
            pass

    def on_start(self):
        import config
        def _primer_frame(*_):
            if config.es_primer_uso():
                Clock.schedule_once(lambda *_: setattr(self.root, 'current', 'setup'), 0.5)
            else:
                self._cargar_empresa()
                Clock.schedule_once(lambda *_: setattr(self.root, 'current', 'login'), 2.0)
        Clock.schedule_once(_primer_frame, 0)

    def build(self):
        sm = ScreenManager(transition=FadeTransition(duration=0.15))
        sm.app = self
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(SetupScreen(name='setup'))
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(CambiarPasswordScreen(name='cambiar_password'))
        sm.add_widget(DashboardScreen(name='dashboard'))
        sm.add_widget(ImportarScreen(name='importar'))
        sm.add_widget(SuscriptoresScreen(name='suscriptores'))
        sm.add_widget(FacturacionScreen(name='facturacion'))
        sm.add_widget(TicketsScreen(name='tickets'))
        sm.add_widget(SinConexionScreen(name='sin_conexion'))
        sm.add_widget(UsuariosScreen(name='usuarios'))
        sm.add_widget(EstadisticasScreen(name='estadisticas'))
        sm.add_widget(VolcadoScreen(name='volcado'))
        sm.add_widget(RolesScreen(name='roles'))
        return sm

    def ir_sin_conexion(self, origen):
        sc = self.root.get_screen('sin_conexion')
        sc.origen = origen
        self.root.current = 'sin_conexion'


if __name__ == '__main__':
    RecivaApp().run()

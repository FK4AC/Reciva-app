from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.core.text import LabelBase
from kivy.properties import StringProperty, BooleanProperty
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
from screens.menu import MenuLateral  # noqa: F401  (registra el widget para el kv)
import widgets.components  # noqa: F401  (registra PillButton, AccentCard, FilterPill, TabButton…)

LabelBase.register(
    name='Sora',
    fn_regular='fonts/Sora-SemiBold2.ttf',
    fn_bold='fonts/Sora-Bold2.ttf',
)
LabelBase.register(
    name='Jakarta',
    fn_regular='fonts/Jakarta-Regular.ttf',
    fn_italic='fonts/Jakarta-Medium.ttf',
    fn_bold='fonts/Jakarta-SemiBold.ttf',
)


class RecivaApp(App):
    current_user   = None
    user_rol       = StringProperty('operador')
    usuario_nombre = StringProperty('')

    # Permisos por pantalla — actualizados al hacer login
    perm_dashboard    = BooleanProperty(False)
    perm_suscriptores = BooleanProperty(False)
    perm_facturacion  = BooleanProperty(False)
    perm_tickets      = BooleanProperty(False)
    perm_importar     = BooleanProperty(False)
    perm_estadisticas = BooleanProperty(False)
    perm_volcado      = BooleanProperty(False)
    perm_usuarios     = BooleanProperty(False)
    perm_roles        = BooleanProperty(False)

    def aplicar_permisos(self, permisos_dict):
        """Recibe dict pantalla → (puede_ver, puede_editar) y actualiza las properties."""
        self.perm_dashboard    = permisos_dict.get('dashboard',    (False, False))[0]
        self.perm_suscriptores = permisos_dict.get('suscriptores', (False, False))[0]
        self.perm_facturacion  = permisos_dict.get('facturacion',  (False, False))[0]
        self.perm_tickets      = permisos_dict.get('tickets',      (False, False))[0]
        self.perm_importar     = permisos_dict.get('importar',     (False, False))[0]
        self.perm_estadisticas = permisos_dict.get('estadisticas', (False, False))[0]
        self.perm_volcado      = permisos_dict.get('volcado',      (False, False))[0]
        self.perm_usuarios     = permisos_dict.get('usuarios',     (False, False))[0]
        self.perm_roles        = permisos_dict.get('roles',        (False, False))[0]

    def build(self):
        sm = ScreenManager(transition=FadeTransition(duration=0.15))
        sm.app = self
        sm.add_widget(LoginScreen(name='login'))
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

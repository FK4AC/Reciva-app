from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.core.text import LabelBase
from screens.login import LoginScreen
from screens.dashboard import DashboardScreen
from screens.importar import ImportarScreen
from screens.suscriptores import SuscriptoresScreen
from screens.facturacion import FacturacionScreen
from screens.tickets import TicketsScreen
from screens.menu import MenuLateral  # noqa: F401  (registra el widget para el kv)

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
    current_user = None

    def build(self):
        sm = ScreenManager(transition=NoTransition())
        sm.app = self
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(DashboardScreen(name='dashboard'))
        sm.add_widget(ImportarScreen(name='importar'))
        sm.add_widget(SuscriptoresScreen(name='suscriptores'))
        sm.add_widget(FacturacionScreen(name='facturacion'))
        sm.add_widget(TicketsScreen(name='tickets'))
        return sm


if __name__ == '__main__':
    RecivaApp().run()

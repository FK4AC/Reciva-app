from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock
import threading


class ImportarScreen(Screen):
    mensaje = StringProperty('')
    color_msg = ListProperty([0.2, 0.9, 0.4, 1])

    def seleccionar_archivo(self, tipo):
        from plyer import filechooser
        try:
            archivos = filechooser.open_file(
                title=f'Seleccionar archivo {tipo}',
                filters=[('Excel', '*.xlsx', '*.xls')]
            )
            if archivos:
                self.procesar(archivos[0], tipo)
        except Exception as e:
            self.mensaje = f'Error al abrir selector: {e}'

    def procesar(self, filepath, tipo):
        self.mensaje = f'Importando {tipo}...'
        self.color_msg = [0.9, 0.8, 0.1, 1]

        def tarea():
            from utils.importar import importar_catastro, importar_facturacion, importar_recaudo
            if tipo == 'catastro':
                ok, msg = importar_catastro(filepath)
            elif tipo == 'facturacion':
                ok, msg = importar_facturacion(filepath)
            elif tipo == 'recaudo':
                ok, msg = importar_recaudo(filepath)
            else:
                ok, msg = False, 'Tipo desconocido'

            Clock.schedule_once(lambda _: self._actualizar_ui(ok, msg), 0)

        threading.Thread(target=tarea, daemon=True).start()

    def _actualizar_ui(self, ok, msg):
        self.mensaje = msg
        self.color_msg = [0.2, 0.9, 0.4, 1] if ok else [1, 0.3, 0.3, 1]

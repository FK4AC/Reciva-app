from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty

from db.connection import get_connection

MESES = {
    '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
    '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
    '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}


class FacturacionScreen(Screen):
    mensaje         = StringProperty('')
    total_facturado = StringProperty('—')
    total_recaudado = StringProperty('—')
    deuda_periodo   = StringProperty('—')

    def on_enter(self):
        self._cargar_periodos()

    def _cargar_periodos(self):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT año FROM facturas WHERE año IS NOT NULL ORDER BY año DESC")
            años = [str(r[0]) for r in cursor.fetchall()]
            sp_año = self.ids.spinner_año
            if años:
                sp_año.values = años
                if sp_año.text not in años:
                    sp_año.text = años[0]

            cursor.execute("""
                SELECT DISTINCT mes FROM facturas
                WHERE mes IS NOT NULL
                ORDER BY CAST(mes AS UNSIGNED)
            """)
            meses_db = [str(r[0]) for r in cursor.fetchall()]
            sp_mes = self.ids.spinner_mes
            if meses_db:
                sp_mes.values = meses_db
                if sp_mes.text not in meses_db:
                    sp_mes.text = meses_db[-1]
        except Exception as e:
            self.mensaje = f'Error: {e}'
        finally:
            cursor.close()
            conn.close()

    def consultar(self):
        año = self.ids.spinner_año.text
        mes = self.ids.spinner_mes.text
        if año in ('Año', '') or mes in ('Mes', ''):
            self.mensaje = 'Selecciona un período válido'
            return
        self._cargar_periodo(año, mes)

    def _cargar_periodo(self, año, mes):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COALESCE(SUM(valor_recibo), 0) FROM facturas WHERE año=%s AND mes=%s",
                (año, mes)
            )
            total_fac = float(cursor.fetchone()[0])

            cursor.execute(
                "SELECT COALESCE(SUM(valor_recibo), 0) FROM recaudos WHERE año=%s AND mes=%s",
                (año, mes)
            )
            total_rec = float(cursor.fetchone()[0])

            self.total_facturado = f'${total_fac:,.0f}'
            self.total_recaudado = f'${total_rec:,.0f}'
            self.deuda_periodo   = f'${max(0, total_fac - total_rec):,.0f}'

            cursor.execute("""
                SELECT estrato_contrato, COUNT(*), SUM(valor_recibo)
                FROM facturas WHERE año=%s AND mes=%s
                GROUP BY estrato_contrato ORDER BY estrato_contrato
            """, (año, mes))
            estratos = cursor.fetchall()

            cursor.execute("""
                SELECT s.cuenta, s.nombre, s.barrio, f.valor_recibo
                FROM facturas f
                JOIN suscriptores s ON f.cuenta_contrato = s.cuenta
                WHERE f.año=%s AND f.mes=%s
                  AND f.cuenta_contrato NOT IN (
                      SELECT cuenta_contrato FROM recaudos WHERE año=%s AND mes=%s
                  )
                ORDER BY f.valor_recibo DESC
                LIMIT 200
            """, (año, mes, año, mes))
            pendientes = cursor.fetchall()

            nombre_mes = MESES.get(mes, mes)
            self.mensaje = f'{nombre_mes} {año} — {len(pendientes)} pendientes de pago'
            self._actualizar_tablas(estratos, pendientes)

        except Exception as e:
            self.mensaje = f'Error: {e}'
        finally:
            cursor.close()
            conn.close()

    def _actualizar_tablas(self, estratos, pendientes):
        tabla = self.ids.tabla_estratos
        tabla.clear_widgets()
        for estrato, count, total in estratos:
            for val in [str(estrato or '-'), str(count), f'${float(total):,.0f}']:
                tabla.add_widget(Label(text=val, font_size=12, color=(0.9, 0.9, 0.9, 1)))

        lista = self.ids.lista_pendientes
        lista.clear_widgets()
        for cuenta, nombre, barrio, valor in pendientes:
            fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=36, spacing=2)
            with fila.canvas.before:
                Color(0.18, 0.07, 0.07, 1)
                rect = Rectangle(pos=fila.pos, size=fila.size)
            fila.bind(pos=lambda inst, v, r=rect: setattr(r, 'pos', v))
            fila.bind(size=lambda inst, v, r=rect: setattr(r, 'size', v))

            for txt, sx, col in [
                (str(cuenta),            0.18, (0.8, 0.8, 0.8, 1)),
                ((nombre or '')[:32],    0.42, (0.9, 0.9, 0.9, 1)),
                ((barrio or '-')[:18],   0.22, (0.7, 0.7, 0.7, 1)),
                (f'${float(valor):,.0f}',0.18, (1.0, 0.4, 0.4, 1)),
            ]:
                lbl = Label(text=txt, size_hint_x=sx, font_size=12, color=col,
                            halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
                fila.add_widget(lbl)
            lista.add_widget(fila)

from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty, ListProperty
from db.connection import get_connection
from theme import TINTA, STAGE, CARD, VERMILLON, LINE, MUTED, TEXT_SEC

MESES_NOMBRE = {
    '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
    '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
    '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}


class DashboardScreen(Screen):
    usuario_nombre     = StringProperty('')
    total_suscriptores = StringProperty('—')
    total_facturado    = StringProperty('—')
    total_recaudado    = StringProperty('—')
    deuda_total        = StringProperty('—')
    sus_con_deuda      = StringProperty('—')
    pqr_abiertas       = StringProperty('—')
    periodo_label      = StringProperty('Selecciona un período')
    años_disponibles   = ListProperty([])
    meses_disponibles  = ListProperty([])

    def on_enter(self):
        app = self.manager.app
        if app.current_user:
            self.usuario_nombre = app.current_user['nombre']
        self._cargar_global()
        self._cargar_periodos()

    def _cargar_global(self):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM suscriptores")
            self.total_suscriptores = f"{cursor.fetchone()[0]:,}"
            cursor.execute("SELECT COUNT(*) FROM pqr WHERE estado != 'Resuelto'")
            self.pqr_abiertas = str(cursor.fetchone()[0])
        except Exception as e:
            print(f'Error stats global: {e}')
        finally:
            cursor.close()
            conn.close()

    def _cargar_periodos(self):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT año FROM facturas WHERE año IS NOT NULL ORDER BY año DESC"
            )
            self.años_disponibles = [str(r[0]) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT DISTINCT mes FROM facturas
                WHERE mes IS NOT NULL
                ORDER BY CAST(mes AS UNSIGNED)
            """)
            self.meses_disponibles = [str(r[0]) for r in cursor.fetchall()]

            # Cargar el período más reciente automáticamente
            cursor.execute("""
                SELECT año, mes FROM facturas
                WHERE año IS NOT NULL AND mes IS NOT NULL
                ORDER BY año DESC, CAST(mes AS UNSIGNED) DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                año_rec, mes_rec = str(row[0]), str(row[1])
                self.ids.dash_año.text = año_rec
                self.ids.dash_mes.text = mes_rec
                self._cargar_stats(año_rec, mes_rec)

        except Exception as e:
            print(f'Error períodos dashboard: {e}')
        finally:
            cursor.close()
            conn.close()

    def cambiar_periodo(self, año, mes):
        if año in ('Año', '') or mes in ('Mes', ''):
            return
        self._cargar_stats(año, mes)

    def _cargar_stats(self, año, mes):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            self.periodo_label = f"{MESES_NOMBRE.get(str(mes), mes)} {año}"

            cursor.execute(
                "SELECT COALESCE(SUM(valor_recibo), 0) FROM facturas WHERE año=%s AND mes=%s",
                (año, mes)
            )
            total_fac = float(cursor.fetchone()[0])
            self.total_facturado = f'${total_fac:,.0f}'

            cursor.execute(
                "SELECT COALESCE(SUM(valor_recibo), 0) FROM recaudos WHERE año=%s AND mes=%s",
                (año, mes)
            )
            total_rec = float(cursor.fetchone()[0])
            self.total_recaudado = f'${total_rec:,.0f}'
            self.deuda_total = f'${max(0, total_fac - total_rec):,.0f}'

            cursor.execute("""
                SELECT COUNT(DISTINCT cuenta_contrato) FROM facturas f
                WHERE año=%s AND mes=%s
                AND NOT EXISTS (
                    SELECT 1 FROM recaudos r
                    WHERE r.cuenta_contrato = f.cuenta_contrato
                    AND r.año = f.año AND r.mes = f.mes
                )
            """, (año, mes))
            self.sus_con_deuda = f"{cursor.fetchone()[0]:,}"

        except Exception as e:
            print(f'Error stats dashboard: {e}')
        finally:
            cursor.close()
            conn.close()

    def popup_barrios(self):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COALESCE(barrio, '(Sin barrio)'), COUNT(*) as total
                FROM suscriptores
                GROUP BY barrio
                ORDER BY total DESC
            """)
            barrios = cursor.fetchall()
        except Exception as e:
            print(f'Error barrios: {e}')
            return
        finally:
            cursor.close()
            conn.close()

        total_general = sum(c for _, c in barrios)

        content = BoxLayout(orientation='vertical', spacing=8, padding=12)
        with content.canvas.before:
            Color(*CARD)
            bg_r = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(bg_r, 'pos', v))
        content.bind(size=lambda _, v: setattr(bg_r, 'size', v))

        content.add_widget(Label(
            text=f'Total: {total_general:,} suscriptores en {len(barrios)} barrios',
            color=VERMILLON, bold=True, font_size=13,
            size_hint_y=None, height=28
        ))

        # Encabezado
        header = BoxLayout(size_hint_y=None, height=30, spacing=4)
        with header.canvas.before:
            Color(*TINTA)
            Rectangle(pos=header.pos, size=header.size)
        for txt, sx in [('Barrio', 0.55), ('Suscriptores', 0.25), ('% del total', 0.20)]:
            header.add_widget(Label(text=txt, bold=True, size_hint_x=sx,
                                    font_size=11, color=LINE))
        content.add_widget(header)

        scroll = ScrollView()
        lista = GridLayout(cols=3, size_hint_y=None,
                           row_default_height=32, row_force_default=True, spacing=1)
        lista.bind(minimum_height=lista.setter('height'))

        for i, (barrio, count) in enumerate(barrios):
            pct = count / total_general * 100 if total_general else 0
            bg = CARD if i % 2 == 0 else STAGE
            bar_color = VERMILLON if pct >= 10 else MUTED

            for txt, sx, col in [
                (barrio,           0.55, TINTA),
                (f'{count:,}',     0.25, TEXT_SEC),
                (f'{pct:.1f}%',    0.20, bar_color),
            ]:
                lbl = Label(text=txt, size_hint_x=sx, font_size=12,
                            color=col, halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0]-4, v[1])))
                with lbl.canvas.before:
                    Color(*bg)
                    rect = Rectangle(pos=lbl.pos, size=lbl.size)
                lbl.bind(pos=lambda _, v, r=rect: setattr(r, 'pos', v))
                lbl.bind(size=lambda _, v, r=rect: setattr(r, 'size', v))
                lista.add_widget(lbl)

        scroll.add_widget(lista)
        content.add_widget(scroll)

        btn_cerrar = Button(text='Cerrar', size_hint_y=None, height=40,
                            background_normal='', background_color=LINE, color=TINTA)
        content.add_widget(btn_cerrar)

        popup = Popup(title='Suscriptores por Barrio', content=content,
                      size_hint=(0.52, 0.80),
                      background_color=VERMILLON, title_color=(1,1,1,1),
                      separator_color=LINE)
        btn_cerrar.bind(on_press=popup.dismiss)
        popup.open()

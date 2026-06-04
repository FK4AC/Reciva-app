from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty
from db.connection import get_connection


class DashboardScreen(Screen):
    usuario_nombre    = StringProperty('')
    total_suscriptores = StringProperty('...')
    total_facturado   = StringProperty('...')
    total_recaudado   = StringProperty('...')
    deuda_total       = StringProperty('...')
    sus_con_deuda     = StringProperty('...')
    pqr_abiertas      = StringProperty('...')

    def on_enter(self):
        app = self.manager.app
        if app.current_user:
            self.usuario_nombre = app.current_user['nombre']
        self._cargar_stats()

    def _cargar_stats(self):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM suscriptores")
            self.total_suscriptores = f"{cursor.fetchone()[0]:,}"

            cursor.execute("SELECT COALESCE(SUM(valor_recibo), 0) FROM facturas")
            total_fac = float(cursor.fetchone()[0])
            self.total_facturado = f'${total_fac:,.0f}'

            cursor.execute("SELECT COALESCE(SUM(valor_recibo), 0) FROM recaudos")
            total_rec = float(cursor.fetchone()[0])
            self.total_recaudado = f'${total_rec:,.0f}'
            self.deuda_total = f'${max(0, total_fac - total_rec):,.0f}'

            cursor.execute("""
                SELECT COUNT(DISTINCT cuenta_contrato) FROM facturas f
                WHERE NOT EXISTS (
                    SELECT 1 FROM recaudos r
                    WHERE r.cuenta_contrato = f.cuenta_contrato
                    AND r.año = f.año AND r.mes = f.mes
                )
            """)
            self.sus_con_deuda = f"{cursor.fetchone()[0]:,}"

            cursor.execute("SELECT COUNT(*) FROM pqr WHERE estado != 'Resuelto'")
            self.pqr_abiertas = str(cursor.fetchone()[0])

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

        content.add_widget(Label(
            text=f'Total: {total_general:,} suscriptores en {len(barrios)} barrios',
            color=(0.5, 0.75, 1, 1), bold=True,
            size_hint_y=None, height=28
        ))

        # Encabezado
        header = BoxLayout(size_hint_y=None, height=30, spacing=4)
        header.canvas.before.add(Color(0.15, 0.15, 0.3, 1))
        with header.canvas.before:
            Color(0.15, 0.15, 0.3, 1)
            Rectangle(pos=header.pos, size=header.size)
        for txt, sx in [('Barrio', 0.55), ('Suscriptores', 0.25), ('% del total', 0.20)]:
            header.add_widget(Label(text=txt, bold=True, size_hint_x=sx,
                                    font_size=12, color=(0.2, 0.6, 1, 1)))
        content.add_widget(header)

        scroll = ScrollView()
        lista = GridLayout(cols=3, size_hint_y=None,
                           row_default_height=32, row_force_default=True, spacing=2)
        lista.bind(minimum_height=lista.setter('height'))

        for i, (barrio, count) in enumerate(barrios):
            pct = count / total_general * 100 if total_general else 0
            bg = (0.11, 0.11, 0.20, 1) if i % 2 == 0 else (0.13, 0.13, 0.24, 1)

            # barra de proporción visual en el color del texto
            bar_color = (0.2, 0.7, 1, 1) if pct >= 10 else (0.5, 0.75, 1, 1)

            for txt, sx, col in [
                (barrio,           0.55, (0.9, 0.9, 0.9, 1)),
                (f'{count:,}',     0.25, (1.0, 1.0, 1.0, 1)),
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
                            background_color=(0.35, 0.35, 0.35, 1))
        content.add_widget(btn_cerrar)

        popup = Popup(title='Suscriptores por Barrio',
                      content=content, size_hint=(0.52, 0.80))
        btn_cerrar.bind(on_press=popup.dismiss)
        popup.open()

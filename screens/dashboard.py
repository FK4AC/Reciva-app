from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock
import threading
from db.connection import get_connection
from theme import TINTA, STAGE, CARD, VERMILLON, LINE, MUTED, TEXT_SEC, SUCCESS, DANGER, WARNING
import utils.overlay as overlay

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
    tasa_cobro         = StringProperty('—')
    tasa_cobro_color   = ListProperty([0.549, 0.502, 0.467, 1])
    periodo_label      = StringProperty('Selecciona un período')
    años_disponibles   = ListProperty([])
    meses_disponibles  = ListProperty([])

    def on_enter(self):
        app = self.manager.app
        if app.current_user:
            self.usuario_nombre = app.current_user['nombre']
        overlay.show()
        threading.Thread(target=self._tarea_inicio, daemon=True).start()

    def _tarea_inicio(self):
        d = {'sus': '—', 'pqr': '0', 'años': [], 'meses': [],
             'año': None, 'mes': None, 'fac': 0.0, 'rec': 0.0, 'deuda_sus': 0,
             'sin_conexion': False}
        conn = get_connection()
        if not conn:
            d['sin_conexion'] = True
            Clock.schedule_once(lambda *_: self._aplicar_inicio(d), 0)
            return
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM suscriptores")
                d['sus'] = f"{cursor.fetchone()[0]:,}"
                cursor.execute("SELECT COUNT(*) FROM pqr WHERE estado != 'Resuelto'")
                d['pqr'] = str(cursor.fetchone()[0])
                cursor.execute(
                    "SELECT DISTINCT año FROM facturas WHERE año IS NOT NULL ORDER BY año DESC"
                )
                d['años'] = [str(r[0]) for r in cursor.fetchall()]
                cursor.execute("""
                    SELECT DISTINCT mes FROM facturas
                    WHERE mes IS NOT NULL ORDER BY CAST(mes AS UNSIGNED)
                """)
                d['meses'] = [str(r[0]) for r in cursor.fetchall()]
                cursor.execute("""
                    SELECT año, mes FROM facturas
                    WHERE año IS NOT NULL AND mes IS NOT NULL
                    ORDER BY año DESC, CAST(mes AS UNSIGNED) DESC LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    año, mes = str(row[0]), str(row[1])
                    d['año'], d['mes'] = año, mes
                    cursor.execute(
                        "SELECT COALESCE(SUM(valor_recibo), 0) FROM facturas WHERE año=%s AND mes=%s",
                        (año, mes)
                    )
                    d['fac'] = float(cursor.fetchone()[0])
                    cursor.execute(
                        "SELECT COALESCE(SUM(valor_recibo), 0) FROM recaudos WHERE año=%s AND mes=%s",
                        (año, mes)
                    )
                    d['rec'] = float(cursor.fetchone()[0])
                    cursor.execute("""
                        SELECT COUNT(DISTINCT cuenta_contrato) FROM facturas f
                        WHERE año=%s AND mes=%s
                        AND NOT EXISTS (
                            SELECT 1 FROM recaudos r
                            WHERE r.cuenta_contrato = f.cuenta_contrato
                            AND r.año = f.año AND r.mes = f.mes
                        )
                    """, (año, mes))
                    d['deuda_sus'] = cursor.fetchone()[0]
            except Exception as e:
                print(f'Error dashboard: {e}')
            finally:
                cursor.close()
                conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_inicio(d), 0)

    def _set_tasa(self, fac, rec):
        if fac > 0:
            pct = rec / fac * 100
            self.tasa_cobro = f'{pct:.1f}%'
            if pct >= 80:
                self.tasa_cobro_color = list(SUCCESS)
            elif pct >= 50:
                self.tasa_cobro_color = list(WARNING)
            else:
                self.tasa_cobro_color = list(DANGER)
        else:
            self.tasa_cobro = '—'
            self.tasa_cobro_color = [0.549, 0.502, 0.467, 1]

    def _aplicar_inicio(self, d):
        overlay.hide()
        if d.get('sin_conexion'):
            from kivy.app import App
            App.get_running_app().ir_sin_conexion(self.name)
            return
        self.total_suscriptores = d['sus']
        self.pqr_abiertas = d['pqr']
        self.años_disponibles = d['años']
        self.meses_disponibles = d['meses']
        if d['año']:
            año, mes = d['año'], d['mes']
            self.ids.dash_año.text = año
            self.ids.dash_mes.text = mes
            self.periodo_label = f"{MESES_NOMBRE.get(mes, mes)} {año}"
            self.total_facturado = f'${d["fac"]:,.0f}'
            self.total_recaudado = f'${d["rec"]:,.0f}'
            self.deuda_total = f'${max(0, d["fac"] - d["rec"]):,.0f}'
            self.sus_con_deuda = f'{d["deuda_sus"]:,}'
            self._set_tasa(d['fac'], d['rec'])

    def cambiar_periodo(self, año, mes):
        if año in ('Año', '') or mes in ('Mes', ''):
            return
        overlay.show('Cargando período…')
        threading.Thread(
            target=lambda: self._tarea_stats(año, mes), daemon=True
        ).start()

    def _tarea_stats(self, año, mes):
        d = {'año': año, 'mes': mes, 'fac': 0.0, 'rec': 0.0, 'deuda_sus': 0}
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT COALESCE(SUM(valor_recibo), 0) FROM facturas WHERE año=%s AND mes=%s",
                    (año, mes)
                )
                d['fac'] = float(cursor.fetchone()[0])
                cursor.execute(
                    "SELECT COALESCE(SUM(valor_recibo), 0) FROM recaudos WHERE año=%s AND mes=%s",
                    (año, mes)
                )
                d['rec'] = float(cursor.fetchone()[0])
                cursor.execute("""
                    SELECT COUNT(DISTINCT cuenta_contrato) FROM facturas f
                    WHERE año=%s AND mes=%s
                    AND NOT EXISTS (
                        SELECT 1 FROM recaudos r
                        WHERE r.cuenta_contrato = f.cuenta_contrato
                        AND r.año = f.año AND r.mes = f.mes
                    )
                """, (año, mes))
                d['deuda_sus'] = cursor.fetchone()[0]
            except Exception as e:
                print(f'Error stats dashboard: {e}')
            finally:
                cursor.close()
                conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_stats(d), 0)

    def _aplicar_stats(self, d):
        año, mes = d['año'], d['mes']
        self.periodo_label = f"{MESES_NOMBRE.get(str(mes), mes)} {año}"
        self.total_facturado = f'${d["fac"]:,.0f}'
        self.total_recaudado = f'${d["rec"]:,.0f}'
        self.deuda_total = f'${max(0, d["fac"] - d["rec"]):,.0f}'
        self.sus_con_deuda = f'{d["deuda_sus"]:,}'
        self._set_tasa(d['fac'], d['rec'])
        overlay.hide()

    def popup_barrios(self):
        # ── Estructura del popup ──────────────────────────────────────
        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            _bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(_bg, 'pos', v),
                     size=lambda _, v: setattr(_bg, 'size', v))

        # Franja header
        hdr = BoxLayout(size_hint_y=None, height=52, padding=[16, 0])
        with hdr.canvas.before:
            Color(*TINTA)
            _rh = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda _, v: setattr(_rh, 'pos', v),
                 size=lambda _, v: setattr(_rh, 'size', v))
        hdr.add_widget(Label(text='Segmentación de Suscriptores', bold=True,
                             font_size=15, color=(1, 1, 1, 1),
                             halign='left', valign='middle', text_size=(500, 52)))
        content.add_widget(hdr)

        # Barra de pestañas
        tab_bar = BoxLayout(size_hint_y=None, height=40, spacing=2, padding=[8, 6])
        with tab_bar.canvas.before:
            Color(*STAGE)
            _rt = Rectangle(pos=tab_bar.pos, size=tab_bar.size)
        tab_bar.bind(pos=lambda _, v: setattr(_rt, 'pos', v),
                     size=lambda _, v: setattr(_rt, 'size', v))
        btn_b = Button(text='Por Barrio',  font_size=14, size_hint_x=0.33,
                       background_normal='', background_color=VERMILLON, color=(1,1,1,1))
        btn_e = Button(text='Por Estrato', font_size=14, size_hint_x=0.33,
                       background_normal='', background_color=LINE, color=TINTA)
        btn_s = Button(text='Por Estado',  font_size=14, size_hint_x=0.34,
                       background_normal='', background_color=LINE, color=TINTA)
        tab_bar.add_widget(btn_b)
        tab_bar.add_widget(btn_e)
        tab_bar.add_widget(btn_s)
        content.add_widget(tab_bar)

        # Línea de resumen
        lbl_res = Label(text='  Cargando…', color=MUTED, font_size=13,
                        size_hint_y=None, height=28,
                        halign='left', valign='middle')
        lbl_res.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0]-8, v[1])))
        content.add_widget(lbl_res)

        # Área de contenido (reemplazable al cambiar pestaña)
        scroll = ScrollView()
        area = GridLayout(cols=1, size_hint_y=None, spacing=0)
        area.bind(minimum_height=area.setter('height'))
        scroll.add_widget(area)
        content.add_widget(scroll)

        # Footer
        footer = BoxLayout(size_hint_y=None, height=48, padding=[12, 8])
        with footer.canvas.before:
            Color(*STAGE)
            _rf = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda _, v: setattr(_rf, 'pos', v),
                    size=lambda _, v: setattr(_rf, 'size', v))
        btn_cerrar = Button(text='Cerrar', background_normal='',
                            background_color=LINE, color=TINTA, font_size=12)
        footer.add_widget(btn_cerrar)
        content.add_widget(footer)

        popup = Popup(title='', content=content, size_hint=(0.65, 0.86),
                      background_color=CARD, separator_height=0)
        btn_cerrar.bind(on_press=popup.dismiss)

        # ── Estado compartido ─────────────────────────────────────────
        datos = {}
        tab_actual = ['barrios']
        tabs = {'barrios': btn_b, 'estratos': btn_e, 'estados': btn_s}

        # ── Helpers de fila ───────────────────────────────────────────
        def _hdr_row(cols):
            row = BoxLayout(size_hint_y=None, height=34)
            with row.canvas.before:
                Color(*TINTA)
                r = Rectangle(pos=row.pos, size=row.size)
            row.bind(pos=lambda _, v: setattr(r, 'pos', v),
                     size=lambda _, v: setattr(r, 'size', v))
            for txt, sx in cols:
                row.add_widget(Label(text=txt, bold=True, font_size=13, color=LINE,
                                     size_hint_x=sx, halign='left', valign='middle',
                                     text_size=(200, 34)))
            return row

        def _data_row(celdas, bg):
            row = BoxLayout(size_hint_y=None, height=36)
            with row.canvas.before:
                Color(*bg)
                r = Rectangle(pos=row.pos, size=row.size)
            row.bind(pos=lambda _, v: setattr(r, 'pos', v),
                     size=lambda _, v: setattr(r, 'size', v))
            for txt, sx, col in celdas:
                lbl = Label(text=txt, size_hint_x=sx, font_size=13, color=col,
                            halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0]-4, v[1])))
                row.add_widget(lbl)
            return row

        # ── Renderers por pestaña ──────────────────────────────────────
        def _render_barrios():
            area.clear_widgets()
            rows = datos.get('barrios', [])
            total_g = datos.get('total', 0)
            area.add_widget(_hdr_row([
                ('Barrio', 0.38), ('Total', 0.14), ('Activos', 0.14),
                ('Inactivos', 0.14), ('% del total', 0.20),
            ]))
            for i, (barrio, total, activos, inactivos) in enumerate(rows):
                pct = total / total_g * 100 if total_g else 0
                act_col = SUCCESS if activos == total else (WARNING if activos > 0 else DANGER)
                area.add_widget(_data_row([
                    (str(barrio),           0.38, TINTA),
                    (f'{total:,}',          0.14, TEXT_SEC),
                    (f'{activos:,}',        0.14, act_col),
                    (f'{inactivos:,}',      0.14, MUTED),
                    (f'{pct:.1f}%',         0.20, VERMILLON if pct >= 10 else MUTED),
                ], CARD if i % 2 == 0 else STAGE))
            lbl_res.text = f'  {len(rows)} barrios · {total_g:,} suscriptores'

        def _render_estratos():
            area.clear_widgets()
            rows = datos.get('estratos', [])
            total_g = datos.get('total', 0)
            area.add_widget(_hdr_row([
                ('Estrato', 0.36), ('Total', 0.16), ('Activos', 0.16),
                ('% activos', 0.16), ('% del total', 0.16),
            ]))
            for i, (categoria, total, activos) in enumerate(rows):
                pct_tot = total / total_g * 100 if total_g else 0
                pct_act = activos / total * 100 if total else 0
                act_col = SUCCESS if pct_act >= 80 else (WARNING if pct_act >= 40 else DANGER)
                label = str(categoria).split(' - ', 1)[-1].strip() if ' - ' in str(categoria) else str(categoria)
                area.add_widget(_data_row([
                    (label,               0.36, TINTA),
                    (f'{total:,}',        0.16, TEXT_SEC),
                    (f'{activos:,}',      0.16, act_col),
                    (f'{pct_act:.0f}%',   0.16, act_col),
                    (f'{pct_tot:.1f}%',   0.16, MUTED),
                ], CARD if i % 2 == 0 else STAGE))
            lbl_res.text = f'  {len(rows)} categorías distintas'

        def _render_estados():
            area.clear_widgets()
            rows = datos.get('estados', [])
            total_g = datos.get('total', 0)
            # Tiles resumen
            n_act = sum(c for e, c in rows
                        if 'ACTIVO' in str(e).upper() and 'IN' not in str(e).upper())
            n_ina = total_g - n_act
            pct_a = n_act / total_g * 100 if total_g else 0
            tiles = BoxLayout(size_hint_y=None, height=78, spacing=8, padding=[4, 4])
            for val, etq, col in [
                (f'{n_act:,}',  'Activos',   SUCCESS),
                (f'{n_ina:,}',  'Inactivos', DANGER),
                (f'{total_g:,}','Total',      TINTA),
            ]:
                tile = BoxLayout(orientation='vertical', padding=[8, 4])
                with tile.canvas.before:
                    Color(*STAGE)
                    rr = RoundedRectangle(pos=tile.pos, size=tile.size, radius=[8])
                tile.bind(pos=lambda _, v, r=rr: setattr(r, 'pos', v),
                          size=lambda _, v, r=rr: setattr(r, 'size', v))
                tile.add_widget(Label(text=val, bold=True, font_size=22, color=col))
                tile.add_widget(Label(text=etq, font_size=12, color=MUTED))
                tiles.add_widget(tile)
            area.add_widget(tiles)
            area.add_widget(_hdr_row([
                ('Estado de suministro', 0.52), ('Cantidad', 0.24), ('% del total', 0.24),
            ]))
            for i, (estado, count) in enumerate(rows):
                e_up = str(estado).upper()
                col = (SUCCESS if 'ACTIVO' in e_up and 'IN' not in e_up
                       else DANGER if any(x in e_up for x in ('CORTA', 'SUSPEN'))
                       else MUTED)
                pct = count / total_g * 100 if total_g else 0
                area.add_widget(_data_row([
                    (str(estado),  0.52, col),
                    (f'{count:,}', 0.24, TEXT_SEC),
                    (f'{pct:.1f}%',0.24, MUTED),
                ], CARD if i % 2 == 0 else STAGE))
            lbl_res.text = (f'  {len(rows)} estados · {n_act:,} activos '
                            f'({pct_a:.1f}%)')

        renderers = {
            'barrios': _render_barrios,
            'estratos': _render_estratos,
            'estados': _render_estados,
        }

        def _cambiar_tab(tab):
            tab_actual[0] = tab
            for k, btn in tabs.items():
                if k == tab:
                    btn.background_color = VERMILLON
                    btn.color = (1, 1, 1, 1)
                else:
                    btn.background_color = LINE
                    btn.color = TINTA
            if datos:
                renderers[tab]()

        btn_b.bind(on_press=lambda _: _cambiar_tab('barrios'))
        btn_e.bind(on_press=lambda _: _cambiar_tab('estratos'))
        btn_s.bind(on_press=lambda _: _cambiar_tab('estados'))

        # ── Carga de datos en hilo ────────────────────────────────────
        def _tarea():
            d = {'barrios': [], 'estratos': [], 'estados': [], 'total': 0}
            conn = get_connection()
            if not conn:
                Clock.schedule_once(
                    lambda *_: setattr(lbl_res, 'text', '  Error de conexión'), 0)
                return
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT COALESCE(barrio,'(Sin barrio)'), COUNT(*),
                           SUM(CASE WHEN estado_suministro='ACTIVO' THEN 1 ELSE 0 END),
                           SUM(CASE WHEN estado_suministro!='ACTIVO'
                                     OR estado_suministro IS NULL THEN 1 ELSE 0 END)
                    FROM suscriptores GROUP BY barrio ORDER BY COUNT(*) DESC
                """)
                d['barrios'] = cursor.fetchall()
                cursor.execute("""
                    SELECT COALESCE(subcategoria,'(Sin categoría)'), COUNT(*),
                           SUM(CASE WHEN estado_suministro='ACTIVO' THEN 1 ELSE 0 END)
                    FROM suscriptores GROUP BY subcategoria ORDER BY subcategoria
                """)
                d['estratos'] = cursor.fetchall()
                cursor.execute("""
                    SELECT COALESCE(estado_suministro,'(Sin estado)'), COUNT(*)
                    FROM suscriptores GROUP BY estado_suministro ORDER BY COUNT(*) DESC
                """)
                d['estados'] = cursor.fetchall()
                d['total'] = sum(row[1] for row in d['barrios'])
            except Exception as e:
                print(f'Error segmentación: {e}')
            finally:
                cursor.close()
                conn.close()
            Clock.schedule_once(lambda *_: _aplicar(d), 0)

        def _aplicar(d):
            datos.update(d)
            renderers[tab_actual[0]]()

        threading.Thread(target=_tarea, daemon=True).start()
        popup.open()

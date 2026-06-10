import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, RoundedRectangle
from widgets.components import HoverRow, EmptyState
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock

from db.connection import get_connection
import utils.overlay as overlay
from theme import (TINTA, STAGE, CARD, LINE, MUTED,
                   TEXT_SEC, SUCCESS, WARNING, DANGER)

MESES_NOMBRE = {
    '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
    '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
    '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre',
}
MESES_NUM = {v: k for k, v in MESES_NOMBRE.items()}


class EstadisticasScreen(Screen):
    periodo_label = StringProperty('Selecciona un período')
    anios         = ListProperty([])
    meses         = ListProperty([])

    def on_enter(self):
        self._vista = 'estrato'
        self._datos = {}
        self._incluir_huerfanos = False
        overlay.show('Cargando…')
        threading.Thread(target=self._tarea_init, daemon=True).start()

    # ── Carga inicial (períodos disponibles + último) ────────────────
    def _tarea_init(self):
        d = {'años': [], 'meses': [], 'año': None, 'mes': None,
             'sin_conexion': False}
        conn = get_connection()
        if not conn:
            d['sin_conexion'] = True
            Clock.schedule_once(lambda *_: self._aplicar_init(d), 0)
            return
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT DISTINCT anno FROM facturas WHERE anno IS NOT NULL ORDER BY anno DESC"
            )
            anios_db = {str(r[0]) for r in cur.fetchall()}
            anios_db.update({'2025', '2026'})
            d['anios'] = sorted(anios_db, reverse=True)

            # Siempre mostrar los 12 meses
            d['meses'] = list(MESES_NOMBRE.values())

            cur.execute(
                "SELECT anno, mes FROM facturas WHERE anno IS NOT NULL AND mes IS NOT NULL "
                "ORDER BY anno DESC, CAST(mes AS UNSIGNED) DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                d['año'] = str(row[0])
                d['mes'] = MESES_NOMBRE.get(str(row[1]), str(row[1]))
            else:
                d['año'] = '2025'
                d['mes'] = 'Enero'
        except Exception as e:
            print(f'Error estadísticas init: {e}')
        finally:
            cur.close()
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_init(d), 0)

    def _aplicar_init(self, d):
        overlay.hide()
        if d['sin_conexion']:
            from kivy.app import App
            App.get_running_app().ir_sin_conexion(self.name)
            return
        self.anios = d['anios']
        self.meses = d['meses']
        if d['año']:
            self.ids.sp_año.text = d['año']
            self.ids.sp_mes.text = d['mes']
            overlay.show('Calculando estadísticas…')
            threading.Thread(
                target=lambda: self._tarea_stats(d['año'], MESES_NUM.get(d['mes'], d['mes'])),
                daemon=True,
            ).start()

    # ── Toggle huérfanos ─────────────────────────────────────────────
    def toggle_huerfanos(self):
        self._incluir_huerfanos = not self._incluir_huerfanos
        btn = self.ids.btn_huerfanos
        btn.is_active = self._incluir_huerfanos
        btn.text = 'Con pagos sin factura' if self._incluir_huerfanos else 'Pagos sin factura'
        año = self.ids.sp_año.text
        mes_txt = self.ids.sp_mes.text
        if año not in ('Año', '') and mes_txt not in ('Mes', ''):
            mes = MESES_NUM.get(mes_txt, mes_txt)
            overlay.show('Calculando estadísticas…')
            threading.Thread(
                target=lambda: self._tarea_stats(año, mes), daemon=True
            ).start()

    # ── Botón Actualizar ─────────────────────────────────────────────
    def actualizar(self):
        año = self.ids.sp_año.text
        mes_txt = self.ids.sp_mes.text
        if año in ('Año', '') or mes_txt in ('Mes', ''):
            return
        mes = MESES_NUM.get(mes_txt, mes_txt)
        overlay.show('Calculando estadísticas…')
        threading.Thread(target=lambda: self._tarea_stats(año, mes), daemon=True).start()

    # ── Consulta BD ──────────────────────────────────────────────────
    def _tarea_stats(self, anno, mes):
        d = {
            'año': anno, 'mes': mes,
            'fac': 0.0, 'rec': 0.0,
            'estratos': [], 'barrios': [],
            'huerfanos_n': 0, 'huerfanos_sum': 0.0,
            'sin_conexion': False,
        }
        conn = get_connection()
        if not conn:
            d['sin_conexion'] = True
            Clock.schedule_once(lambda *_: self._aplicar_stats(d), 0)
            return
        huerfanos = self._incluir_huerfanos
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT COALESCE(SUM(valor_recibo),0) FROM facturas WHERE anno=%s AND mes=%s",
                (anno, mes),
            )
            d['fac'] = float(cur.fetchone()[0])

            if huerfanos:
                cur.execute(
                    "SELECT COALESCE(SUM(valor_recibo),0) FROM recaudos WHERE anno=%s AND mes=%s",
                    (anno, mes),
                )
            else:
                cur.execute("""
                    SELECT COALESCE(SUM(r.valor_recibo), 0)
                    FROM recaudos r
                    INNER JOIN facturas f ON f.numero_factura = r.numero_factura
                    WHERE f.anno=%s AND f.mes=%s
                """, (anno, mes))
            d['rec'] = float(cur.fetchone()[0])

            if huerfanos:
                rec_subquery = """
                    SELECT cuenta_contrato, SUM(valor_recibo) AS total_rec
                    FROM recaudos WHERE anno = %s AND mes = %s
                    GROUP BY cuenta_contrato
                """
            else:
                rec_subquery = """
                    SELECT f.cuenta_contrato, SUM(r.valor_recibo) AS total_rec
                    FROM recaudos r
                    INNER JOIN facturas f ON f.numero_factura = r.numero_factura
                    WHERE f.anno = %s AND f.mes = %s
                    GROUP BY f.cuenta_contrato
                """

            cur.execute("""
                SELECT
                    COALESCE(s.estrato, 'Sin estrato')  AS grupo,
                    COUNT(DISTINCT s.cuenta)             AS total_sus,
                    COALESCE(SUM(fa.total_fac), 0)       AS facturado,
                    COALESCE(SUM(ra.total_rec), 0)       AS recaudado
                FROM suscriptores s
                LEFT JOIN (
                    SELECT cuenta_contrato, SUM(valor_recibo) AS total_fac
                    FROM facturas WHERE anno = %s AND mes = %s
                    GROUP BY cuenta_contrato
                ) fa ON fa.cuenta_contrato = s.cuenta
                LEFT JOIN ({}) ra ON ra.cuenta_contrato = s.cuenta
                GROUP BY s.estrato
                ORDER BY CAST(s.estrato AS UNSIGNED)
            """.format(rec_subquery), (anno, mes, anno, mes))
            d['estratos'] = cur.fetchall()

            cur.execute("""
                SELECT
                    COALESCE(s.barrio, 'Sin barrio')    AS grupo,
                    COUNT(DISTINCT s.cuenta)             AS total_sus,
                    COALESCE(SUM(fa.total_fac), 0)       AS facturado,
                    COALESCE(SUM(ra.total_rec), 0)       AS recaudado
                FROM suscriptores s
                LEFT JOIN (
                    SELECT cuenta_contrato, SUM(valor_recibo) AS total_fac
                    FROM facturas WHERE anno = %s AND mes = %s
                    GROUP BY cuenta_contrato
                ) fa ON fa.cuenta_contrato = s.cuenta
                LEFT JOIN ({}) ra ON ra.cuenta_contrato = s.cuenta
                GROUP BY s.barrio
                ORDER BY s.barrio
            """.format(rec_subquery), (anno, mes, anno, mes))
            d['barrios'] = cur.fetchall()

            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(r.valor_recibo), 0)
                FROM recaudos r
                WHERE NOT EXISTS (
                    SELECT 1 FROM facturas f
                    WHERE f.numero_factura = r.numero_factura
                )
            """)
            hrow = cur.fetchone()
            d['huerfanos_n']   = int(hrow[0])
            d['huerfanos_sum'] = float(hrow[1])

        except Exception as e:
            print(f'Error estadísticas stats: {e}')
        finally:
            cur.close()
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_stats(d), 0)

    # ── Aplicar resultados ───────────────────────────────────────────
    def _aplicar_stats(self, d):
        overlay.hide()
        if d['sin_conexion']:
            from kivy.app import App
            App.get_running_app().ir_sin_conexion(self.name)
            return

        año, mes = d['año'], d['mes']
        self.periodo_label = f"{MESES_NOMBRE.get(str(mes), mes)} {año}"

        fac     = d['fac']
        rec     = d['rec']
        cartera = max(0.0, fac - rec)
        pct     = (rec / fac * 100) if fac > 0 else 0.0

        self.ids.lbl_facturado.text = f'${fac:,.0f}'
        self.ids.lbl_recaudado.text = f'${rec:,.0f}'
        self.ids.lbl_cartera.text   = f'${cartera:,.0f}'
        self.ids.lbl_pct.text       = f'{pct:.1f}%'

        pct_col = SUCCESS if pct >= 80 else (WARNING if pct >= 50 else DANGER)
        self.ids.lbl_pct.color     = list(pct_col)
        self.ids.lbl_cartera.color = list(DANGER if cartera > 0 else SUCCESS)

        n_h = d.get('huerfanos_n', 0)
        s_h = d.get('huerfanos_sum', 0.0)
        if self._incluir_huerfanos:
            self.ids.lbl_aviso_huerfanos.text = (
                f'  ℹ  Modo: con huérfanos — incluye recaudos sin factura importada'
                f' ({n_h:,} globales por ${s_h:,.0f})'
            )
        elif n_h > 0:
            self.ids.lbl_aviso_huerfanos.text = (
                f'  ⚠  {n_h:,} recaudos por ${s_h:,.0f} sin factura importada'
                f' — no están incluidos en las cifras anteriores'
            )
        else:
            self.ids.lbl_aviso_huerfanos.text = ''

        self._datos = d
        self._render(self._vista)

    # ── Toggle estrato / barrio ──────────────────────────────────────
    def cambiar_vista(self, vista):
        self._vista = vista
        self.ids.btn_est.is_active = (vista == 'estrato')
        self.ids.btn_bar.is_active = (vista == 'barrio')
        self.ids.lbl_hdr_grupo.text = 'Barrio' if vista == 'barrio' else 'Estrato'
        if self._datos:
            self._render(vista)

    # ── Renderizar tabla ─────────────────────────────────────────────
    def _render(self, vista):
        rows  = self._datos.get('estratos' if vista == 'estrato' else 'barrios', [])
        tabla = self.ids.tabla_body
        tabla.clear_widgets()

        if not rows:
            tabla.add_widget(EmptyState(
                icon_text='○',
                message='Sin datos para este período',
                subtitle='Selecciona un año y mes con información disponible',
            ))
            return

        for i, (grupo, total_sus, facturado, recaudado) in enumerate(rows):
            facturado = float(facturado)
            recaudado = float(recaudado)
            cartera   = max(0.0, facturado - recaudado)
            pct       = (recaudado / facturado * 100) if facturado > 0 else 0.0
            pct_col   = SUCCESS if pct >= 80 else (WARNING if pct >= 50 else DANGER)
            bg        = CARD if i % 2 == 0 else STAGE
            hover_bg  = STAGE if i % 2 == 0 else (0.961, 0.945, 0.922, 1)

            fila = HoverRow(orientation='vertical', size_hint_y=None, height=48,
                            base_color=bg, hover_color=hover_bg)

            # Fila de datos
            top = BoxLayout(size_hint_y=None, height=38)
            for txt, sx, col in [
                (str(grupo),           0.20, TINTA),
                (f'{total_sus:,}',     0.10, TEXT_SEC),
                (f'${facturado:,.0f}', 0.22, TEXT_SEC),
                (f'${recaudado:,.0f}', 0.22, TEXT_SEC),
                (f'{pct:.1f}%',        0.10, pct_col),
                (f'${cartera:,.0f}',   0.16, DANGER if cartera > 0 else MUTED),
            ]:
                lbl = Label(text=txt, size_hint_x=sx, font_size=11, color=col,
                            halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
                top.add_widget(lbl)
            fila.add_widget(top)

            # Barra de progreso (% cobro)
            barra = _barra_pct(pct, pct_col)
            fila.add_widget(barra)
            tabla.add_widget(fila)


def _barra_pct(pct, color_fill):
    """Barra horizontal proporcional al porcentaje dado."""
    outer = BoxLayout(size_hint_y=None, height=6, padding=[4, 0, 4, 2])
    fill_ratio = min(max(pct / 100.0, 0.0), 1.0)
    rest_ratio = 1.0 - fill_ratio

    if fill_ratio > 0:
        fill = BoxLayout(size_hint_x=fill_ratio)
        with fill.canvas.before:
            Color(*color_fill)
            rf = Rectangle(pos=fill.pos, size=fill.size)
        fill.bind(pos=lambda _, v, r=rf: setattr(r, 'pos', v),
                  size=lambda _, v, r=rf: setattr(r, 'size', v))
        outer.add_widget(fill)

    if rest_ratio > 0:
        rest = BoxLayout(size_hint_x=rest_ratio)
        with rest.canvas.before:
            Color(*LINE)
            rr = Rectangle(pos=rest.pos, size=rest.size)
        rest.bind(pos=lambda _, v, r=rr: setattr(r, 'pos', v),
                  size=lambda _, v, r=rr: setattr(r, 'size', v))
        outer.add_widget(rest)

    return outer

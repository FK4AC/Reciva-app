from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty, ListProperty

from db.connection import get_connection
from theme import TINTA, STAGE, CARD, VERMILLON, LINE, MUTED, TEXT_SEC

MESES = {
    '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
    '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
    '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

_PAGE_SIZE = 50


class FacturacionScreen(Screen):
    mensaje             = StringProperty('')
    total_facturado     = StringProperty('—')
    total_recaudado     = StringProperty('—')
    deuda_periodo       = StringProperty('—')
    info_pendientes     = StringProperty('')
    barrios_disponibles = ListProperty(['Todos'])

    _pendientes_cache = []   # todos los pendientes del período (sin filtro)
    _pendientes_vis   = []   # pendientes después de aplicar búsqueda + barrio
    _pagina_actual    = 0
    _cargando         = False  # guard para no disparar callbacks durante reset

    def on_enter(self):
        self._cargar_periodos()

    # ------------------------------------------------------------------
    # Carga inicial de períodos disponibles y auto-selección del reciente
    # ------------------------------------------------------------------
    def _cargar_periodos(self):
        conn = get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT año FROM facturas WHERE año IS NOT NULL ORDER BY año DESC"
            )
            años = [str(r[0]) for r in cursor.fetchall()]
            sp_año = self.ids.spinner_año
            if años:
                sp_año.values = años
                if sp_año.text not in años:
                    sp_año.text = años[0]

            cursor.execute("""
                SELECT DISTINCT mes FROM facturas
                WHERE mes IS NOT NULL ORDER BY CAST(mes AS UNSIGNED)
            """)
            meses_db = [str(r[0]) for r in cursor.fetchall()]
            sp_mes = self.ids.spinner_mes
            if meses_db:
                sp_mes.values = meses_db
                if sp_mes.text not in meses_db:
                    sp_mes.text = meses_db[-1]

            cursor.execute("""
                SELECT año, mes FROM facturas
                WHERE año IS NOT NULL AND mes IS NOT NULL
                ORDER BY año DESC, CAST(mes AS UNSIGNED) DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                sp_año.text = str(row[0])
                sp_mes.text = str(row[1])
                self.consultar()

        except Exception as e:
            self.mensaje = f'Error: {e}'
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Consulta principal del período
    # ------------------------------------------------------------------
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

            # Sin LIMIT — cargamos todos los pendientes
            cursor.execute("""
                SELECT s.cuenta, s.nombre, s.barrio, f.valor_recibo
                FROM facturas f
                JOIN suscriptores s ON f.cuenta_contrato = s.cuenta
                WHERE f.año=%s AND f.mes=%s
                  AND f.cuenta_contrato NOT IN (
                      SELECT cuenta_contrato FROM recaudos WHERE año=%s AND mes=%s
                  )
                ORDER BY f.valor_recibo DESC
            """, (año, mes, año, mes))
            pendientes = cursor.fetchall()

            nombre_mes = MESES.get(mes, mes)
            self.mensaje = f'{nombre_mes} {año} — {len(pendientes)} pendientes de pago'

            # Actualizar barrios disponibles
            barrios = sorted({r[2] or '—' for r in pendientes})
            self.barrios_disponibles = ['Todos'] + barrios

            # Guardar cache y resetear estado de filtros sin disparar callbacks
            self._pendientes_cache = pendientes
            self._pagina_actual = 0

            self._cargando = True
            self.ids.buscador_pendiente.text = ''
            self.ids.spinner_barrio.text = 'Todos'
            self._cargando = False

            self._actualizar_tablas(estratos)
            self._aplicar_filtros()

        except Exception as e:
            self.mensaje = f'Error: {e}'
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Filtros: barrio y búsqueda (ambos se combinan)
    # ------------------------------------------------------------------
    def filtrar_barrio(self, barrio):
        if self._cargando:
            return
        self._pagina_actual = 0
        self._aplicar_filtros()

    def buscar_pendiente(self, texto):
        if self._cargando:
            return
        self._pagina_actual = 0
        self._aplicar_filtros()

    def _aplicar_filtros(self):
        barrio = self.ids.spinner_barrio.text
        texto  = self.ids.buscador_pendiente.text.strip().lower()

        datos = self._pendientes_cache

        if barrio and barrio != 'Todos':
            datos = [r for r in datos if (r[2] or '—') == barrio]

        if texto:
            datos = [r for r in datos
                     if texto in str(r[0]).lower()
                     or texto in (r[1] or '').lower()]

        self._pendientes_vis = datos
        self._renderizar_pendientes()

    # ------------------------------------------------------------------
    # Paginación
    # ------------------------------------------------------------------
    def pagina_anterior(self):
        if self._pagina_actual > 0:
            self._pagina_actual -= 1
            self._renderizar_pendientes()

    def pagina_siguiente(self):
        if not self._pendientes_vis:
            return
        max_pag = (len(self._pendientes_vis) - 1) // _PAGE_SIZE
        if self._pagina_actual < max_pag:
            self._pagina_actual += 1
            self._renderizar_pendientes()

    # ------------------------------------------------------------------
    # Render de tablas
    # ------------------------------------------------------------------
    def _actualizar_tablas(self, estratos):
        tabla = self.ids.tabla_estratos
        tabla.clear_widgets()
        for i, (estrato, count, total) in enumerate(estratos):
            bg = CARD if i % 2 == 0 else STAGE
            for val, col in [
                (str(estrato or '-'), TINTA),
                (str(count),          TEXT_SEC),
                (f'${float(total):,.0f}', TINTA),
            ]:
                lbl = Label(text=val, font_size=12, color=col)
                with lbl.canvas.before:
                    Color(*bg)
                    r = Rectangle(pos=lbl.pos, size=lbl.size)
                lbl.bind(pos=lambda inst, v, rr=r: setattr(rr, 'pos', v))
                lbl.bind(size=lambda inst, v, rr=r: setattr(rr, 'size', v))
                tabla.add_widget(lbl)

    def _renderizar_pendientes(self):
        lista = self.ids.lista_pendientes
        lista.clear_widgets()

        total = len(self._pendientes_vis)
        start = self._pagina_actual * _PAGE_SIZE
        end   = min(start + _PAGE_SIZE, total)
        page  = self._pendientes_vis[start:end]

        if total == 0:
            self.info_pendientes = 'Sin resultados'
        else:
            self.info_pendientes = f'{start + 1}–{end} de {total:,}'

        for i, (cuenta, nombre, barrio, valor) in enumerate(page):
            fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=36, spacing=2)
            bg = CARD if i % 2 == 0 else STAGE
            with fila.canvas.before:
                Color(*bg)
                rect = Rectangle(pos=fila.pos, size=fila.size)
            fila.bind(pos=lambda _, v, r=rect: setattr(r, 'pos', v))
            fila.bind(size=lambda _, v, r=rect: setattr(r, 'size', v))

            for txt, sx, col in [
                (str(cuenta),             0.15, TEXT_SEC),
                ((nombre or '')[:28],     0.36, TINTA),
                ((barrio or '—')[:16],    0.20, MUTED),
                (f'${float(valor):,.0f}', 0.15, VERMILLON),
            ]:
                lbl = Label(text=txt, size_hint_x=sx, font_size=12, color=col,
                            halign='left', valign='middle')
                lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
                fila.add_widget(lbl)

            btn = Button(
                text='Ver', size_hint_x=0.14, font_size=11,
                background_normal='', background_color=VERMILLON, color=(1, 1, 1, 1)
            )
            btn.bind(on_press=lambda _, c=cuenta: self._ver_suscriptor(c))
            fila.add_widget(btn)
            lista.add_widget(fila)

    def _ver_suscriptor(self, cuenta):
        sus = self.manager.get_screen('suscriptores')
        sus._ver_detalle(cuenta)

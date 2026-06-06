import csv
import os
from datetime import date

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock
import threading

from db.connection import get_connection
import utils.overlay as overlay
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
        overlay.show()
        threading.Thread(target=self._tarea_inicio, daemon=True).start()

    # ------------------------------------------------------------------
    # Carga inicial: períodos + datos del período más reciente (en hilo)
    # ------------------------------------------------------------------
    def _tarea_inicio(self):
        d = {'años': [], 'meses': [], 'año': None, 'mes': None,
             'fac': 0.0, 'rec': 0.0, 'estratos': [], 'pendientes': [], 'error': None}
        conn = get_connection()
        if not conn:
            d['error'] = 'Sin conexión'
            Clock.schedule_once(lambda *_: self._aplicar_datos(d), 0)
            return
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT año FROM facturas WHERE año IS NOT NULL ORDER BY año DESC"
            )
            anios_db = {str(r[0]) for r in cursor.fetchall()}
            anios_db.update({'2025', '2026'})
            d['años'] = sorted(anios_db, reverse=True)

            # Siempre mostrar los 12 meses
            d['meses'] = [str(i) for i in range(1, 13)]

            cursor.execute("""
                SELECT año, mes FROM facturas
                WHERE año IS NOT NULL AND mes IS NOT NULL
                ORDER BY año DESC, CAST(mes AS UNSIGNED) DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                año, mes = str(row[0]), str(row[1])
                d['año'], d['mes'] = año, mes
                self._consultar_periodo(cursor, año, mes, d)
            else:
                d['año'], d['mes'] = '2025', '1'
        except Exception as e:
            d['error'] = str(e)
        finally:
            cursor.close()
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_datos(d), 0)

    # ------------------------------------------------------------------
    # Consulta al presionar el botón (en hilo)
    # ------------------------------------------------------------------
    def consultar(self):
        año = self.ids.spinner_año.text
        mes = self.ids.spinner_mes.text
        if año in ('Año', '') or mes in ('Mes', ''):
            self.mensaje = 'Selecciona un período válido'
            return
        overlay.show('Cargando período…')
        threading.Thread(
            target=lambda: self._tarea_periodo(año, mes), daemon=True
        ).start()

    def _tarea_periodo(self, año, mes):
        d = {'años': None, 'meses': None, 'año': año, 'mes': mes,
             'fac': 0.0, 'rec': 0.0, 'estratos': [], 'pendientes': [], 'error': None}
        conn = get_connection()
        if not conn:
            d['error'] = 'Sin conexión'
            Clock.schedule_once(lambda *_: self._aplicar_datos(d), 0)
            return
        cursor = conn.cursor()
        try:
            self._consultar_periodo(cursor, año, mes, d)
        except Exception as e:
            d['error'] = str(e)
        finally:
            cursor.close()
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_datos(d), 0)

    def _consultar_periodo(self, cursor, año, mes, d):
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
            SELECT estrato_contrato, COUNT(*), SUM(valor_recibo)
            FROM facturas WHERE año=%s AND mes=%s
            GROUP BY estrato_contrato ORDER BY estrato_contrato
        """, (año, mes))
        d['estratos'] = cursor.fetchall()
        cursor.execute("""
            SELECT f.cuenta_contrato,
                   COALESCE(s.nombre, f.cuenta_contrato) AS nombre,
                   COALESCE(s.barrio, '—')               AS barrio,
                   f.valor_recibo
            FROM facturas f
            LEFT JOIN suscriptores s ON s.cuenta = f.cuenta_contrato
            WHERE f.año=%s AND f.mes=%s
              AND NOT EXISTS (
                  SELECT 1 FROM recaudos r
                  WHERE r.cuenta_contrato = f.cuenta_contrato
                    AND r.año = f.año AND r.mes = f.mes
              )
            ORDER BY f.valor_recibo DESC
        """, (año, mes))
        d['pendientes'] = cursor.fetchall()

    def _aplicar_datos(self, d):
        overlay.hide()
        if d['error']:
            if 'conexión' in d['error'].lower() or d['error'] == 'Sin conexión':
                from kivy.app import App
                App.get_running_app().ir_sin_conexion(self.name)
            else:
                self.mensaje = f'Error: {d["error"]}'
            return
        # Actualizar spinners solo si vienen del inicio
        if d['años'] is not None:
            sp_año = self.ids.spinner_año
            sp_año.values = d['años']
            sp_año.text = d['año'] or (d['años'][0] if d['años'] else '')
        if d['meses'] is not None:
            sp_mes = self.ids.spinner_mes
            sp_mes.values = d['meses']
            sp_mes.text = d['mes'] or (d['meses'][-1] if d['meses'] else '')
        if not d['año']:
            return
        año, mes = d['año'], d['mes']
        self.total_facturado = f'${d["fac"]:,.0f}'
        self.total_recaudado = f'${d["rec"]:,.0f}'
        self.deuda_periodo   = f'${max(0, d["fac"] - d["rec"]):,.0f}'
        pendientes = d['pendientes']
        self.mensaje = f'{MESES.get(mes, mes)} {año} — {len(pendientes)} pendientes de pago'
        barrios = sorted({r[2] or '—' for r in pendientes})
        self.barrios_disponibles = ['Todos'] + barrios
        self._pendientes_cache = pendientes
        self._pagina_actual = 0
        self._cargando = True
        self.ids.buscador_pendiente.text = ''
        self.ids.spinner_barrio.text = 'Todos'
        self._cargando = False
        self._actualizar_tablas(d['estratos'])
        self._aplicar_filtros()

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

    # ------------------------------------------------------------------
    # Exportar pendientes visibles a CSV
    # ------------------------------------------------------------------
    def exportar_csv(self):
        datos = self._pendientes_vis
        if not datos:
            self.mensaje = 'No hay pendientes para exportar'
            return

        año = self.ids.spinner_año.text
        mes = self.ids.spinner_mes.text
        nombre_archivo = f'pendientes_{año}_{mes.zfill(2)}_{date.today()}.csv'
        ruta = os.path.join(os.path.expanduser('~'), 'Documents', nombre_archivo)

        try:
            with open(ruta, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Cuenta', 'Nombre', 'Barrio', 'Valor pendiente'])
                for cuenta, nombre, barrio, valor in datos:
                    writer.writerow([cuenta, nombre or '', barrio or '', f'{float(valor):.2f}'])
            self.mensaje = f'CSV guardado: {nombre_archivo}'
            os.startfile(ruta)
        except Exception as e:
            self.mensaje = f'Error al exportar: {e}'

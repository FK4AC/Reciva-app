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
from theme import (TINTA, STAGE, CARD, VERMILLON,
                   MUTED, TEXT_SEC, SUCCESS, WARNING)

MESES = {
    '1': 'Enero',  '2': 'Febrero',  '3': 'Marzo',    '4': 'Abril',
    '5': 'Mayo',   '6': 'Junio',    '7': 'Julio',     '8': 'Agosto',
    '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}


def _fmt_fecha(fecha):
    """Convierte una fecha a DD/MM/YY; devuelve '—' si es None."""
    if not fecha:
        return '—'
    s = str(fecha)[:10]
    try:
        from datetime import datetime
        return datetime.strptime(s, '%Y-%m-%d').strftime('%d/%m/%y')
    except Exception:
        return s

_PAGE_SIZE = 50


class FacturacionScreen(Screen):
    mensaje             = StringProperty('')
    total_facturado     = StringProperty('—')
    total_recaudado     = StringProperty('—')
    deuda_periodo       = StringProperty('—')
    info_lista          = StringProperty('')
    barrios_disponibles = ListProperty(['Todos'])

    _vista_activa = 'pendientes'   # 'pendientes' | 'pagadas' | 'recaudos_mes'

    _pendientes_cache = []
    _pendientes_vis   = []
    _pagadas_cache    = []
    _pagadas_vis      = []
    _recaudos_cache   = []
    _recaudos_vis     = []

    _pagina_actual = 0
    _cargando      = False

    def on_enter(self):
        overlay.show()
        threading.Thread(target=self._tarea_inicio, daemon=True).start()

    # ------------------------------------------------------------------
    # Carga inicial
    # ------------------------------------------------------------------
    def _tarea_inicio(self):
        d = {'años': [], 'meses': [], 'año': None, 'mes': None,
             'fac': 0.0, 'rec': 0.0, 'estratos': [],
             'pendientes': [], 'pagadas': [], 'recaudos_mes': [], 'error': None}
        conn = get_connection()
        if not conn:
            d['error'] = 'Sin conexión'
            Clock.schedule_once(lambda *_: self._aplicar_datos(d), 0)
            return
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT anno FROM facturas WHERE anno IS NOT NULL ORDER BY anno DESC"
            )
            anios_db = {str(r[0]) for r in cursor.fetchall()}
            anios_db.update({'2025', '2026'})
            d['años'] = sorted(anios_db, reverse=True)
            d['meses'] = [str(i) for i in range(1, 13)]
            cursor.execute("""
                SELECT anno, mes FROM facturas
                WHERE anno IS NOT NULL AND mes IS NOT NULL
                ORDER BY anno DESC, CAST(mes AS UNSIGNED) DESC LIMIT 1
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
    # Consulta manual
    # ------------------------------------------------------------------
    def consultar(self):
        año = self.ids.spinner_año.text
        mes = self.ids.spinner_mes.text
        if año in ('Año', '') or mes in ('Mes', ''):
            self.mensaje = 'Selecciona un período válido'
            return
        overlay.show('Cargando período…')
        threading.Thread(target=lambda: self._tarea_periodo(año, mes), daemon=True).start()

    def _tarea_periodo(self, anno, mes):
        d = {'años': None, 'meses': None, 'año': anno, 'mes': mes,
             'fac': 0.0, 'rec': 0.0, 'estratos': [],
             'pendientes': [], 'pagadas': [], 'recaudos_mes': [], 'error': None}
        conn = get_connection()
        if not conn:
            d['error'] = 'Sin conexión'
            Clock.schedule_once(lambda *_: self._aplicar_datos(d), 0)
            return
        cursor = conn.cursor()
        try:
            self._consultar_periodo(cursor, anno, mes, d)
        except Exception as e:
            d['error'] = str(e)
        finally:
            cursor.close()
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_datos(d), 0)

    def _consultar_periodo(self, cursor, año, mes, d):
        # Facturado
        cursor.execute(
            "SELECT COALESCE(SUM(valor_recibo), 0) FROM facturas WHERE anno=%s AND mes=%s",
            (año, mes)
        )
        d['fac'] = float(cursor.fetchone()[0])

        # Recaudado del período (por número de factura)
        cursor.execute("""
            SELECT COALESCE(SUM(r.valor_recibo), 0)
            FROM recaudos r
            INNER JOIN facturas f ON f.numero_factura = r.numero_factura
            WHERE f.anno=%s AND f.mes=%s
        """, (año, mes))
        d['rec'] = float(cursor.fetchone()[0])

        # Por estrato (desde catastro, fuente autoritativa)
        cursor.execute("""
            SELECT COALESCE(s.estrato, '—'), COUNT(*), SUM(f.valor_recibo)
            FROM facturas f
            LEFT JOIN suscriptores s ON s.susccodi = f.susccodi
            WHERE f.anno=%s AND f.mes=%s
            GROUP BY s.estrato ORDER BY s.estrato
        """, (año, mes))
        d['estratos'] = cursor.fetchall()

        # Pendientes — facturas sin recaudo
        cursor.execute("""
            SELECT f.cuenta_contrato,
                   COALESCE(s.nombre, CAST(f.cuenta_contrato AS CHAR)) AS nombre,
                   COALESCE(s.barrio, '—') AS barrio,
                   f.valor_recibo
            FROM facturas f
            LEFT JOIN suscriptores s ON s.cuenta = f.cuenta_contrato
            WHERE f.anno=%s AND f.mes=%s
              AND NOT EXISTS (
                  SELECT 1 FROM recaudos r WHERE r.numero_factura = f.numero_factura
              )
            ORDER BY f.valor_recibo DESC
        """, (año, mes))
        d['pendientes'] = cursor.fetchall()

        # Pagadas — con indicador de retraso
        cursor.execute("""
            SELECT f.cuenta_contrato,
                   COALESCE(s.nombre, CAST(f.cuenta_contrato AS CHAR)) AS nombre,
                   COALESCE(s.barrio, '—') AS barrio,
                   f.valor_recibo,
                   r.fecha_recaudo,
                   CASE WHEN r.fecha_recaudo > LAST_DAY(
                       STR_TO_DATE(CONCAT(f.anno, '-', LPAD(f.mes, 2, '0'), '-01'), '%%Y-%%m-%%d')
                   ) THEN 1 ELSE 0 END AS tarde
            FROM facturas f
            INNER JOIN recaudos r ON r.numero_factura = f.numero_factura
            LEFT  JOIN suscriptores s ON s.cuenta = f.cuenta_contrato
            WHERE f.anno=%s AND f.mes=%s
            ORDER BY tarde DESC, r.fecha_recaudo DESC
        """, (año, mes))
        d['pagadas'] = cursor.fetchall()

        # Recaudos del mes — por fecha real de pago
        cursor.execute("""
            SELECT r.cuenta_contrato,
                   COALESCE(s.nombre, CAST(r.cuenta_contrato AS CHAR)) AS nombre,
                   r.valor_recibo,
                   r.fecha_recaudo,
                   r.anno  AS año_factura,
                   r.mes  AS mes_factura
            FROM recaudos r
            LEFT JOIN suscriptores s ON s.cuenta = r.cuenta_contrato
            WHERE YEAR(r.fecha_recaudo) = %s AND MONTH(r.fecha_recaudo) = %s
            ORDER BY r.fecha_recaudo DESC
        """, (int(año), int(mes)))
        d['recaudos_mes'] = cursor.fetchall()

    # ------------------------------------------------------------------
    # Aplicar datos al UI
    # ------------------------------------------------------------------
    def _aplicar_datos(self, d):
        overlay.hide()
        if d['error']:
            if 'conexión' in d['error'].lower() or d['error'] == 'Sin conexión':
                from kivy.app import App
                App.get_running_app().ir_sin_conexion(self.name)
            else:
                self.mensaje = f'Error: {d["error"]}'
            return
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

        self.total_facturado = f'${d["fac"]:,.0f}'
        self.total_recaudado = f'${d["rec"]:,.0f}'
        self.deuda_periodo   = f'${max(0, d["fac"] - d["rec"]):,.0f}'

        self._pendientes_cache = d['pendientes']
        self._pagadas_cache    = d['pagadas']
        self._recaudos_cache   = d['recaudos_mes']

        barrios = sorted({r[2] or '—' for r in d['pendientes']})
        self.barrios_disponibles = ['Todos'] + barrios

        self._pagina_actual = 0
        self._cargando = True
        self.ids.buscador.text = ''
        self.ids.spinner_barrio.text = 'Todos'
        self._cargando = False

        self._actualizar_tablas(d['estratos'])
        self._aplicar_filtros()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def cambiar_vista(self, vista):
        self._vista_activa = vista
        self._pagina_actual = 0
        self._cargando = True
        self.ids.buscador.text = ''
        self._cargando = False

        # Mostrar u ocultar filtro de barrio (solo para pendientes)
        box_barrio = self.ids.box_barrio
        if vista == 'pendientes':
            box_barrio.size_hint_x = None
            box_barrio.width       = 148
            box_barrio.opacity     = 1
            box_barrio.disabled    = False
        else:
            box_barrio.size_hint_x = None
            box_barrio.width       = 0
            box_barrio.opacity     = 0
            box_barrio.disabled    = True

        # Activar/desactivar tabs (TabButton.is_active maneja el estilo)
        mapa = {
            'pendientes':   self.ids.tab_pendientes,
            'pagadas':      self.ids.tab_pagadas,
            'recaudos_mes': self.ids.tab_recaudos,
        }
        for k, btn in mapa.items():
            btn.is_active = (k == vista)

        self._actualizar_cabecera()
        self._aplicar_filtros()

    def _actualizar_cabecera(self):
        cab = self.ids.cabecera_lista
        cab.clear_widgets()

        def _lbl(txt, sx):
            l = Label(text=txt, size_hint_x=sx, font_size=11, bold=True,
                      color=(0.906, 0.863, 0.812, 1),
                      halign='left', valign='middle')
            l.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
            cab.add_widget(l)

        if self._vista_activa == 'pendientes':
            _lbl('Cuenta',  0.15)
            _lbl('Nombre',  0.36)
            _lbl('Barrio',  0.20)
            _lbl('Valor',   0.15)
            _lbl('',        0.14)
        elif self._vista_activa == 'pagadas':
            _lbl('Cuenta',  0.13)
            _lbl('Nombre',  0.28)
            _lbl('Valor',   0.13)
            _lbl('Pagó el', 0.14)
            _lbl('Estado',  0.23)
            _lbl('',        0.09)
        else:  # recaudos_mes
            _lbl('Cuenta',     0.13)
            _lbl('Nombre',     0.28)
            _lbl('Valor',      0.13)
            _lbl('Fecha pago', 0.14)
            _lbl('Período',    0.23)
            _lbl('',           0.09)

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------
    def filtrar_barrio(self, barrio):
        if self._cargando:
            return
        self._pagina_actual = 0
        self._aplicar_filtros()

    def buscar(self, texto):
        if self._cargando:
            return
        self._pagina_actual = 0
        self._aplicar_filtros()

    def _aplicar_filtros(self):
        texto  = self.ids.buscador.text.strip().lower()
        barrio = self.ids.spinner_barrio.text

        def _filtro_texto(datos, i_cuenta=0, i_nombre=1):
            if not texto:
                return datos
            return [r for r in datos
                    if texto in str(r[i_cuenta]).lower()
                    or texto in (r[i_nombre] or '').lower()]

        if self._vista_activa == 'pendientes':
            datos = self._pendientes_cache
            if barrio and barrio != 'Todos':
                datos = [r for r in datos if (r[2] or '—') == barrio]
            self._pendientes_vis = _filtro_texto(datos)
        elif self._vista_activa == 'pagadas':
            self._pagadas_vis = _filtro_texto(self._pagadas_cache)
        else:
            self._recaudos_vis = _filtro_texto(self._recaudos_cache)

        self._renderizar_lista()

    # ------------------------------------------------------------------
    # Paginación
    # ------------------------------------------------------------------
    def _vis_actual(self):
        if self._vista_activa == 'pendientes':
            return self._pendientes_vis
        elif self._vista_activa == 'pagadas':
            return self._pagadas_vis
        return self._recaudos_vis

    def pagina_anterior(self):
        if self._pagina_actual > 0:
            self._pagina_actual -= 1
            self._renderizar_lista()

    def pagina_siguiente(self):
        vis = self._vis_actual()
        if not vis:
            return
        max_pag = (len(vis) - 1) // _PAGE_SIZE
        if self._pagina_actual < max_pag:
            self._pagina_actual += 1
            self._renderizar_lista()

    # ------------------------------------------------------------------
    # Render tablas
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
        self._actualizar_cabecera()

    def _renderizar_lista(self):
        lista = self.ids.lista_principal
        lista.clear_widgets()

        vis   = self._vis_actual()
        total = len(vis)
        start = self._pagina_actual * _PAGE_SIZE
        end   = min(start + _PAGE_SIZE, total)
        page  = vis[start:end]

        self.info_lista = f'{start + 1}–{end} de {total:,}' if total else 'Sin resultados'

        mes_txt = self.ids.spinner_mes.text
        año_txt = self.ids.spinner_año.text
        nom_mes = MESES.get(mes_txt, mes_txt)

        if self._vista_activa == 'pendientes':
            self.mensaje = f'{nom_mes} {año_txt} — {total} pendientes'
        elif self._vista_activa == 'pagadas':
            tarde = sum(1 for r in vis if r[5])
            self.mensaje = (f'{nom_mes} {año_txt} — {total} pagadas'
                            + (f'  ({tarde} con retraso)' if tarde else ''))
        else:
            self.mensaje = f'Cobrado en {nom_mes} {año_txt} — {total} pagos'

        for i, row in enumerate(page):
            fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=36, spacing=2)
            bg = CARD if i % 2 == 0 else STAGE
            with fila.canvas.before:
                Color(*bg)
                rect = Rectangle(pos=fila.pos, size=fila.size)
            fila.bind(pos=lambda _, v, r=rect: setattr(r, 'pos', v))
            fila.bind(size=lambda _, v, r=rect: setattr(r, 'size', v))

            def _lbl(txt, sx, col, bold=False):
                l = Label(text=str(txt), size_hint_x=sx, font_size=12,
                          color=col, bold=bold, halign='left', valign='middle')
                l.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
                fila.add_widget(l)

            def _btn(cuenta):
                b = Button(text='Ver', size_hint_x=0.09, font_size=11,
                           background_normal='', background_color=VERMILLON, color=(1, 1, 1, 1))
                b.bind(on_press=lambda _, c=cuenta: self._ver_suscriptor(c))
                fila.add_widget(b)

            if self._vista_activa == 'pendientes':
                cuenta, nombre, barrio, valor = row
                _lbl(cuenta,                    0.15, TEXT_SEC)
                _lbl((nombre or '')[:28],        0.36, TINTA)
                _lbl((barrio or '—')[:16],       0.20, MUTED)
                _lbl(f'${float(valor):,.0f}',    0.15, VERMILLON)
                b = Button(text='Ver', size_hint_x=0.14, font_size=11,
                           background_normal='', background_color=VERMILLON, color=(1, 1, 1, 1))
                b.bind(on_press=lambda _, c=cuenta: self._ver_suscriptor(c))
                fila.add_widget(b)

            elif self._vista_activa == 'pagadas':
                cuenta, nombre, barrio, valor, fecha_rec, tarde = row
                fecha_txt = _fmt_fecha(fecha_rec)
                tarde_bool = bool(tarde)
                _lbl(cuenta,                    0.13, TEXT_SEC)
                _lbl((nombre or '')[:24],        0.28, TINTA)
                _lbl(f'${float(valor):,.0f}',    0.13, TINTA)
                _lbl(fecha_txt,                  0.14, MUTED)
                estado_col = WARNING if tarde_bool else SUCCESS
                estado_txt = '⚠ Con retraso' if tarde_bool else '✓ A tiempo'
                _lbl(estado_txt, 0.23, estado_col, bold=True)
                _btn(cuenta)

            else:  # recaudos_mes
                cuenta, nombre, valor, fecha_rec, año_fac, mes_fac = row
                fecha_txt   = _fmt_fecha(fecha_rec)
                nom_fac     = MESES.get(str(mes_fac), str(mes_fac))[:3] if mes_fac else '—'
                periodo_txt = f'{nom_fac} {año_fac}' if mes_fac else '—'
                _lbl(cuenta,                    0.13, TEXT_SEC)
                _lbl((nombre or '')[:24],        0.28, TINTA)
                _lbl(f'${float(valor):,.0f}',    0.13, TINTA)
                _lbl(fecha_txt,                  0.14, MUTED)
                _lbl(periodo_txt,                0.23, TEXT_SEC)
                _btn(cuenta)

            lista.add_widget(fila)

        if not page:
            from widgets.components import EmptyState
            lista.add_widget(EmptyState(
                icon_text='○',
                message='Sin facturas para este período',
                subtitle='Consulta otro mes o cambia los filtros',
            ))

    def _ver_suscriptor(self, cuenta):
        sus = self.manager.get_screen('suscriptores')
        sus._ver_detalle(cuenta)

    # ------------------------------------------------------------------
    # Exportar CSV
    # ------------------------------------------------------------------
    def exportar_csv(self):
        vis = self._vis_actual()
        if not vis:
            self.mensaje = 'No hay datos para exportar'
            return
        año = self.ids.spinner_año.text
        mes = self.ids.spinner_mes.text
        nombre_archivo = f'{self._vista_activa}_{año}_{mes.zfill(2)}_{date.today()}.csv'
        ruta = os.path.join(os.path.expanduser('~'), 'Documents', nombre_archivo)
        try:
            with open(ruta, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                if self._vista_activa == 'pendientes':
                    writer.writerow(['Cuenta', 'Nombre', 'Barrio', 'Valor pendiente'])
                    for cuenta, nombre, barrio, valor in vis:
                        writer.writerow([cuenta, nombre or '', barrio or '', f'{float(valor):.2f}'])
                elif self._vista_activa == 'pagadas':
                    writer.writerow(['Cuenta', 'Nombre', 'Valor', 'Fecha pago', 'Estado'])
                    for cuenta, nombre, barrio, valor, fecha_rec, tarde in vis:
                        writer.writerow([cuenta, nombre or '', f'{float(valor):.2f}',
                                         str(fecha_rec or ''), 'Con retraso' if tarde else 'A tiempo'])
                else:
                    writer.writerow(['Cuenta', 'Nombre', 'Valor', 'Fecha pago', 'Año factura', 'Mes factura'])
                    for cuenta, nombre, valor, fecha_rec, año_fac, mes_fac in vis:
                        writer.writerow([cuenta, nombre or '', f'{float(valor):.2f}',
                                         str(fecha_rec or ''), año_fac, mes_fac])
            self.mensaje = f'CSV guardado: {nombre_archivo}'
            os.startfile(ruta)
        except Exception as e:
            self.mensaje = f'Error al exportar: {e}'

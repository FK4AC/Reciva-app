from datetime import datetime

from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import StringProperty
from kivy.uix.widget import Widget

from kivy.clock import Clock
import threading
from db.connection import get_connection
import utils.overlay as overlay
from utils.email_smtp import enviar_respuesta_pqr
from theme import (TINTA, BG, STAGE, CARD, VERMILLON, LADRILLO,
                   LINE, MUTED, TEXT_SEC, SUCCESS, WARNING, DANGER)
from widgets.components import PillButton, PopupHeader, EmptyState

TIPOS   = ['Petición', 'Queja', 'Recurso', 'Reclamo']
ESTADOS = ['Abierto', 'En Proceso', 'Resuelto']

COLOR_ESTADO = {
    'Abierto':    DANGER,
    'En Proceso': WARNING,
    'Resuelto':   SUCCESS,
}
COLOR_TIPO = {
    'Petición': (0.200, 0.470, 0.820, 1),
    'Queja':    DANGER,
    'Recurso':  WARNING,
    'Reclamo':  (0.550, 0.180, 0.750, 1),
}


class TicketsScreen(Screen):
    mensaje = StringProperty('')

    def on_enter(self):
        self.ids.lista_pqr.clear_widgets()
        overlay.show()
        threading.Thread(target=self._tarea_lista, daemon=True).start()

    def cargar_lista(self):
        estado = self.ids.filtro_estado.text
        tipo   = self.ids.filtro_tipo.text
        self.ids.lista_pqr.clear_widgets()
        overlay.show()
        threading.Thread(
            target=lambda: self._tarea_lista(estado, tipo), daemon=True
        ).start()

    def _tarea_lista(self, estado='Todos', tipo='Todos'):
        rows, error = [], None
        conn = get_connection()
        if not conn:
            Clock.schedule_once(lambda *_: self._aplicar_lista([], 'Error de conexión'), 0)
            return
        cursor = conn.cursor()
        try:
            where, params = [], []
            if estado != 'Todos':
                where.append("estado=%s"); params.append(estado)
            if tipo != 'Todos':
                where.append("tipo=%s");   params.append(tipo)
            sql = ("SELECT id, nombre_suscriptor, tipo, asunto, estado, "
                   "DATE(fecha_creacion), COALESCE(origen,'sistema') FROM pqr")
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY fecha_creacion DESC LIMIT 200"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        except Exception as e:
            error = str(e)
        finally:
            cursor.close()
            conn.close()
        Clock.schedule_once(lambda *_: self._aplicar_lista(rows, error), 0)

    def _aplicar_lista(self, rows, error):
        overlay.hide()
        if error:
            if 'conexión' in error.lower() or error == 'Error de conexión':
                from kivy.app import App
                App.get_running_app().ir_sin_conexion(self.name)
            else:
                self.mensaje = f'Error: {error}'
            return
        lista = self.ids.lista_pqr
        self.mensaje = f'{len(rows)} PQR encontradas'
        for i, row in enumerate(rows):
            lista.add_widget(self._fila(*row, idx=i))
        if not rows:
            lista.add_widget(EmptyState(
                icon_text='○',
                message='Sin PQR registradas',
                subtitle='No hay resultados con los filtros actuales',
            ))

    def _fila(self, pqr_id, nombre, tipo, asunto, estado, fecha, origen='sistema', idx=0):
        fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=38, spacing=2)
        bg = CARD if idx % 2 == 0 else STAGE
        with fila.canvas.before:
            Color(*bg)
            rect = Rectangle(pos=fila.pos, size=fila.size)
        fila.bind(pos=lambda _, v, r=rect: setattr(r, 'pos', v))
        fila.bind(size=lambda _, v, r=rect: setattr(r, 'size', v))

        col_e = COLOR_ESTADO.get(estado, MUTED)
        col_t = COLOR_TIPO.get(tipo,    MUTED)
        es_web = (origen == 'web')

        # Col #ID
        lbl_id = Label(text=f'#{pqr_id}', size_hint_x=0.06, font_size=12,
                       color=MUTED, halign='left', valign='middle')
        lbl_id.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
        fila.add_widget(lbl_id)

        # Col Suscriptor — badge WEB coloreado + nombre
        col_nombre = BoxLayout(size_hint_x=0.25, spacing=4, padding=[2, 6, 2, 6])
        if es_web:
            badge = BoxLayout(size_hint_x=None, width=36)
            with badge.canvas.before:
                Color(0.200, 0.470, 0.820, 1)
                _bd = RoundedRectangle(pos=badge.pos, size=badge.size, radius=[8])
            badge.bind(pos=lambda _, v, r=_bd: setattr(r, 'pos', v),
                       size=lambda _, v, r=_bd: setattr(r, 'size', v))
            badge.add_widget(Label(text='WEB', color=(1,1,1,1), bold=True, font_size=9))
            col_nombre.add_widget(badge)
        lbl_n = Label(text=(nombre or '-')[:20], font_size=12,
                      color=(0.200, 0.470, 0.820, 1) if es_web else TINTA,
                      halign='left', valign='middle')
        lbl_n.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 2, v[1])))
        col_nombre.add_widget(lbl_n)
        fila.add_widget(col_nombre)

        # Resto de columnas
        fecha_fmt = str(fecha)
        if fecha_fmt and len(fecha_fmt) == 10:
            try:
                from datetime import datetime
                fecha_fmt = datetime.strptime(fecha_fmt, '%Y-%m-%d').strftime('%d/%m/%y')
            except Exception:
                pass

        for txt, sx, col in [
            (tipo or '-',            0.12, col_t),
            ((asunto or '-')[:28],   0.26, TEXT_SEC),
            (estado or '-',          0.13, col_e),
            (fecha_fmt,              0.11, MUTED),
        ]:
            lbl = Label(text=txt, size_hint_x=sx, font_size=12, color=col,
                        halign='left', valign='middle')
            lbl.bind(size=lambda inst, v: setattr(inst, 'text_size', (v[0] - 4, v[1])))
            fila.add_widget(lbl)

        btn = Button(text='Ver', size_hint_x=0.07, font_size=12,
                     background_normal='', background_color=VERMILLON, color=(1,1,1,1))
        btn.bind(on_press=lambda _, pid=pqr_id: self._ver_pqr(pid))
        fila.add_widget(btn)
        return fila

    # ------------------------------------------------------------------
    #  Popup: Nueva PQR
    # ------------------------------------------------------------------
    def nueva_pqr(self):
        state = {'cuenta': None, 'nombre': None}

        def _pill(text, bg, fg=(1, 1, 1, 1), w=120):
            return PillButton(text=text, bg_color=bg, fg_color=fg,
                              size_hint_x=None, width=w, font_size=12,
                              pill_radius=20)

        def _inp(hint, multiline=False, height=38):
            return TextInput(
                hint_text=hint, multiline=multiline,
                size_hint_y=None, height=height,
                background_color=CARD, foreground_color=TINTA,
                cursor_color=VERMILLON, hint_text_color=MUTED,
                padding=[8, 10], font_size=12,
            )

        # ── Root ──
        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            _bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(_bg, 'pos', v),
                     size=lambda _, v: setattr(_bg, 'size', v))

        # ── Franja TINTA ──
        top = BoxLayout(size_hint_y=None, height=52, padding=[18, 0])
        with top.canvas.before:
            Color(*TINTA)
            _top = Rectangle(pos=top.pos, size=top.size)
        top.bind(pos=lambda _, v: setattr(_top, 'pos', v),
                 size=lambda _, v: setattr(_top, 'size', v))
        top.add_widget(Label(
            text='Nueva PQR', bold=True, font_size=16,
            color=(1, 1, 1, 1), halign='left', valign='middle',
        ))
        content.add_widget(top)

        # ── Body ──
        body = BoxLayout(orientation='vertical', spacing=10, padding=[18, 12, 18, 0])
        content.add_widget(body)

        # Sección búsqueda
        body.add_widget(Label(
            text='Suscriptor (opcional)', color=VERMILLON, bold=True,
            font_size=12, size_hint_y=None, height=22,
            halign='left', valign='middle',
        ))

        buscar_box = BoxLayout(size_hint_y=None, height=40, spacing=8)
        pill_wrap = BoxLayout(padding=[12, 0, 8, 0])
        with pill_wrap.canvas.before:
            Color(1, 1, 1, 1)
            _pw = RoundedRectangle(pos=pill_wrap.pos, size=pill_wrap.size, radius=[20])
            Color(*LINE)
            _pl = RoundedRectangle(pos=(pill_wrap.x+1, pill_wrap.y+1),
                                   size=(pill_wrap.width-2, pill_wrap.height-2), radius=[19])
        pill_wrap.bind(
            pos=lambda _, v, a=_pw, b=_pl: (
                setattr(a, 'pos', v),
                setattr(b, 'pos', (v[0]+1, v[1]+1))
            ),
            size=lambda _, v, a=_pw, b=_pl: (
                setattr(a, 'size', v),
                setattr(b, 'size', (v[0]-2, v[1]-2))
            ),
        )
        inp_buscar = TextInput(
            hint_text='Cuenta o nombre...', multiline=False,
            background_color=(0, 0, 0, 0), background_normal='', background_active='',
            foreground_color=TINTA, cursor_color=VERMILLON,
            hint_text_color=MUTED, padding=[4, 10], font_size=12,
        )
        pill_wrap.add_widget(inp_buscar)
        buscar_box.add_widget(pill_wrap)
        btn_buscar = _pill('Buscar', VERMILLON, w=100)
        buscar_box.add_widget(btn_buscar)
        body.add_widget(buscar_box)

        # Resultados
        res_scroll = ScrollView(size_hint_y=None, height=80)
        res_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=2)
        res_box.bind(minimum_height=res_box.setter('height'))
        res_scroll.add_widget(res_box)
        body.add_widget(res_scroll)

        # Suscriptor seleccionado
        lbl_sel = Label(
            text='Sin suscriptor seleccionado',
            color=MUTED, italic=True, font_size=11,
            size_hint_y=None, height=24, halign='left', valign='middle',
        )
        lbl_sel.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        body.add_widget(lbl_sel)

        # Separador
        div = BoxLayout(size_hint_y=None, height=1)
        with div.canvas.before:
            Color(*LINE)
            Rectangle(pos=div.pos, size=div.size)
        body.add_widget(div)

        # Formulario
        form = GridLayout(cols=2, size_hint_y=None, spacing=[8, 6])
        form.bind(minimum_height=form.setter('height'))

        def _lbl_form(text, h=38):
            l = Label(text=text, color=VERMILLON, bold=True,
                      halign='right', valign='middle', size_hint_y=None, height=h)
            l.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
            return l

        # Tipo
        form.add_widget(_lbl_form('Tipo *'))
        sp_wrap = BoxLayout(size_hint_y=None, height=38)
        with sp_wrap.canvas.before:
            Color(*STAGE)
            _sw = Rectangle(pos=sp_wrap.pos, size=sp_wrap.size)
        sp_wrap.bind(pos=lambda _, v, r=_sw: setattr(r, 'pos', v),
                     size=lambda _, v, r=_sw: setattr(r, 'size', v))
        sp_tipo = Spinner(text='Queja', values=TIPOS,
                          background_color=(0, 0, 0, 0), background_normal='',
                          color=TINTA, font_size=12)
        sp_wrap.add_widget(sp_tipo)
        form.add_widget(sp_wrap)

        form.add_widget(_lbl_form('Asunto *'))
        inp_asunto = _inp('Describe el asunto brevemente...')
        form.add_widget(inp_asunto)

        form.add_widget(_lbl_form('Descripción', h=72))
        inp_desc = _inp('Detalle adicional...', multiline=True, height=72)
        form.add_widget(inp_desc)

        body.add_widget(form)

        lbl_err = Label(text='', color=DANGER, font_size=11,
                        size_hint_y=None, height=22)
        body.add_widget(lbl_err)

        # ── Pie ──
        pie = BoxLayout(size_hint_y=None, height=52, spacing=10, padding=[0, 8])
        with pie.canvas.before:
            Color(*STAGE)
            _pie = Rectangle(pos=pie.pos, size=pie.size)
        pie.bind(pos=lambda _, v: setattr(_pie, 'pos', v),
                 size=lambda _, v: setattr(_pie, 'size', v))
        pie.add_widget(Widget())
        btn_guardar  = _pill('Guardar PQR', SUCCESS, w=130)
        btn_cancelar = _pill('Cancelar', LINE, fg=TINTA)
        pie.add_widget(btn_guardar)
        pie.add_widget(btn_cancelar)
        body.add_widget(pie)

        popup = Popup(
            title='', content=content, size_hint=(0.62, 0.88),
            background_color=CARD, separator_height=0,
        )

        # ── Lógica ──
        def buscar(_):
            res_box.clear_widgets()
            texto = inp_buscar.text.strip()
            if not texto:
                return
            conn = get_connection()
            if not conn:
                return
            cur = conn.cursor()
            try:
                like = f'%{texto}%'
                cur.execute("""
                    SELECT cuenta, nombre FROM suscriptores
                    WHERE nombre LIKE %s OR CAST(cuenta AS CHAR) LIKE %s
                    LIMIT 8
                """, (like, like))
                for cuenta, nombre in cur.fetchall():
                    fila = BoxLayout(size_hint_y=None, height=32, spacing=0)
                    with fila.canvas.before:
                        Color(*STAGE)
                        _fr = Rectangle(pos=fila.pos, size=fila.size)
                    fila.bind(pos=lambda _, v, r=_fr: setattr(r, 'pos', v),
                              size=lambda _, v, r=_fr: setattr(r, 'size', v))
                    b = Button(
                        text=f'#{cuenta}  —  {nombre}',
                        font_size=12, color=TINTA,
                        background_color=(0, 0, 0, 0),
                        background_normal='', background_down='',
                        halign='left',
                    )
                    def seleccionar(_, c=cuenta, n=nombre):
                        state['cuenta'] = c
                        state['nombre'] = n
                        lbl_sel.text = f'✓  #{c} — {n}'
                        lbl_sel.color = SUCCESS
                        lbl_sel.italic = False
                        lbl_sel.bold = True
                        res_box.clear_widgets()
                    b.bind(on_press=seleccionar)
                    fila.add_widget(b)
                    res_box.add_widget(fila)
            finally:
                cur.close()
                conn.close()

        btn_buscar.bind(on_press=buscar)
        inp_buscar.bind(on_text_validate=buscar)

        def guardar(_):
            if not inp_asunto.text.strip():
                lbl_err.text = 'El asunto es obligatorio'
                return
            conn = get_connection()
            if not conn:
                lbl_err.text = 'Error de conexión'
                return
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO pqr
                    (cuenta_contrato, nombre_suscriptor, tipo, asunto, descripcion, estado)
                    VALUES (%s, %s, %s, %s, %s, 'Abierto')
                """, (
                    state['cuenta'],
                    state['nombre'] or 'Sin suscriptor',
                    sp_tipo.text,
                    inp_asunto.text.strip(),
                    inp_desc.text.strip() or None,
                ))
                conn.commit()
                popup.dismiss()
                self.cargar_lista()
                self.mensaje = 'PQR creada correctamente'
            except Exception as e:
                lbl_err.text = f'Error: {e}'
            finally:
                cur.close()
                conn.close()

        btn_guardar.bind(on_press=guardar)
        btn_cancelar.bind(on_press=popup.dismiss)
        popup.open()

    # ------------------------------------------------------------------
    #  Popup: Ver / Actualizar PQR
    # ------------------------------------------------------------------
    def _ver_pqr(self, pqr_id):
        overlay.show('Cargando PQR…')

        def _tarea():
            pqr, error = None, None
            conn = get_connection()
            if not conn:
                Clock.schedule_once(
                    lambda *_: (overlay.hide(),
                                setattr(self, 'mensaje', 'Error de conexión')), 0)
                return
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT id, cuenta_contrato, nombre_suscriptor, tipo, asunto,
                           descripcion, estado, observaciones,
                           fecha_creacion, fecha_resolucion,
                           COALESCE(email,''), COALESCE(telefono,''),
                           COALESCE(origen,'sistema')
                    FROM pqr WHERE id=%s
                """, (pqr_id,))
                pqr = cursor.fetchone()
            except Exception as e:
                error = str(e)
            finally:
                cursor.close()
                conn.close()
            Clock.schedule_once(lambda *_: _abrir(pqr, error), 0)

        def _abrir(pqr, error):
            overlay.hide()
            if error or not pqr:
                self.mensaje = f'Error: {error or "PQR no encontrada"}'
                return

            pid, cuenta, nombre, tipo, asunto, desc, estado, obs, fecha_c, fecha_r, email, telefono, origen = pqr

            col_e = COLOR_ESTADO.get(estado, MUTED)
            col_t = COLOR_TIPO.get(tipo, MUTED)

            def _pill(text, bg, fg=(1, 1, 1, 1), w=120):
                return PillButton(text=text, bg_color=bg, fg_color=fg,
                                  size_hint_x=None, width=w, font_size=12,
                                  pill_radius=20)

            # ── Root ──
            content = BoxLayout(orientation='vertical', spacing=0)
            with content.canvas.before:
                Color(*CARD)
                _bg = Rectangle(pos=content.pos, size=content.size)
            content.bind(pos=lambda _, v: setattr(_bg, 'pos', v),
                         size=lambda _, v: setattr(_bg, 'size', v))

            # ── Franja TINTA ──
            top = BoxLayout(orientation='vertical', size_hint_y=None, height=76,
                            padding=[18, 8])
            with top.canvas.before:
                Color(*TINTA)
                _top = Rectangle(pos=top.pos, size=top.size)
            top.bind(pos=lambda _, v: setattr(_top, 'pos', v),
                     size=lambda _, v: setattr(_top, 'size', v))

            # Fila título + chip de estado
            title_row = BoxLayout(size_hint_y=None, height=36)
            title_row.add_widget(Label(
                text=f'PQR #{pid}', bold=True, font_size=17,
                color=(1, 1, 1, 1), halign='left', valign='middle',
                size_hint_x=0.45,
            ))
            chip_wrap = BoxLayout(size_hint_x=0.55, spacing=6, padding=[0, 4, 0, 4])
            for chip_txt, chip_col in [(tipo, col_t), (estado, col_e)]:
                chip = BoxLayout(size_hint_x=None, width=110)
                with chip.canvas.before:
                    Color(*chip_col)
                    _ch = RoundedRectangle(pos=chip.pos, size=chip.size, radius=[13])
                chip.bind(pos=lambda _, v, r=_ch: setattr(r, 'pos', v),
                          size=lambda _, v, r=_ch: setattr(r, 'size', v))
                chip.add_widget(Label(text=chip_txt, color=(1, 1, 1, 1),
                                      bold=True, font_size=11))
                chip_wrap.add_widget(chip)
            title_row.add_widget(chip_wrap)
            top.add_widget(title_row)

            sus_txt = f'#{cuenta} — {nombre}' if cuenta else nombre or '—'
            sus_col = LINE
            if origen == 'web':
                sus_col = SUCCESS if cuenta else WARNING

            sub_row = BoxLayout(size_hint_y=None, height=26)
            sub_row.add_widget(Label(
                text=sus_txt, font_size=11, color=sus_col,
                halign='left', valign='middle', size_hint_x=0.44,
            ))
            if origen == 'web':
                badge = BoxLayout(size_hint_x=None, width=52, padding=[4, 4])
                with badge.canvas.before:
                    Color(0.200, 0.470, 0.820, 1)
                    _bd = RoundedRectangle(pos=badge.pos, size=badge.size, radius=[10])
                badge.bind(pos=lambda _, v, r=_bd: setattr(r, 'pos', v),
                           size=lambda _, v, r=_bd: setattr(r, 'size', v))
                badge.add_widget(Label(text='WEB', color=(1,1,1,1), bold=True, font_size=10))
                sub_row.add_widget(badge)

                link_col  = SUCCESS if cuenta else WARNING
                link_text = 'Vinculado' if cuenta else 'Sin match'
                link_badge = BoxLayout(size_hint_x=None, width=74, padding=[4, 4])
                with link_badge.canvas.before:
                    Color(*link_col)
                    _lb = RoundedRectangle(pos=link_badge.pos, size=link_badge.size, radius=[10])
                link_badge.bind(pos=lambda _, v, r=_lb: setattr(r, 'pos', v),
                                size=lambda _, v, r=_lb: setattr(r, 'size', v))
                link_badge.add_widget(Label(text=link_text, color=(1,1,1,1), bold=True, font_size=10))
                sub_row.add_widget(link_badge)
            top.add_widget(sub_row)
            content.add_widget(top)

            # ── Metadatos ──
            meta = BoxLayout(size_hint_y=None, height=38, spacing=1)
            with meta.canvas.before:
                Color(*STAGE)
                _m = Rectangle(pos=meta.pos, size=meta.size)
            meta.bind(pos=lambda _, v: setattr(_m, 'pos', v),
                      size=lambda _, v: setattr(_m, 'size', v))
            fecha_c_txt = str(fecha_c)[:16] if fecha_c else '—'
            fecha_r_txt = str(fecha_r)[:16] if fecha_r else 'Pendiente'
            meta_items = [(fecha_c_txt, 'Creada'), (fecha_r_txt, 'Resuelta')]
            if email:
                meta_items.append((email, 'Email'))
            if telefono:
                meta_items.append((telefono, 'Teléfono'))
            for txt, lbl_t in meta_items:
                col = BoxLayout(orientation='vertical', padding=[14, 4])
                col.add_widget(Label(text=txt, font_size=11, bold=True, color=TINTA,
                                     halign='left', valign='middle'))
                col.add_widget(Label(text=lbl_t, font_size=9, color=MUTED,
                                     halign='left', valign='middle'))
                meta.add_widget(col)
            content.add_widget(meta)

            # ── Cuerpo: asunto + descripción ──
            body = BoxLayout(orientation='vertical', padding=[18, 10], spacing=8)
            content.add_widget(body)

            for etq, val in [('Asunto', asunto), ('Descripción', desc)]:
                if val:
                    body.add_widget(Label(
                        text=etq, bold=True, font_size=11, color=VERMILLON,
                        size_hint_y=None, height=18,
                        halign='left', valign='middle',
                    ))
                    lbl_val = Label(
                        text=val, font_size=13, color=TINTA,
                        size_hint_y=None, halign='left', valign='top',
                    )
                    lbl_val.bind(
                        width=lambda inst, w: setattr(inst, 'text_size', (w - 4, None)),
                        texture_size=lambda inst, ts: setattr(inst, 'height', ts[1] + 6),
                    )
                    body.add_widget(lbl_val)

            # ── Actualizar ──
            body.add_widget(Label(
                text='Actualizar estado', bold=True, font_size=11, color=VERMILLON,
                size_hint_y=None, height=22,
                halign='left', valign='middle',
            ))
            upd = BoxLayout(size_hint_y=None, height=42, spacing=10)
            sp_wrap = BoxLayout(size_hint_x=0.38)
            with sp_wrap.canvas.before:
                Color(*STAGE)
                _sw = Rectangle(pos=sp_wrap.pos, size=sp_wrap.size)
            sp_wrap.bind(pos=lambda _, v, r=_sw: setattr(r, 'pos', v),
                         size=lambda _, v, r=_sw: setattr(r, 'size', v))
            sp_estado = Spinner(text=estado, values=ESTADOS,
                                background_color=(0, 0, 0, 0), background_normal='',
                                color=TINTA, font_size=13)
            sp_wrap.add_widget(sp_estado)
            upd.add_widget(sp_wrap)

            obs_wrap = BoxLayout(size_hint_x=0.62)
            with obs_wrap.canvas.before:
                Color(*STAGE)
                _ow = Rectangle(pos=obs_wrap.pos, size=obs_wrap.size)
            obs_wrap.bind(pos=lambda _, v, r=_ow: setattr(r, 'pos', v),
                          size=lambda _, v, r=_ow: setattr(r, 'size', v))
            inp_obs = TextInput(
                hint_text='Observaciones...', multiline=False,
                text=obs or '',
                background_color=(0, 0, 0, 0), background_normal='', background_active='',
                foreground_color=TINTA, cursor_color=VERMILLON,
                hint_text_color=MUTED, padding=[8, 10], font_size=13,
            )
            obs_wrap.add_widget(inp_obs)
            upd.add_widget(obs_wrap)
            body.add_widget(upd)

            lbl_err = Label(text='', color=DANGER, font_size=11,
                            size_hint_y=None, height=22)
            body.add_widget(lbl_err)

            # ── Footer ──
            footer = BoxLayout(size_hint_y=None, height=52, spacing=10, padding=[14, 8])
            with footer.canvas.before:
                Color(*STAGE)
                _ft = Rectangle(pos=footer.pos, size=footer.size)
            footer.bind(pos=lambda _, v: setattr(_ft, 'pos', v),
                        size=lambda _, v: setattr(_ft, 'size', v))
            footer.add_widget(Widget())
            btn_email  = _pill('Enviar respuesta', (0.200, 0.470, 0.820, 1), w=150)
            btn_act    = _pill('Guardar cambios', SUCCESS, w=140)
            btn_cerrar = _pill('Cerrar', LINE, fg=TINTA)
            if email:
                footer.add_widget(btn_email)
            footer.add_widget(btn_act)
            footer.add_widget(btn_cerrar)
            content.add_widget(footer)

            popup = Popup(title='', content=content, size_hint=(0.62, 0.86),
                          background_color=CARD, separator_height=0)

            def actualizar(_):
                conn2 = get_connection()
                if not conn2:
                    lbl_err.text = 'Error de conexión'
                    return
                cur2 = conn2.cursor()
                try:
                    nuevo_estado = sp_estado.text
                    nueva_fecha_r = (datetime.now()
                                     if nuevo_estado == 'Resuelto' and estado != 'Resuelto'
                                     else fecha_r)
                    cur2.execute("""
                        UPDATE pqr
                        SET estado=%s, observaciones=%s, fecha_resolucion=%s
                        WHERE id=%s
                    """, (nuevo_estado, inp_obs.text.strip() or None, nueva_fecha_r, pid))
                    conn2.commit()
                    popup.dismiss()
                    self.cargar_lista()
                    self.mensaje = f'PQR #{pid} actualizada'
                except Exception as e:
                    lbl_err.text = f'Error: {e}'
                finally:
                    cur2.close()
                    conn2.close()

            def enviar_email(_):
                self._popup_enviar_email(pid, nombre, email, asunto, obs or '')

            btn_act.bind(on_press=actualizar)
            btn_cerrar.bind(on_press=popup.dismiss)
            btn_email.bind(on_press=enviar_email)
            popup.open()

        threading.Thread(target=_tarea, daemon=True).start()

    # ------------------------------------------------------------------
    #  Popup: Enviar respuesta por email
    # ------------------------------------------------------------------
    def _popup_enviar_email(self, pqr_id, nombre, email, asunto, obs_actual):
        def _pill(text, bg, fg=(1, 1, 1, 1), w=120):
            return PillButton(text=text, bg_color=bg, fg_color=fg,
                              size_hint_x=None, width=w, font_size=12,
                              pill_radius=20)

        content = BoxLayout(orientation='vertical', spacing=0)
        with content.canvas.before:
            Color(*CARD)
            _bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda _, v: setattr(_bg, 'pos', v),
                     size=lambda _, v: setattr(_bg, 'size', v))

        # Header
        top = BoxLayout(size_hint_y=None, height=52, padding=[18, 0])
        with top.canvas.before:
            Color(*TINTA)
            _top = Rectangle(pos=top.pos, size=top.size)
        top.bind(pos=lambda _, v: setattr(_top, 'pos', v),
                 size=lambda _, v: setattr(_top, 'size', v))
        top.add_widget(Label(
            text=f'Responder PQR #{pqr_id}', bold=True, font_size=16,
            color=(1, 1, 1, 1), halign='left', valign='middle',
        ))
        content.add_widget(top)

        # Body
        body = BoxLayout(orientation='vertical', spacing=8, padding=[18, 14, 18, 0])
        content.add_widget(body)

        # Destinatario (solo lectura)
        dest_box = BoxLayout(size_hint_y=None, height=36, spacing=8)
        dest_box.add_widget(Label(text='Para:', color=VERMILLON, bold=True,
                                  font_size=12, size_hint_x=0.12,
                                  halign='right', valign='middle'))
        dest_box.add_widget(Label(
            text=f'{nombre} <{email}>', color=TEXT_SEC, font_size=12,
            halign='left', valign='middle',
        ))
        body.add_widget(dest_box)

        # Textarea mensaje
        body.add_widget(Label(text='Mensaje:', color=VERMILLON, bold=True,
                              font_size=12, size_hint_y=None, height=22,
                              halign='left', valign='middle'))
        inp_msg = TextInput(
            hint_text='Escribe la respuesta aquí...',
            text=obs_actual,
            multiline=True,
            background_color=STAGE, foreground_color=TINTA,
            cursor_color=VERMILLON, hint_text_color=MUTED,
            padding=[10, 10], font_size=13,
        )
        body.add_widget(inp_msg)

        lbl_estado = Label(text='', color=SUCCESS, font_size=12,
                           size_hint_y=None, height=26)
        body.add_widget(lbl_estado)

        # Footer
        footer = BoxLayout(size_hint_y=None, height=52, spacing=10, padding=[0, 8])
        with footer.canvas.before:
            Color(*STAGE)
            _ft = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda _, v: setattr(_ft, 'pos', v),
                    size=lambda _, v: setattr(_ft, 'size', v))
        footer.add_widget(Widget())
        btn_enviar  = _pill('Enviar email', (0.200, 0.470, 0.820, 1), w=130)
        btn_cancelar = _pill('Cancelar', LINE, fg=TINTA)
        footer.add_widget(btn_enviar)
        footer.add_widget(btn_cancelar)
        body.add_widget(footer)

        popup = Popup(title='', content=content, size_hint=(0.52, 0.72),
                      background_color=CARD, separator_height=0)

        def enviar(_):
            msg = inp_msg.text.strip()
            if not msg:
                lbl_estado.text = 'Escribe un mensaje antes de enviar.'
                lbl_estado.color = DANGER
                return
            btn_enviar.disabled = True
            lbl_estado.text = 'Enviando...'
            lbl_estado.color = MUTED

            def _tarea_envio():
                ok, err = enviar_respuesta_pqr(email, nombre, pqr_id, asunto, msg)
                def _resultado(*_):
                    if ok:
                        lbl_estado.text = 'Email enviado correctamente.'
                        lbl_estado.color = SUCCESS
                        btn_cancelar.text = 'Cerrar'
                        btn_enviar.disabled = True
                    else:
                        lbl_estado.text = err
                        lbl_estado.color = DANGER
                        btn_enviar.disabled = False
                Clock.schedule_once(_resultado, 0)

            threading.Thread(target=_tarea_envio, daemon=True).start()

        btn_enviar.bind(on_press=enviar)
        btn_cancelar.bind(on_press=popup.dismiss)
        popup.open()

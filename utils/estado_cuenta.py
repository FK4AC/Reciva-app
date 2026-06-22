import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether,
)

# ── Registro de fuentes de marca ──────────────────────────────────────────────
_BASE = os.path.dirname(__file__)

def _reg():
    _map = {
        'Sora':         '../fonts/Sora-SemiBold2.ttf',
        'Sora-Bold':    '../fonts/Sora-Bold2.ttf',
        'Jakarta':      '../fonts/Jakarta-Regular.ttf',
        'Jakarta-Med':  '../fonts/Jakarta-Medium.ttf',
        'Jakarta-Bold': '../fonts/Jakarta-SemiBold.ttf',
    }
    for name, rel in _map.items():
        path = os.path.join(_BASE, rel)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    try:
        registerFontFamily('Sora',    normal='Sora',    bold='Sora-Bold',
                           italic='Sora',    boldItalic='Sora-Bold')
        registerFontFamily('Jakarta', normal='Jakarta', bold='Jakarta-Bold',
                           italic='Jakarta-Med', boldItalic='Jakarta-Bold')
    except Exception:
        pass

_reg()

# ── Paleta de marca INGESAM (rojo) ───────────────────────────────────────────
VERDE        = colors.HexColor('#C9040B')   # rojo INGESAM principal
VERDE_OSC    = colors.HexColor('#8F0307')   # rojo oscuro (footer, banda)
VERDE_CLARO  = colors.HexColor('#FDECED')   # rojo muy claro (fondos alternos)
VERDE_TXT    = colors.HexColor('#F7BBBE')   # texto claro sobre rojo
TINTA        = colors.HexColor('#1B1512')
VERMILLON    = colors.HexColor('#C9040B')   # rojo (mora/deuda — mismo que brand)
LINE         = colors.HexColor('#F0C8CA')   # bordes cálidos
MUTED        = colors.HexColor('#7A5252')   # muted cálido
SUCCESS      = colors.HexColor('#1F8838')
WARNING      = colors.HexColor('#CC8008')
WHITE        = colors.white
STAGE        = colors.HexColor('#FEF6F4')   # fondo alternado filas

MESES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


# ── Estilos tipográficos ──────────────────────────────────────────────────────
def _styles():
    J  = 'Jakarta'
    JB = 'Jakarta-Bold'
    S  = 'Sora'
    SB = 'Sora-Bold'
    return {
        # Encabezado del documento
        'hdr_empresa': ParagraphStyle('hdr_empresa', fontName=SB, fontSize=13,
                                      textColor=WHITE, spaceAfter=3),
        'hdr_sub':     ParagraphStyle('hdr_sub',     fontName=J,  fontSize=8,
                                      textColor=VERDE_TXT, spaceAfter=0),
        'hdr_doc':     ParagraphStyle('hdr_doc',     fontName=SB, fontSize=11,
                                      textColor=WHITE, alignment=2, spaceAfter=3),
        'hdr_fecha':   ParagraphStyle('hdr_fecha',   fontName=J,  fontSize=8,
                                      textColor=VERDE_TXT, alignment=2),
        # Cabeceras de sección
        'sec':         ParagraphStyle('sec', fontName=SB, fontSize=10,
                                      textColor=WHITE, spaceAfter=0, spaceBefore=0,
                                      leftIndent=8),
        # Cuerpo
        'body':        ParagraphStyle('body', fontName=J,  fontSize=8.5,
                                      textColor=TINTA, leading=11),
        'body_b':      ParagraphStyle('body_b', fontName=JB, fontSize=8.5,
                                      textColor=TINTA, leading=11),
        'muted':       ParagraphStyle('muted', fontName=J,  fontSize=7.5,
                                      textColor=MUTED),
        # Tarjetas financieras
        'card_num':    ParagraphStyle('card_num', fontName=SB, fontSize=16,
                                      textColor=TINTA, spaceAfter=0, alignment=1),
        'card_lbl':    ParagraphStyle('card_lbl', fontName=J,  fontSize=7.5,
                                      textColor=MUTED, spaceAfter=0, alignment=1),
        # Pie
        'pie':         ParagraphStyle('pie', fontName=J, fontSize=7.5,
                                      textColor=WHITE, alignment=1),
    }


def _sec_header(text, st):
    """Cabecera de sección con fondo verde INGESAM."""
    p = Paragraph(text, st['sec'])
    t = Table([[p]], colWidths=[17.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), VERDE),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return t


def _carpeta_salida():
    carpeta = os.path.join(_BASE, '..', 'estados_cuenta')
    os.makedirs(carpeta, exist_ok=True)
    return os.path.abspath(carpeta)


# ── Función principal ─────────────────────────────────────────────────────────
def generar_estado_cuenta(info, facturas, recaudos, pqr_list):
    """
    info      — (cuenta, nombre, direccion, barrio, estrato,
                  estado_suministro, municipio, susccodi)
    facturas  — dict {(año, mes): valor_facturado}
    recaudos  — dict {(año, mes): valor_pagado}
    pqr_list  — lista de tuplas (id, tipo, asunto, estado, fecha_creacion)
    Retorna la ruta del PDF generado.
    """
    cuenta, nombre, direccion, barrio, estrato, estado_sum, municipio, susccodi = info

    total_fac = sum(facturas.values())
    total_rec = sum(recaudos.values())
    deuda     = max(0.0, total_fac - total_rec)

    meses_sin = sum(
        1 for (a, m), v in facturas.items()
        if recaudos.get((a, m), 0) < v * 0.95
    )
    consecutivos = 0
    for (a, m), v in sorted(facturas.items(), reverse=True):
        if recaudos.get((a, m), 0) < v * 0.95:
            consecutivos += 1
        else:
            break

    if meses_sin == 0:
        estado_pago  = 'AL DÍA'
        color_estado = SUCCESS
    elif meses_sin <= 2:
        estado_pago  = f'{meses_sin} mes(es) de mora'
        color_estado = WARNING
    else:
        estado_pago  = f'{meses_sin} meses de mora'
        color_estado = VERMILLON

    nombre_archivo = f'estado_cuenta_{cuenta}_{date.today().isoformat()}.pdf'
    ruta = os.path.join(_carpeta_salida(), nombre_archivo)

    doc = SimpleDocTemplate(
        ruta, pagesize=letter,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    st = _styles()
    story = []

    # ── ENCABEZADO INGESAM ────────────────────────────────────────────────────
    logo_path = os.path.join(_BASE, '..', 'logo_png', 'logo-512-space-no-fondo-1.png')
    logo_img = (RLImage(logo_path, width=1.8*cm, height=1.8*cm, kind='proportional')
                if os.path.exists(logo_path) else Paragraph('', st['body']))

    cel_logo  = logo_img
    cel_emp   = [Paragraph('INGESAM ASEO S.A.S E.S.P.', st['hdr_empresa']),
                 Paragraph('Servicio Público de Aseo — Hatonuevo, La Guajira',
                            st['hdr_sub'])]
    cel_doc   = [Paragraph('ESTADO DE CUENTA', st['hdr_doc']),
                 Paragraph(f'Generado: {date.today().strftime("%d/%m/%Y")}',
                            st['hdr_fecha'])]

    t_hdr = Table([[cel_logo, cel_emp, cel_doc]],
                  colWidths=[2.2*cm, 10*cm, 5.3*cm])
    t_hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), VERDE),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING',   (0, 0), (0,  -1), 14),
        ('LEFTPADDING',   (1, 0), (1,  -1), 12),
        ('RIGHTPADDING',  (2, 0), (2,  -1), 14),
        ('LEFTPADDING',   (2, 0), (2,  -1), 8),
    ]))
    story.append(t_hdr)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width='100%', thickness=2, color=VERDE_OSC, spaceAfter=10))

    # ── DATOS DEL SUSCRIPTOR ──────────────────────────────────────────────────
    story.append(_sec_header('Datos del Suscriptor', st))
    story.append(Spacer(1, 8))

    datos = [
        [Paragraph('Cuenta contrato', st['body_b']), Paragraph(str(cuenta), st['body']),
         Paragraph('SUSCCODI', st['body_b']),         Paragraph(str(susccodi), st['body'])],
        [Paragraph('Nombre', st['body_b']),           Paragraph(nombre or '—', st['body']),
         Paragraph('Municipio', st['body_b']),         Paragraph(municipio or '—', st['body'])],
        [Paragraph('Dirección', st['body_b']),         Paragraph(direccion or '—', st['body']),
         Paragraph('Barrio', st['body_b']),             Paragraph(barrio or '—', st['body'])],
        [Paragraph('Estrato', st['body_b']),            Paragraph(str(estrato or '—'), st['body']),
         Paragraph('Estado suministro', st['body_b']),  Paragraph(estado_sum or '—', st['body'])],
    ]
    t_sus = Table(datos, colWidths=[3.5*cm, 7*cm, 3.5*cm, 3.5*cm])
    t_sus.setStyle(TableStyle([
        ('ROWBACKGROUNDS',  (0, 0), (-1, -1), [WHITE, STAGE]),
        ('TOPPADDING',      (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',   (0, 0), (-1, -1), 5),
        ('LEFTPADDING',     (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',    (0, 0), (-1, -1), 6),
        ('LINEBELOW',       (0, -1), (-1, -1), 0.5, LINE),
        ('LINEBEFORE',      (0,  0), (0,  -1), 0.5, LINE),
        ('LINEAFTER',       (-1, 0), (-1, -1), 0.5, LINE),
        ('LINEABOVE',       (0,  0), (-1,  0), 0.5, LINE),
    ]))
    story.append(t_sus)
    story.append(Spacer(1, 12))

    # ── RESUMEN FINANCIERO ────────────────────────────────────────────────────
    story.append(_sec_header('Resumen Financiero', st))
    story.append(Spacer(1, 4))

    color_deuda = VERMILLON if deuda > 0 else SUCCESS
    sn_fac = ParagraphStyle('sn_fac', fontName='Sora-Bold', fontSize=17,
                             textColor=TINTA,       alignment=1, spaceAfter=0)
    sn_rec = ParagraphStyle('sn_rec', fontName='Sora-Bold', fontSize=17,
                             textColor=SUCCESS,     alignment=1, spaceAfter=0)
    sn_deu = ParagraphStyle('sn_deu', fontName='Sora-Bold', fontSize=17,
                             textColor=color_deuda, alignment=1, spaceAfter=0)
    sn_est = ParagraphStyle('sn_est', fontName='Sora-Bold', fontSize=15,
                             textColor=color_estado, alignment=1, spaceAfter=0)
    lbl_c  = ParagraphStyle('lbl_c',  fontName='Jakarta',   fontSize=7.5,
                             textColor=MUTED,       alignment=1, spaceAfter=0)

    CW = [4.375*cm] * 4
    row_nums = [
        Paragraph(f'${total_fac:,.0f}', sn_fac),
        Paragraph(f'${total_rec:,.0f}', sn_rec),
        Paragraph(f'${deuda:,.0f}',     sn_deu),
        Paragraph(estado_pago,           sn_est),
    ]
    row_lbl = [
        Paragraph('Total Facturado',              lbl_c),
        Paragraph('Total Pagado',                 lbl_c),
        Paragraph('Saldo Pendiente',              lbl_c),
        Paragraph(f'{consecutivos} mes(es) consec.', lbl_c),
    ]
    t_cards = Table([row_nums, row_lbl], colWidths=CW)
    t_cards.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), STAGE),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1,  0), 18),
        ('BOTTOMPADDING', (0, 0), (-1,  0), 18),
        ('TOPPADDING',    (0, 1), (-1,  1), 12),
        ('BOTTOMPADDING', (0, 1), (-1,  1), 18),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('INNERGRID',     (0, 0), (-1, -1), 0.5, LINE),
        ('BOX',           (0, 0), (-1, -1), 0.5, LINE),
        ('LINEABOVE',     (0, 0), (0,  -1), 3, TINTA),
        ('LINEABOVE',     (1, 0), (1,  -1), 3, SUCCESS),
        ('LINEABOVE',     (2, 0), (2,  -1), 3, color_deuda),
        ('LINEABOVE',     (3, 0), (3,  -1), 3, color_estado),
    ]))
    story.append(t_cards)
    story.append(Spacer(1, 12))

    # ── HISTORIAL DE PAGOS ────────────────────────────────────────────────────
    all_months = sorted(set(list(facturas.keys()) + list(recaudos.keys())))
    if all_months:
        story.append(_sec_header('Historial de Pagos por Período', st))
        story.append(Spacer(1, 8))

        enc = [[
            Paragraph('Año',       st['sec']),
            Paragraph('Mes',       st['sec']),
            Paragraph('Facturado', st['sec']),
            Paragraph('Pagado',    st['sec']),
            Paragraph('Estado',    st['sec']),
        ]]
        filas = []
        col_estados = []
        for (a, m) in all_months:
            fac_v = facturas.get((a, m), 0)
            rec_v = recaudos.get((a, m), 0)
            if fac_v > 0 and rec_v >= fac_v * 0.95:
                est, col_e = 'Pagado',      SUCCESS
            elif fac_v > 0:
                est, col_e = 'Pendiente',   VERMILLON
            else:
                est, col_e = 'Sin factura', MUTED
            col_estados.append(col_e)
            filas.append([
                Paragraph(str(a),               st['body']),
                Paragraph(MESES.get(m, str(m)), st['body']),
                Paragraph(f'${fac_v:,.0f}',     st['body']),
                Paragraph(f'${rec_v:,.0f}',     st['body']),
                Paragraph(est,                  st['body']),
            ])

        estilos = [
            ('BACKGROUND',    (0, 0), (-1,  0), VERDE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, STAGE]),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('ALIGN',         (2, 0), (3, -1), 'RIGHT'),
            ('ALIGN',         (4, 0), (4, -1), 'CENTER'),
            ('GRID',          (0, 0), (-1, -1), 0.3, LINE),
            ('FONTSIZE',      (0, 0), (-1, -1), 8.5),
        ]
        for i, col_e in enumerate(col_estados, start=1):
            estilos.append(('TEXTCOLOR', (4, i), (4, i), col_e))

        t_hist = Table(enc + filas,
                       colWidths=[2*cm, 3.5*cm, 4*cm, 4*cm, 4*cm],
                       repeatRows=1)
        t_hist.setStyle(TableStyle(estilos))
        story.append(t_hist)
        story.append(Spacer(1, 12))

    # ── PQR ───────────────────────────────────────────────────────────────────
    if pqr_list:
        story.append(_sec_header('PQR Asociadas', st))
        story.append(Spacer(1, 8))

        COLOR_ESTADO_PDF = {
            'Abierto':    VERMILLON,
            'En Proceso': WARNING,
            'Resuelto':   SUCCESS,
        }

        enc_pqr = [[
            Paragraph('#',       st['sec']),
            Paragraph('Tipo',    st['sec']),
            Paragraph('Asunto',  st['sec']),
            Paragraph('Estado',  st['sec']),
            Paragraph('Fecha',   st['sec']),
        ]]
        filas_pqr = []
        col_pqr   = []
        for p in pqr_list:
            c_e = COLOR_ESTADO_PDF.get(p[3], MUTED)
            col_pqr.append(c_e)
            filas_pqr.append([
                Paragraph(str(p[0]),              st['body']),
                Paragraph(p[1] or '—',            st['body']),
                Paragraph((p[2] or '—')[:45],     st['body']),
                Paragraph(p[3] or '—',            st['body']),
                Paragraph(str(p[4])[:10] if p[4] else '—', st['body']),
            ])

        estilos_pqr = [
            ('BACKGROUND',    (0, 0), (-1,  0), VERDE),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, STAGE]),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('GRID',          (0, 0), (-1, -1), 0.3, LINE),
        ]
        for i, c_e in enumerate(col_pqr, start=1):
            estilos_pqr.append(('TEXTCOLOR', (3, i), (3, i), c_e))

        t_pqr = Table(enc_pqr + filas_pqr,
                      colWidths=[1.2*cm, 2.8*cm, 8*cm, 2.8*cm, 2.7*cm],
                      repeatRows=1)
        t_pqr.setStyle(TableStyle(estilos_pqr))
        story.append(KeepTogether(t_pqr))
        story.append(Spacer(1, 10))

    # ── PIE DE PÁGINA ─────────────────────────────────────────────────────────
    pie_data = [[Paragraph(
        'INGESAM ASEO S.A.S E.S.P. — Hatonuevo, La Guajira  ·  '
        'Tel: +57 300 285 3547  ·  pqringesamaseo@gmail.com  ·  '
        'Documento generado por Sistema RECIVA',
        st['pie']
    )]]
    t_pie = Table(pie_data, colWidths=[17.5*cm])
    t_pie.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), VERDE_OSC),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_pie)

    doc.build(story)
    return ruta


def _hex_sin_hash(color_obj):
    return color_obj.hexval().lstrip('#')

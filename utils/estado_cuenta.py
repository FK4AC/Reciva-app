import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

MESES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

AZUL   = colors.HexColor('#1565C0')
AZUL_L = colors.HexColor('#E3F2FD')
ROJO   = colors.HexColor('#C62828')
VERDE  = colors.HexColor('#2E7D32')
GRIS   = colors.HexColor('#455A64')
GRIS_L = colors.HexColor('#ECEFF1')


def _carpeta_salida():
    carpeta = os.path.join(os.path.dirname(__file__), '..', 'estados_cuenta')
    os.makedirs(carpeta, exist_ok=True)
    return os.path.abspath(carpeta)


def generar_estado_cuenta(info, facturas, recaudos, pqr_list):
    """
    info      — tupla (cuenta, nombre, direccion, barrio, estrato,
                       estado_suministro, municipio, susccodi)
    facturas  — dict {(año, mes): valor_facturado}
    recaudos  — dict {(año, mes): valor_pagado}
    pqr_list  — lista de tuplas (id, tipo, asunto, estado, fecha_creacion)
    Retorna la ruta del PDF generado.
    """
    cuenta, nombre, direccion, barrio, estrato, estado_sum, municipio, susccodi = info

    total_fac = sum(facturas.values())
    total_rec = sum(recaudos.values())
    deuda     = max(0, total_fac - total_rec)

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
        estado_pago = 'AL DÍA'
        color_estado = VERDE
    elif meses_sin <= 2:
        estado_pago = f'{meses_sin} mes(es) de mora'
        color_estado = colors.HexColor('#E65100')
    else:
        estado_pago = f'{meses_sin} meses de mora'
        color_estado = ROJO

    nombre_archivo = f'estado_cuenta_{cuenta}_{date.today().isoformat()}.pdf'
    ruta = os.path.join(_carpeta_salida(), nombre_archivo)

    doc = SimpleDocTemplate(
        ruta,
        pagesize=letter,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('titulo', fontSize=18, textColor=AZUL,
                                  spaceAfter=2, fontName='Helvetica-Bold')
    sub_style    = ParagraphStyle('sub', fontSize=10, textColor=GRIS,
                                  spaceAfter=4, fontName='Helvetica')
    seccion_style = ParagraphStyle('sec', fontSize=11, textColor=AZUL,
                                   spaceBefore=10, spaceAfter=4,
                                   fontName='Helvetica-Bold')
    normal = styles['Normal']

    story = []

    # ------------------------------------------------------------------ Encabezado
    story.append(Paragraph('INGESAM', titulo_style))
    story.append(Paragraph(
        'Servicio de Aseo — Hatonuevo, La Guajira', sub_style
    ))
    story.append(Paragraph(
        f'Estado de Cuenta &nbsp;|&nbsp; Generado: {date.today().strftime("%d/%m/%Y")}',
        sub_style
    ))
    story.append(HRFlowable(width='100%', thickness=2, color=AZUL, spaceAfter=8))

    # ------------------------------------------------------------------ Datos del suscriptor
    story.append(Paragraph('Datos del Suscriptor', seccion_style))
    datos_sus = [
        ['Cuenta contrato:', str(cuenta),   'SUSCCODI:',    str(susccodi)],
        ['Nombre:',          nombre or '-', 'Municipio:',   municipio or '-'],
        ['Dirección:',       direccion or '-', 'Barrio:',   barrio or '-'],
        ['Estrato:',         str(estrato or '-'), 'Estado suministro:', estado_sum or '-'],
    ]
    t_sus = Table(datos_sus, colWidths=[3.5*cm, 7*cm, 3.5*cm, 5.5*cm])
    t_sus.setStyle(TableStyle([
        ('FONTNAME',    (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME',    (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',    (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 9),
        ('TEXTCOLOR',   (0, 0), (0, -1), AZUL),
        ('TEXTCOLOR',   (2, 0), (2, -1), AZUL),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [GRIS_L, colors.white]),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sus)
    story.append(Spacer(1, 8))

    # ------------------------------------------------------------------ Resumen financiero
    story.append(Paragraph('Resumen Financiero', seccion_style))
    t_res = Table([
        [
            Paragraph(f'<font color="#1565C0"><b>Total Facturado</b></font><br/>${total_fac:,.0f}', normal),
            Paragraph(f'<font color="#2E7D32"><b>Total Pagado</b></font><br/>${total_rec:,.0f}', normal),
            Paragraph(f'<font color="#C62828"><b>Saldo Pendiente</b></font><br/>${deuda:,.0f}', normal),
            Paragraph(
                f'<font color="#{_hex_sin_hash(color_estado)}"><b>Estado</b></font><br/>'
                f'{estado_pago}<br/>'
                f'<font size="8">{consecutivos} consecutivos</font>',
                normal
            ),
        ]
    ], colWidths=[4.8*cm, 4.8*cm, 4.8*cm, 4.8*cm])
    t_res.setStyle(TableStyle([
        ('BOX',         (0, 0), (-1, -1), 1, AZUL),
        ('INNERGRID',   (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',  (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND',  (0, 0), (-1, -1), AZUL_L),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 10))

    # ------------------------------------------------------------------ Historial de pagos
    story.append(Paragraph('Historial de Pagos por Período', seccion_style))

    encabezado = [['Año', 'Mes', 'Facturado', 'Pagado', 'Estado']]
    filas_tabla = []
    all_months = sorted(set(list(facturas.keys()) + list(recaudos.keys())))

    for (a, m) in all_months:
        fac_v = facturas.get((a, m), 0)
        rec_v = recaudos.get((a, m), 0)

        if fac_v > 0 and rec_v >= fac_v * 0.95:
            est = 'Pagado'
        elif fac_v > 0:
            est = 'Pendiente'
        else:
            est = 'Sin factura'

        filas_tabla.append([
            str(a),
            MESES.get(m, str(m)),
            f'${fac_v:,.0f}',
            f'${rec_v:,.0f}',
            est,
        ])

    t_hist = Table(
        encabezado + filas_tabla,
        colWidths=[2*cm, 3.5*cm, 4*cm, 4*cm, 3*cm],
        repeatRows=1
    )
    estilos_hist = [
        ('BACKGROUND',   (0, 0), (-1, 0), AZUL),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 8.5),
        ('ALIGN',        (2, 0), (3, -1), 'RIGHT'),
        ('ALIGN',        (4, 0), (4, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_L]),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('GRID',         (0, 0), (-1, -1), 0.4, colors.lightgrey),
    ]
    for i, (_, m_idx) in enumerate(all_months, start=1):
        fac_v = facturas.get((all_months[i-1][0], all_months[i-1][1]), 0)
        rec_v = recaudos.get((all_months[i-1][0], all_months[i-1][1]), 0)
        if fac_v > 0 and rec_v < fac_v * 0.95:
            estilos_hist.append(('TEXTCOLOR', (4, i), (4, i), ROJO))
        elif fac_v > 0:
            estilos_hist.append(('TEXTCOLOR', (4, i), (4, i), VERDE))

    t_hist.setStyle(TableStyle(estilos_hist))
    story.append(t_hist)
    story.append(Spacer(1, 10))

    # ------------------------------------------------------------------ PQR
    if pqr_list:
        story.append(Paragraph('PQR Asociadas', seccion_style))
        enc_pqr = [['#', 'Tipo', 'Asunto', 'Estado', 'Fecha']]
        filas_pqr = [
            [str(p[0]), p[1] or '-', (p[2] or '-')[:40], p[3] or '-',
             str(p[4])[:10] if p[4] else '-']
            for p in pqr_list
        ]
        t_pqr = Table(
            enc_pqr + filas_pqr,
            colWidths=[1.2*cm, 2.8*cm, 8*cm, 2.8*cm, 2.8*cm],
            repeatRows=1
        )
        t_pqr.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), GRIS),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, -1), 8.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_L]),
            ('GRID',         (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ('TOPPADDING',   (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ]))
        story.append(t_pqr)
        story.append(Spacer(1, 8))

    # ------------------------------------------------------------------ Pie de página
    story.append(HRFlowable(width='100%', thickness=1, color=GRIS, spaceBefore=10))
    story.append(Paragraph(
        'INGESAM — Hatonuevo, La Guajira &nbsp;|&nbsp; '
        'Sistema RECIVA &nbsp;|&nbsp; Documento generado automáticamente',
        ParagraphStyle('pie', fontSize=7.5, textColor=GRIS, alignment=1)
    ))

    doc.build(story)
    return ruta


def _hex_sin_hash(color_obj):
    """Extrae el hex sin # para usarlo en markup de ReportLab."""
    h = color_obj.hexval()          # '#rrggbb'
    return h.lstrip('#')

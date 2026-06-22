"""
Helpers de BD y generación de archivos para el módulo Volcado.
El volcado se genera directamente desde la BD (suscriptores + facturas + tarifas_volcado).
"""
import os
import unicodedata
import openpyxl

# ── Mapa subcategoría catastro → (uso_volcado, lote) ─────────────────────────

MAPA_SUBCATEGORIA = {
    '1 - ESTRATO 1': ('Residencial 1 Ocupado',  'principal'),
    '2 - ESTRATO 2': ('Residencial 2 Ocupado',  'principal'),
    '3 - ESTRATO 3': ('Residencial 3 Ocupado',  'principal'),
    '1 - COMERCIAL': ('Comercial 0 Ocupado',    'principal'),
}
# Subcategorías conocidas que requieren asignación manual (quedan en NULL):
_SUBCATS_MANUAL = {
    '3 - OFICIAL', '9 - INDUSTRIAL EXENTO CONTRIBUCION', '13 - OFICIAL EDUCACION',
    '2 - INDUSTRIAL', '4 - AUTOCONSUMO',
    '5 - ALUMBRADO PUBLICO', '5 - ALUMBRADO P\xc3\x9aBLICO',
    '6 - TOTALIZADOR MACROMEDIDOR',
}

_SUBCATS_HOJA1 = {k for k, (_, lote) in MAPA_SUBCATEGORIA.items() if lote == 'hoja1'}


def _norm_subcat(s):
    """Normaliza subcategoría para lookup robusto: quita tildes y chars de reemplazo."""
    s = s.replace('�', '').strip()
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').strip().upper()


_MAPA_NORM = {_norm_subcat(k): v for k, v in MAPA_SUBCATEGORIA.items()}

# ── Constantes de formato AIR-E ───────────────────────────────────────────────

_SUFIJO   = '1261'
_CONVENIO = '2087'
_LARGO_FC = 235
_LARGO_FD = 2000
_FIN_ID_FC     = 16
_FIN_VALOR_FC  = 45
_COL_PERIODO_FC = 229
_FIN_ID_FD     = 12

MESES_TEXTO = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO',
               'JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE']

# ── Tarifas por defecto (Mayo 2026) ───────────────────────────────────────────

TARIFAS_DEFAULT = {
    'Comercial 0 Ocupado': {
        'valor': 44290, 'precio_xlsx': 44290.65,
        'sub_val': '+14.763,55', 'sub_pct': '+50,00',
        'tarifa_media': '29.527,11', 'TC': '3.530,99', 'TLU': '-0,11',
        'TBL': '11.986,94', 'TRT': '7.016,99', 'TDF': '6.506,77', 'TTL': '484,86',
    },
    'Comercial 0 Desocupado': {
        'valor': 22145, 'precio_xlsx': 22145.33,
        'sub_val': '+7.381,78', 'sub_pct': '+50,00',
        'tarifa_media': '14.763,55', 'TC': '1.765,50', 'TLU': '-0,06',
        'TBL': '5.993,47', 'TRT': '3.508,50', 'TDF': '3.253,39', 'TTL': '242,43',
    },
    'Residencial 1 Ocupado': {
        'valor': 8860, 'precio_xlsx': 8858.13,
        'sub_val': '-20.668,97', 'sub_pct': '-70,00',
        'tarifa_media': '29.527,10', 'TC': '3.531,41', 'TLU': '0,31',
        'TBL': '11.987,36', 'TRT': '7.017,41', 'TDF': '6.507,19', 'TTL': '485,28',
    },
    'Residencial 1 Desocupado': {
        'valor': 4430, 'precio_xlsx': 4429.07,
        'sub_val': '-25.098,03', 'sub_pct': '-85,00',
        'tarifa_media': '29.527,10', 'TC': '3.531,26', 'TLU': '0,16',
        'TBL': '11.987,21', 'TRT': '7.017,26', 'TDF': '6.507,04', 'TTL': '485,13',
    },
    'Residencial 2 Ocupado': {
        'valor': 17720, 'precio_xlsx': 17716.26,
        'sub_val': '-11.810,84', 'sub_pct': '-40,00',
        'tarifa_media': '29.527,10', 'TC': '3.531,72', 'TLU': '0,62',
        'TBL': '11.987,67', 'TRT': '7.017,72', 'TDF': '6.507,50', 'TTL': '485,59',
    },
    'Residencial 2 Desocupado': {
        'valor': 8860, 'precio_xlsx': 8858.13,
        'sub_val': '-20.668,97', 'sub_pct': '-70,00',
        'tarifa_media': '29.527,10', 'TC': '3.531,41', 'TLU': '0,31',
        'TBL': '11.987,36', 'TRT': '7.017,41', 'TDF': '6.507,19', 'TTL': '485,28',
    },
    'Residencial 3 Ocupado': {
        'valor': 25100, 'precio_xlsx': 25098.04,
        'sub_val': '-4.429,07', 'sub_pct': '-15,00',
        'tarifa_media': '29.527,11', 'TC': '3.531,43', 'TLU': '0,33',
        'TBL': '11.987,38', 'TRT': '7.017,43', 'TDF': '6.507,21', 'TTL': '485,30',
    },
    'Residencial 3 Desocupado': {
        'valor': 12550, 'precio_xlsx': 12549.02,
        'sub_val': '-16.978,08', 'sub_pct': '-57,50',
        'tarifa_media': '29.527,10', 'TC': '3.531,26', 'TLU': '0,16',
        'TBL': '11.987,21', 'TRT': '7.017,26', 'TDF': '6.507,04', 'TTL': '485,13',
    },
}

USO_ORDEN = [
    'Residencial 1 Ocupado',
    'Residencial 2 Ocupado',
    'Residencial 3 Ocupado',
    'Comercial 0 Ocupado',
    'Residencial 1 Desocupado',
    'Residencial 2 Desocupado',
    'Residencial 3 Desocupado',
    'Comercial 0 Desocupado',
]

# ── Creación de tablas ────────────────────────────────────────────────────────

def setup_tablas(conn):
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tarifas_volcado (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            uso          VARCHAR(50) NOT NULL UNIQUE,
            valor        INT         NOT NULL DEFAULT 0,
            precio_xlsx  DECIMAL(10,2)        DEFAULT 0,
            sub_val      VARCHAR(30)          DEFAULT '',
            sub_pct      VARCHAR(20)          DEFAULT '',
            tarifa_media VARCHAR(30)          DEFAULT '',
            TC  VARCHAR(20) DEFAULT '', TLU VARCHAR(20) DEFAULT '',
            TBL VARCHAR(20) DEFAULT '', TRT VARCHAR(20) DEFAULT '',
            TDF VARCHAR(20) DEFAULT '', TTL VARCHAR(20) DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS volcado_config (
            id             INT NOT NULL DEFAULT 1 PRIMARY KEY,
            carpeta_salida VARCHAR(500) DEFAULT '',
            email_destino  VARCHAR(200) DEFAULT ''
        )
    """)
    cur.execute("INSERT IGNORE INTO volcado_config (id) VALUES (1)")

    # Tabla clave-valor para configuración global (SMTP, etc.)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            config_key   VARCHAR(100) NOT NULL PRIMARY KEY,
            config_value TEXT         NOT NULL
        )
    """)

    # Columnas nuevas en tarifas_volcado (idempotente: try/except absorbe "duplicate column")
    for ddl in [
        "ALTER TABLE tarifas_volcado ADD COLUMN precio_xlsx  DECIMAL(10,2) DEFAULT 0",
        "ALTER TABLE tarifas_volcado ADD COLUMN sub_val      VARCHAR(30)   DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN sub_pct      VARCHAR(20)   DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN tarifa_media VARCHAR(30)   DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN TC  VARCHAR(20) DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN TLU VARCHAR(20) DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN TBL VARCHAR(20) DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN TRT VARCHAR(20) DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN TDF VARCHAR(20) DEFAULT ''",
        "ALTER TABLE tarifas_volcado ADD COLUMN TTL VARCHAR(20) DEFAULT ''",
    ]:
        try:
            cur.execute(ddl)
        except Exception:
            pass

    # Columna email_destino en volcado_config (idempotente)
    try:
        cur.execute("ALTER TABLE volcado_config ADD COLUMN email_destino VARCHAR(200) DEFAULT ''")
    except Exception:
        pass

    # Columnas lote y uso_volcado en suscriptores (idempotente)
    for ddl in [
        "ALTER TABLE suscriptores ADD COLUMN lote        VARCHAR(10) NOT NULL DEFAULT 'principal'",
        "ALTER TABLE suscriptores ADD COLUMN uso_volcado VARCHAR(50) DEFAULT NULL",
    ]:
        try:
            cur.execute(ddl)
        except Exception:
            pass

    def _cn(col):
        return f"COALESCE(NULLIF({col},''), VALUES({col}))"

    for uso, t in TARIFAS_DEFAULT.items():
        cur.execute(f"""
            INSERT INTO tarifas_volcado
              (uso, valor, precio_xlsx, sub_val, sub_pct, tarifa_media,
               TC, TLU, TBL, TRT, TDF, TTL)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              precio_xlsx  = COALESCE(IF(precio_xlsx=0 OR precio_xlsx IS NULL,
                               NULL, precio_xlsx), VALUES(precio_xlsx)),
              sub_val      = {_cn('sub_val')},
              sub_pct      = {_cn('sub_pct')},
              tarifa_media = {_cn('tarifa_media')},
              TC={_cn('TC')}, TLU={_cn('TLU')}, TBL={_cn('TBL')},
              TRT={_cn('TRT')}, TDF={_cn('TDF')}, TTL={_cn('TTL')}
        """, (uso, t['valor'], t.get('precio_xlsx', t['valor']),
              t['sub_val'], t['sub_pct'], t['tarifa_media'],
              t['TC'], t['TLU'], t['TBL'], t['TRT'], t['TDF'], t['TTL']))

    conn.commit()
    cur.close()


# ── Config ────────────────────────────────────────────────────────────────────

def cargar_config(conn):
    cur = conn.cursor()
    cur.execute("SELECT carpeta_salida, email_destino FROM volcado_config WHERE id=1")
    row = cur.fetchone()
    cfg = {'carpeta_salida': '', 'email_destino': '',
           'smtp_user': '', 'smtp_password': '', 'smtp_destinatarios': ''}
    if row:
        cfg['carpeta_salida'] = row[0] or ''
        cfg['email_destino']  = row[1] or ''
    try:
        _ensure_app_config(cur)
        cur.execute("""
            SELECT config_key, config_value FROM app_config
            WHERE config_key IN ('smtp_user', 'smtp_password', 'smtp_destinatarios')
        """)
        for k, v in cur.fetchall():
            cfg[k] = v or ''
    except Exception:
        pass
    cur.close()
    return cfg


def guardar_config(conn, carpeta_salida, email_destino):
    cur = conn.cursor()
    cur.execute(
        "UPDATE volcado_config SET carpeta_salida=%s, email_destino=%s WHERE id=1",
        (carpeta_salida, email_destino),
    )
    conn.commit()
    cur.close()


_CREATE_APP_CONFIG = """
    CREATE TABLE IF NOT EXISTS app_config (
        config_key   VARCHAR(100) NOT NULL PRIMARY KEY,
        config_value TEXT         NOT NULL
    )
"""


def _ensure_app_config(cur):
    cur.execute(_CREATE_APP_CONFIG)


def guardar_email_config(conn, smtp_user, smtp_password, smtp_destinatarios):
    cur = conn.cursor()
    _ensure_app_config(cur)
    for key, val in [
        ('smtp_user',          smtp_user),
        ('smtp_password',      smtp_password),
        ('smtp_destinatarios', smtp_destinatarios),
    ]:
        cur.execute("""
            INSERT INTO app_config (config_key, config_value) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
        """, (key, val))
    conn.commit()
    cur.close()


def cargar_smtp_config(conn):
    """Retorna {'user': ..., 'password': ...} desde app_config, o {} si no está configurado."""
    cur = conn.cursor()
    try:
        _ensure_app_config(cur)
        cur.execute("""
            SELECT config_key, config_value FROM app_config
            WHERE config_key IN ('smtp_user', 'smtp_password')
        """)
        rows = {r[0]: r[1] for r in cur.fetchall()}
        if rows.get('smtp_user'):
            return {'user': rows['smtp_user'], 'password': rows.get('smtp_password', '')}
        return {}
    except Exception:
        return {}
    finally:
        cur.close()


# ── Tarifas ───────────────────────────────────────────────────────────────────

def cargar_tarifas(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT uso, valor, precio_xlsx, sub_val, sub_pct, tarifa_media,
                   TC, TLU, TBL, TRT, TDF, TTL
            FROM tarifas_volcado
        """)
        rows = cur.fetchall()
    except Exception:
        cur.close()
        return {k: dict(v) for k, v in TARIFAS_DEFAULT.items()}
    cur.close()
    result = {k: dict(v) for k, v in TARIFAS_DEFAULT.items()}
    for r in rows:
        uso = r[0]
        d = result.get(uso, dict(TARIFAS_DEFAULT.get(uso, {})))
        result[uso] = {
            'valor':        int(r[1] or 0) or d.get('valor', 0),
            'precio_xlsx':  float(r[2] or r[1] or 0) or d.get('precio_xlsx', 0),
            'sub_val':      r[3] or d.get('sub_val', ''),
            'sub_pct':      r[4] or d.get('sub_pct', ''),
            'tarifa_media': r[5] or d.get('tarifa_media', ''),
            'TC':  r[6]  or d.get('TC', ''),
            'TLU': r[7]  or d.get('TLU', ''),
            'TBL': r[8]  or d.get('TBL', ''),
            'TRT': r[9]  or d.get('TRT', ''),
            'TDF': r[10] or d.get('TDF', ''),
            'TTL': r[11] or d.get('TTL', ''),
        }
    return result


def guardar_tarifas(conn, tarifas):
    cur = conn.cursor()
    for uso, t in tarifas.items():
        cur.execute("""
            INSERT INTO tarifas_volcado
              (uso, valor, precio_xlsx, sub_val, sub_pct, tarifa_media,
               TC, TLU, TBL, TRT, TDF, TTL)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              valor=%s, precio_xlsx=%s, sub_val=%s, sub_pct=%s,
              tarifa_media=%s, TC=%s, TLU=%s, TBL=%s, TRT=%s, TDF=%s, TTL=%s
        """, (uso, t['valor'], t.get('precio_xlsx', t['valor']),
              t['sub_val'], t['sub_pct'], t['tarifa_media'],
              t['TC'], t['TLU'], t['TBL'], t['TRT'], t['TDF'], t['TTL'],
              t['valor'], t.get('precio_xlsx', t['valor']),
              t['sub_val'], t['sub_pct'], t['tarifa_media'],
              t['TC'], t['TLU'], t['TBL'], t['TRT'], t['TDF'], t['TTL']))
    conn.commit()
    cur.close()


# ── Utilidades de período ─────────────────────────────────────────────────────

def periodo_siguiente(aaaamm):
    anio, mes = int(aaaamm[:4]), int(aaaamm[4:])
    mes += 1
    if mes > 12:
        mes, anio = 1, anio + 1
    return f'{anio}{mes:02d}'


def nombre_mes(aaaamm):
    nombres = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    anio, mes = int(aaaamm[:4]), int(aaaamm[4:])
    return f'{nombres[mes-1]} {anio}'


def periodo_actual():
    from datetime import date
    hoy = date.today()
    return f'{hoy.year}{hoy.month:02d}'


# ── Generador de volcado desde BD ─────────────────────────────────────────────

def _co_fmt(v):
    """17720.0 → '17.720,00'  (formato colombiano)"""
    s = f'{abs(float(v)):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return s


def _xml_suscriptor(uso, valor, hist6, periodo_texto, t):
    """Genera el bloque XML completo para una línea FD."""
    total_fmt = _co_fmt(valor)
    h = [_co_fmt(v) for v in hist6]
    return (
        '<INFO_ASEO>'
        '<INFO_EMPRESA>'
        '<EMPRESA>INGESAM.ASEO.S.A.S.E.S.P</EMPRESA>'
        '<NIT>900920770-5</NIT>'
        '<FRECUENCIA_BARRIDOS_POR_SEMANA>1</FRECUENCIA_BARRIDOS_POR_SEMANA>'
        '<FRECUENCIA_RECOLECCION_POR_SEMANA>2</FRECUENCIA_RECOLECCION_POR_SEMANA>'
        f'<USO>{uso}</USO>'
        '<ESTRATO>o</ESTRATO>'
        '<SUBSIDIO_CONTRIBUCION>'
        f'<VALOR>{t.get("sub_val","")}</VALOR>'
        f'<PORCENTAJE>{t.get("sub_pct","")}</PORCENTAJE>'
        '</SUBSIDIO_CONTRIBUCION>'
        f'<PERIODO_FACTURADO>{periodo_texto}</PERIODO_FACTURADO>'
        f'<TARIFA_MEDIA>{t.get("tarifa_media","")}</TARIFA_MEDIA>'
        '<M3></M3>'
        '</INFO_EMPRESA>'
        '<DESGLOSE_SERVICIO>'
        '<TRLU>0,00</TRLU><TRBL>0,00</TRBL><TRRA>0,00</TRRA>'
        '<TRA>0,00</TRA><TRNA>0,00</TRNA><TAFA>0,00</TAFA>'
        '<TAFNA>0.00</TAFNA><VBA>0.00</VBA>'
        f'<TC>{t.get("TC","")}</TC>'
        f'<TLU>{t.get("TLU","")}</TLU>'
        f'<TBL>{t.get("TBL","")}</TBL>'
        f'<TRT>{t.get("TRT","")}</TRT>'
        f'<TDF>{t.get("TDF","")}</TDF>'
        f'<TTL>{t.get("TTL","")}</TTL>'
        '<TA>0,00</TA>'
        f'<TOTAL>{total_fmt}</TOTAL>'
        '</DESGLOSE_SERVICIO>'
        '<DESCUENTOS_POR_FALLA_EN_CALIDAD_SERVICIO>'
        '<V_RCF></V_RCF><V_CTR_NA></V_CTR_NA><V_CRS></V_CRS><D_TOTAL_></D_TOTAL_>'
        '</DESCUENTOS_POR_FALLA_EN_CALIDAD_SERVICIO>'
        '<VALORES_INFORMATIVOS>'
        '<UNIDADES_RESIDENCIALES></UNIDADES_RESIDENCIALES>'
        '<UNIDADES_NO_RESIDENCIALES></UNIDADES_NO_RESIDENCIALES>'
        '</VALORES_INFORMATIVOS>'
        '<HISTORICO_FACTURACION>'
        f'<MES_1>{h[0]}</MES_1><MES_2>{h[1]}</MES_2><MES_3>{h[2]}</MES_3>'
        f'<MES_4>{h[3]}</MES_4><MES_5>{h[4]}</MES_5><MES_6>{h[5]}</MES_6>'
        '</HISTORICO_FACTURACION>'
        '<HISTORICO_PRODUCCION>'
        '<MES_1>0,00</MES_1><MES_1>0,00</MES_1><MES_1>0,00</MES_1>'
        '</HISTORICO_PRODUCCION>'
        '</INFO_ASEO>'
    )


def _linea_fc(nic_str, valor, periodo):
    id_completo = nic_str + _SUFIJO
    campo = f'{valor * 100}DB'
    linea = 'FC' + id_completo.rjust(_FIN_ID_FC - 2)
    linea = linea + campo.rjust(_FIN_VALOR_FC - len(linea))
    linea = linea.ljust(_COL_PERIODO_FC) + periodo
    if len(linea) != _LARGO_FC:
        raise ValueError(f'FC de {len(linea)} chars (NIC {nic_str})')
    return linea


def _linea_fd(nic_str, xml):
    cabecera = 'FD' + nic_str.rjust(_FIN_ID_FD - 2)
    relleno = _LARGO_FD - len(cabecera) - len(xml)
    if relleno < 0:
        raise ValueError(f'XML demasiado largo para NIC {nic_str}')
    return cabecera + ' ' * relleno + xml


def generar_volcado_bd(conn, tarifas, carpeta_salida, periodo_salida):
    """
    Genera los 4 TXT del volcado directamente desde BD.

    Retorna (totales_dict, errores_list).
    totales_dict = {'principal': N, 'hoja1': M}
    """
    os.makedirs(carpeta_salida, exist_ok=True)
    periodo_texto = MESES_TEXTO[int(periodo_salida[4:]) - 1] + ' ' + periodo_salida[:4]

    cur = conn.cursor()

    # cuenta = NIC del usuario; susccodi = codigo AIR-E distinto que va en el volcado
    cur.execute("""
        SELECT cuenta, susccodi, lote, uso_volcado
        FROM suscriptores
        WHERE uso_volcado IS NOT NULL AND uso_volcado != ''
        ORDER BY cuenta
    """)
    suscriptores = cur.fetchall()

    # Histórico: últimos 6 períodos antes del periodo_salida
    periodos_hist = []
    a, m = int(periodo_salida[:4]), int(periodo_salida[4:])
    for _ in range(6):
        m -= 1
        if m == 0:
            m, a = 12, a - 1
        periodos_hist.append((a, m))

    # Mapa cuenta → [valor_mes1, valor_mes2, ...] (orden cronológico desc)
    hist_map = {}
    for pa, pm in periodos_hist:
        cur.execute("""
            SELECT cuenta_contrato, SUM(valor_recibo)
            FROM facturas
            WHERE anno=%s AND CAST(mes AS UNSIGNED)=%s
            GROUP BY cuenta_contrato
        """, (pa, pm))
        for cuenta_c, valor in cur.fetchall():
            if cuenta_c not in hist_map:
                hist_map[cuenta_c] = []
            if len(hist_map[cuenta_c]) < 6:
                hist_map[cuenta_c].append(float(valor or 0))

    cur.close()

    lotes = {'principal': ([], []), 'hoja1': ([], [])}
    errores = []

    for cuenta, susccodi, lote, uso in suscriptores:
        lote = lote if lote in lotes else 'principal'
        t = tarifas.get(uso)
        if not t:
            errores.append(f'NIC {cuenta}: uso "{uso}" sin tarifa definida')
            continue

        valor = int(t['valor'])
        hist6 = hist_map.get(susccodi, [])  # facturas.cuenta_contrato = susccodi
        while len(hist6) < 6:
            hist6.append(0.0)

        nic_str = str(int(susccodi))  # codigo AIR-E que va en la linea FC
        try:
            xml = _xml_suscriptor(uso, valor, hist6, periodo_texto, t)
            fc  = _linea_fc(nic_str, valor, periodo_salida)
            fd  = _linea_fd(nic_str, xml)
        except Exception as e:
            errores.append(str(e))
            continue

        lotes[lote][0].append(fc)
        lotes[lote][1].append(fd)

    # Escribir archivos
    p = periodo_salida
    nombres = {
        'principal': (f'INGESAM_VOLCADO_{_CONVENIO}_{p}.txt',
                      f'INFO_ADICIONAL_INGESAM_{_CONVENIO}_{p}.txt'),
        'hoja1':     (f'Hoja1_INGESAM_VOLCADO_{_CONVENIO}_{p}.txt',
                      f'Hoja1_INFO_ADICIONAL_INGESAM_{_CONVENIO}_{p}.txt'),
    }
    totales = {}
    for lote, (fcs, fds) in lotes.items():
        if not fcs:
            continue
        f_vol, f_info = nombres[lote]
        with open(os.path.join(carpeta_salida, f_vol),  'w', encoding='ascii', newline='') as fv:
            fv.write('\n'.join(fcs) + '\n')
        with open(os.path.join(carpeta_salida, f_info), 'w', encoding='ascii', newline='') as fi:
            fi.write('\n'.join(fds) + '\n')
        totales[lote] = len(fcs)

    generar_xlsx_precios(tarifas, carpeta_salida)
    return totales, errores


def validar_volcado_bd(conn, tarifas, periodo_salida):
    """Valida sin escribir archivos. Retorna lista de errores."""
    errores = []
    cur = conn.cursor()
    cur.execute("""
        SELECT cuenta, uso_volcado FROM suscriptores
        WHERE uso_volcado IS NOT NULL AND uso_volcado != ''
    """)
    rows = cur.fetchall()
    cur.close()

    sin_tarifa = [uso for _, uso in rows if uso not in tarifas]
    if sin_tarifa:
        usos_unicos = sorted(set(sin_tarifa))
        errores.append(f'Sin tarifa definida: {", ".join(usos_unicos)}')

    # Verificar largo FC/FD con primer suscriptor de cada uso
    visto = set()
    for cuenta, uso in rows:
        if uso in visto:
            continue
        visto.add(uso)
        t = tarifas.get(uso)
        if not t:
            continue
        nic_str = str(int(cuenta))
        try:
            xml = _xml_suscriptor(uso, int(t['valor']), [0.0]*6, 'TEST', t)
            fc  = _linea_fc(nic_str, int(t['valor']), periodo_salida)
            fd  = _linea_fd(nic_str, xml)
            if len(fc) != _LARGO_FC:
                errores.append(f'FC de largo incorrecto para {uso}')
            if len(fd) != _LARGO_FD:
                errores.append(f'FD de largo incorrecto para {uso} ({len(fd)} chars)')
        except Exception as e:
            errores.append(str(e))

    return errores


# ── XLSX de precios ───────────────────────────────────────────────────────────

_CATEGORIA = {
    'Comercial 0 Ocupado':      'COMERCIAL',
    'Comercial 0 Desocupado':   'COMERCIAL',
    'Residencial 1 Ocupado':    'RESIDENCIAL',
    'Residencial 1 Desocupado': 'RESIDENCIAL',
    'Residencial 2 Ocupado':    'RESIDENCIAL',
    'Residencial 2 Desocupado': 'RESIDENCIAL',
    'Residencial 3 Ocupado':    'RESIDENCIAL',
    'Residencial 3 Desocupado': 'RESIDENCIAL',
}


def importar_catastro(conn, ruta_xlsx):
    """Delega al motor unificado en utils.catastro. conn se usa pero no se cierra."""
    from utils.catastro import importar_catastro as _cat
    res = _cat(ruta_xlsx, conn_externo=conn)
    if res.get('error'):
        raise Exception(res['error'])
    return res


def generar_xlsx_precios(tarifas, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Hoja1'
    ws.append(['CONSORCIO', 'TERCERO', 'DEPARTAMENTO', 'MUNICIPIO',
               'CORREGIMIENTO', 'CATEGORIA', 'SUBCATEGORIA', 'PRECIO $:'])
    for uso in USO_ORDEN:
        if uso not in tarifas:
            continue
        precio = tarifas[uso].get('precio_xlsx') or tarifas[uso]['valor']
        ws.append(['INGESAM', 'ASEO', 'LA GUAJIRA', 'HATONUEVO', 'HATONUEVO',
                   _CATEGORIA.get(uso, ''), uso, float(precio)])
    ruta = os.path.join(output_dir, 'TABLA_PRECIOS_ASEO.xlsx')
    wb.save(ruta)
    return ruta

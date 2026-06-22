"""
Motor unificado de importación de catastro AIR-E.

Combina:
- utils/importar.py  → lectura multi-formato (CSV/XLSX), upsert masivo, marca retirados
- utils/volcado.py   → asignación uso_volcado/lote desde MAPA_SUBCATEGORIA

La función principal es importar_catastro(filepath, conn_externo=None).
"""
import re
import unicodedata
import pandas as pd
from db.connection import get_connection

_BATCH = 500

# ── Mapa subcategoría → (uso_volcado, lote) ──────────────────────────────────
MAPA_SUBCATEGORIA = {
    '1 - ESTRATO 1': ('Residencial 1 Ocupado',  'principal'),
    '2 - ESTRATO 2': ('Residencial 2 Ocupado',  'principal'),
    '3 - ESTRATO 3': ('Residencial 3 Ocupado',  'principal'),
    '1 - COMERCIAL': ('Comercial 0 Ocupado',    'principal'),
}

_SUBCATS_MANUAL = {
    '3 - OFICIAL', '9 - INDUSTRIAL EXENTO CONTRIBUCION',
    '13 - OFICIAL EDUCACION', '2 - INDUSTRIAL',
    '4 - AUTOCONSUMO', '5 - ALUMBRADO PUBLICO',
    '5 - ALUMBRADO PÚBLICO', '6 - TOTALIZADOR MACROMEDIDOR',
}


def _norm_subcat(s):
    s = s.replace('�', '').strip()
    return (unicodedata.normalize('NFKD', s)
            .encode('ascii', 'ignore').decode('ascii').strip().upper())


_MAPA_NORM = {_norm_subcat(k): v for k, v in MAPA_SUBCATEGORIA.items()}
_SUBCATS_MANUAL_NORM = {_norm_subcat(s) for s in _SUBCATS_MANUAL}


def _uso_lote(subcategoria_raw):
    return _MAPA_NORM.get(_norm_subcat(subcategoria_raw))


# ── Lectura de archivo ────────────────────────────────────────────────────────

def _read_file(filepath):
    if filepath.lower().endswith('.csv'):
        df = None
        for sep in ('|', ';', ','):
            try:
                tmp = pd.read_csv(filepath, sep=sep, encoding='latin-1')
                if len(tmp.columns) > 1:
                    df = tmp
                    break
            except Exception:
                pass
        if df is None:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        df.columns = [c.strip().strip('"').upper() for c in df.columns]
    else:
        df = pd.read_excel(filepath)
        df.columns = [c.strip().upper() for c in df.columns]
    return df


def _extraer_estrato(subcategoria):
    if not subcategoria:
        return ''
    partes = str(subcategoria).split(' - ', 1)
    if len(partes) < 2:
        return subcategoria.strip()
    texto = partes[1].strip()
    if re.match(r'^ESTRATO\s+\d+$', texto, re.IGNORECASE):
        return partes[0].strip()
    return texto


# ── Upsert masivo ─────────────────────────────────────────────────────────────

_PREFIX = """
    INSERT INTO suscriptores
    (cuenta, susccodi, nombre, direccion, municipio, barrio,
     subcategoria, estrato, estado_suministro, territorial,
     departamento, sufijo, desc_servicio, periodo, uso_volcado, lote)
    VALUES """
_PH = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
# uso_volcado y lote se excluyen del ON DUPLICATE KEY UPDATE
# para no sobreescribir asignaciones manuales en registros existentes
_SUFFIX = """
    ON DUPLICATE KEY UPDATE
      susccodi=VALUES(susccodi), nombre=VALUES(nombre),
      direccion=VALUES(direccion), municipio=VALUES(municipio),
      barrio=VALUES(barrio), subcategoria=VALUES(subcategoria),
      estrato=VALUES(estrato), estado_suministro=VALUES(estado_suministro),
      territorial=VALUES(territorial), departamento=VALUES(departamento),
      sufijo=VALUES(sufijo), desc_servicio=VALUES(desc_servicio),
      periodo=VALUES(periodo)"""


def _bulk_upsert(cursor, conn, rows):
    total_rc = 0
    for i in range(0, len(rows), _BATCH):
        batch = rows[i:i + _BATCH]
        sql = _PREFIX + ', '.join([_PH] * len(batch)) + _SUFFIX
        flat = [v for row in batch for v in row]
        cursor.execute(sql, flat)
        conn.commit()
        total_rc += cursor.rowcount
    return total_rc


# ── Función principal ─────────────────────────────────────────────────────────

def importar_catastro(filepath, conn_externo=None):
    """
    Importa catastro desde filepath (CSV, XLSX, XLS).

    conn_externo: conexión abierta externamente — se usa pero NO se cierra.
                  Si None, crea y cierra su propia conexión.

    Devuelve dict:
        nuevos         int   — filas insertadas
        actualizados   int   — filas actualizadas
        retirados      list  — cuentas marcadas como RETIRADO
        sin_clasificar list  — susccodi con subcategoría desconocida
        omitidos       int   — filas sin CUENTA válida
        error          str|None
    """
    try:
        df = _read_file(filepath)
    except Exception as e:
        return {'error': f'Error al leer archivo: {e}',
                'nuevos': 0, 'actualizados': 0,
                'retirados': [], 'sin_clasificar': [], 'omitidos': 0}

    cols = set(df.columns)
    if 'FECHA_RECAUDO' in cols:
        return {'error': 'Este archivo es un RECAUDO, no un catastro.',
                'nuevos': 0, 'actualizados': 0,
                'retirados': [], 'sin_clasificar': [], 'omitidos': 0}
    if 'NUMERO_FACTURA' in cols and 'ESTADO_SUMINISTRO' not in cols:
        return {'error': 'Este archivo parece ser una FACTURACIÓN, no un catastro.',
                'nuevos': 0, 'actualizados': 0,
                'retirados': [], 'sin_clasificar': [], 'omitidos': 0}

    _own_conn = conn_externo is None
    conn = conn_externo if conn_externo else get_connection()
    if not conn:
        return {'error': 'Sin conexión a la base de datos',
                'nuevos': 0, 'actualizados': 0,
                'retirados': [], 'sin_clasificar': [], 'omitidos': 0}

    cursor = conn.cursor()
    try:
        # Estado actual de la BD
        cursor.execute("SELECT cuenta FROM suscriptores")
        existentes = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT susccodi, uso_volcado FROM suscriptores")
        uso_actual = {str(row[0]): row[1] for row in cursor.fetchall()}

        upsert_rows    = []
        uso_update     = []   # (uso, lote, susccodi) — existentes con uso_volcado NULL
        sin_clasificar = []
        en_archivo     = set()
        omitidos       = 0

        for _, row in df.iterrows():
            try:
                cuenta = int(row.get('CUENTA', 0) or 0)
                if not cuenta:
                    omitidos += 1
                    continue
                en_archivo.add(cuenta)

                susccodi_raw = row.get('SUSCCODI', '')
                susccodi = int(float(str(susccodi_raw))) if susccodi_raw else cuenta
                subcategoria = str(
                    row.get('SUBCATEORIA', '') or row.get('SUBCATEGORIA', '') or ''
                )
                ul = _uso_lote(subcategoria)

                if not ul and subcategoria:
                    if _norm_subcat(subcategoria) not in _SUBCATS_MANUAL_NORM:
                        sin_clasificar.append(f'{susccodi} ({subcategoria})')

                uso_v  = ul[0] if ul else None
                lote_v = ul[1] if ul else None

                # Programar update de uso_volcado solo si está NULL en BD
                s_key = str(susccodi)
                if s_key in uso_actual and not uso_actual[s_key] and uso_v:
                    uso_update.append((uso_v, lote_v or 'principal', susccodi))

                upsert_rows.append((
                    cuenta,
                    susccodi,
                    str(row.get('NOMBRE',           '') or ''),
                    str(row.get('DIRECCION',         '') or ''),
                    str(row.get('MUNICIPIO',         '') or ''),
                    str(row.get('BARRIO',            '') or ''),
                    subcategoria,
                    _extraer_estrato(subcategoria),
                    str(row.get('ESTADO_SUMINISTRO', '') or ''),
                    str(row.get('TERRITORIAL',       '') or ''),
                    str(row.get('DEPARTAMENTO',      '') or ''),
                    str(row.get('SUFIJO',            '') or ''),
                    str(row.get('DESC_SERVICIO',     '') or ''),
                    str(row.get('PERIODO',           '') or ''),
                    uso_v,
                    lote_v,
                ))
            except Exception:
                omitidos += 1

        if not upsert_rows:
            return {'error': 'No se encontraron filas válidas en el archivo.',
                    'nuevos': 0, 'actualizados': 0,
                    'retirados': [], 'sin_clasificar': sin_clasificar, 'omitidos': omitidos}

        total_rc = _bulk_upsert(cursor, conn, upsert_rows)
        n_total = len(upsert_rows)
        n_actualizados = max(0, total_rc - n_total)
        n_nuevos = n_total - n_actualizados

        # Asignar uso_volcado a existentes que lo tenían en NULL
        if uso_update:
            for i in range(0, len(uso_update), _BATCH):
                cursor.executemany(
                    "UPDATE suscriptores SET uso_volcado=%s, lote=%s WHERE susccodi=%s",
                    uso_update[i:i + _BATCH]
                )
            conn.commit()

        # Marcar retirados
        retirados = list(existentes - en_archivo)
        if retirados:
            for i in range(0, len(retirados), _BATCH):
                lote_r = retirados[i:i + _BATCH]
                ph = ', '.join(['%s'] * len(lote_r))
                cursor.execute(
                    f"UPDATE suscriptores SET estado_suministro='RETIRADO' WHERE cuenta IN ({ph})",
                    lote_r
                )
            conn.commit()

        return {
            'nuevos':         n_nuevos,
            'actualizados':   n_actualizados,
            'retirados':      retirados,
            'sin_clasificar': sin_clasificar,
            'omitidos':       omitidos,
            'error':          None,
        }

    except Exception as e:
        return {'error': str(e),
                'nuevos': 0, 'actualizados': 0,
                'retirados': [], 'sin_clasificar': [], 'omitidos': 0}
    finally:
        cursor.close()
        if _own_conn:
            conn.close()

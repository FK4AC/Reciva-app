"""
Helper de lectura/escritura para la tabla config_sistema.
Cada cliente tiene sus propios valores (empresa, módulos, etiquetas).
"""

from db.connection import get_connection

_cache: dict = {}
_cache_valido = False


def _con():
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sin conexión a la base de datos")
    return conn


def _invalidar():
    global _cache_valido
    _cache_valido = False


def get_all() -> dict:
    global _cache, _cache_valido
    if _cache_valido:
        return dict(_cache)
    conn = _con()
    try:
        cur = conn.cursor()
        cur.execute("SELECT clave, valor FROM config_sistema")
        rows = cur.fetchall()
        cur.close()
        _cache = {k: v for k, v in rows}
        _cache_valido = True
        return dict(_cache)
    finally:
        conn.close()


def get(clave: str, default: str = '') -> str:
    try:
        return get_all().get(clave, default)
    except Exception:
        return default


def set(clave: str, valor: str):
    conn = _con()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO config_sistema (clave, valor) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE valor = VALUES(valor)",
            (clave, valor)
        )
        conn.commit()
        cur.close()
        _invalidar()
    finally:
        conn.close()


def set_many(cambios: dict):
    """Guarda múltiples claves en una sola transacción."""
    conn = _con()
    try:
        cur = conn.cursor()
        for clave, valor in cambios.items():
            cur.execute(
                "INSERT INTO config_sistema (clave, valor) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE valor = VALUES(valor)",
                (clave, str(valor))
            )
        conn.commit()
        cur.close()
        _invalidar()
    finally:
        conn.close()


def modulos_activos() -> set:
    """Devuelve el conjunto de módulos activos, ej: {'clientes','cobros','volcado'}."""
    raw = get('modulos_activos', 'clientes,cobros,pagos,soporte,estadisticas')
    return {m.strip() for m in raw.split(',') if m.strip()}


def volcado_activo() -> bool:
    return 'volcado' in modulos_activos()


def init_defaults(conn=None):
    """Inserta los valores por defecto si la tabla está vacía. Usa conn externo si se provee."""
    close_after = False
    if conn is None:
        conn = _con()
        close_after = True
    try:
        cur = conn.cursor()
        defaults = [
            ('empresa_nombre',   ''),
            ('empresa_nit',      ''),
            ('empresa_logo',     ''),
            ('modulos_activos',  'clientes,cobros,pagos,soporte,estadisticas'),
            ('label_clientes',   'Clientes'),
            ('label_cobros',     'Cobros'),
            ('label_pagos',      'Pagos'),
            ('label_soporte',    'Soporte'),
            ('label_id_cliente', 'Código'),
        ]
        for clave, valor in defaults:
            cur.execute(
                "INSERT IGNORE INTO config_sistema (clave, valor) VALUES (%s, %s)",
                (clave, valor)
            )
        conn.commit()
        cur.close()
        _invalidar()
    finally:
        if close_after:
            conn.close()

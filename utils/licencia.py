"""
Verifica codigos de activacion generados por generar_licencia.py.
La clave maestra esta embebida — aceptable para escala 1-50 clientes.
"""

import base64
import json
import zlib
from datetime import date

from cryptography.fernet import Fernet, InvalidToken

_MASTER_KEY = b'wZK8Fp5d3MgIn_KJ85Ha7lmPlfliHd-U6fSAE8ehlGg='
_fernet = Fernet(_MASTER_KEY)


class LicenciaError(Exception):
    pass


def verificar_codigo(codigo: str) -> dict:
    """Decodifica el codigo de activacion y retorna las credenciales de BD.

    Raises LicenciaError con mensaje legible si el codigo es invalido o expiro.
    """
    try:
        token = base64.urlsafe_b64decode(codigo.strip().encode())
        raw   = zlib.decompress(_fernet.decrypt(token))
        data  = json.loads(raw.decode('utf-8'))
    except InvalidToken:
        raise LicenciaError('Codigo de activacion incorrecto.')
    except Exception:
        raise LicenciaError('El codigo tiene un formato invalido.')

    expires = data.get('expires')
    if expires:
        try:
            if date.fromisoformat(expires) < date.today():
                raise LicenciaError(f'Este codigo expiro el {expires}.')
        except ValueError:
            pass

    for campo in ('host', 'port', 'user', 'password', 'database'):
        if not data.get(campo):
            raise LicenciaError(f'Codigo incompleto: falta el campo "{campo}".')

    return data

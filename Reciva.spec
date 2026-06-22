# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para Reciva — Kivy 2.x + Windows
# Compilar con: pyinstaller Reciva.spec

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# collect_all('kivy') falla porque kivy.garden es un namespace package
# con __path__ personalizado que rompe pkgutil.iter_modules.
kivy_datas    = collect_data_files('kivy')
kivy_binaries = collect_dynamic_libs('kivy')

# Solo los subpaquetes que la app realmente usa.
# Se omiten kivy.modules (debug) y kivy.network (no usado).
kivy_hiddenimports = (
    collect_submodules('kivy.uix') +
    collect_submodules('kivy.graphics') +
    collect_submodules('kivy.core') +
    collect_submodules('kivy.input') +
    collect_submodules('kivy.lang') +
    collect_submodules('kivy.modules') +
    [
        'kivy', 'kivy.app', 'kivy.animation', 'kivy.atlas',
        'kivy.base', 'kivy.cache', 'kivy.clock', 'kivy.compat',
        'kivy.config', 'kivy.context', 'kivy.event', 'kivy.factory',
        'kivy.geometry', 'kivy.logger', 'kivy.metrics', 'kivy.parser',
        'kivy.properties', 'kivy.resources', 'kivy.setupconfig',
        'kivy.support', 'kivy.utils', 'kivy.vector', 'kivy.weakmethod',
    ]
)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=kivy_binaries,
    datas=kivy_datas + [
        ('reciva.kv',      '.'),
        ('fonts',          'fonts'),
        ('logo_png',       'logo_png'),
        ('version.py',     '.'),
        # config.py y theme.py NO van aqui: PyInstaller los compila
        # automaticamente al ser modulos importados desde main.py.
        # estados_cuenta SI va: la app escribe PDFs ahi en runtime.
        ('estados_cuenta', 'estados_cuenta'),
    ],
    hiddenimports=kivy_hiddenimports + [
        # Base de datos
        'pymysql',
        'pymysql.cursors',
        # PDF
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.lib.styles',
        'reportlab.pdfbase',
        'reportlab.pdfbase.ttfonts',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.platypus',
        # Email
        'smtplib',
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        # Excel / CSV
        'openpyxl',
        'openpyxl.styles',
        'pandas',
        'pandas.io.formats.excel',
        # Stdlib usado explicitamente
        'hashlib',
        'threading',
        'csv',
        'json',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        # Dependencias opcionales de pandas que no se usan
        'scipy',
        'matplotlib',
        'matplotlib.backends',
        'PIL',
        'IPython',
        'jupyter',
        'notebook',
        'numba',
        'sqlalchemy',
        'boto3',
        'botocore',
        'pyarrow',
        'fastparquet',
        'tables',
        'blosc',
        'bottleneck',
        'numexpr',
        'statsmodels',
        'sklearn',
        'skimage',
        'cv2',
        'gi',
        'wx',
        # Kivy server/tools — no usados en produccion
        'kivy.network',
        'kivy.tools',
        # Documentacion y herramientas de desarrollo
        'docutils',
        'sphinx',
        'pygments',
        'babel',
        'jinja2',
        # Setuptools interno (no necesario en runtime)
        'setuptools',
        'pkg_resources',
        'pip',
        'wheel',
        # Otros innecesarios
        'xmlrpc',
        'pydoc',
        'pdb',
        'profile',
        'cProfile',
        'ftplib',
        'telnetlib',
        'imaplib',
        'poplib',
        'nntplib',
        'antigravity',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Reciva',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='logo_png/08-app-icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Reciva',
)

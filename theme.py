# Reciva — Design System Tokens
# Paleta "Recibo": cálida, seria, minimalista
# Todos los valores en formato Kivy (R, G, B, A) entre 0 y 1

VERMILLON = (0.914, 0.306, 0.173, 1)   # #E94E2C — acento primario, botones
LADRILLO  = (0.753, 0.227, 0.129, 1)   # #C03A21 — estados activos, degradados
CORAL     = (0.949, 0.447, 0.290, 1)   # #F2724A — acento sobre fondos oscuros
TINTA     = (0.106, 0.082, 0.071, 1)   # #1B1512 — texto principal, sidebar
BG        = (0.945, 0.918, 0.882, 1)   # #F1EAE1 — fondo de pantalla cálido
STAGE     = (0.984, 0.969, 0.945, 1)   # #FBF7F1 — superficie clara, filas alternas
CARD      = (1.000, 1.000, 1.000, 1)   # #FFFFFF — tarjetas
LINE      = (0.906, 0.863, 0.812, 1)   # #E7DCCF — bordes, separadores
MUTED     = (0.549, 0.502, 0.467, 1)   # #8C8077 — texto secundario
TEXT_SEC  = (0.353, 0.318, 0.290, 1)   # #5a514a — cuerpo secundario

# Sidebar
SIDEBAR_BG  = (0.106, 0.082, 0.071, 1)   # TINTA
SIDEBAR_HDR = (0.082, 0.063, 0.055, 1)   # ligeramente más oscuro
SIDEBAR_BTN = (0.145, 0.110, 0.094, 1)   # botones inactivos

# Funcionales (sobre fondos claros)
SUCCESS = (0.122, 0.533, 0.220, 1)   # verde — pagado, resuelto
WARNING = (0.800, 0.500, 0.050, 1)   # ámbar — mora leve, en proceso
DANGER  = VERMILLON                   # rojo — mora grave, abierto

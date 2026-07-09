[Setup]
AppName=Reciva
AppVersion=1.0.23
AppPublisher=INGESAM ASEO S.A.S E.S.P.
AppPublisherURL=https://ingesam.com.co
AppSupportURL=https://ingesam.com.co
DefaultDirName={autopf}\Reciva
DefaultGroupName=Reciva
OutputDir=installer
OutputBaseFilename=Reciva_Setup_v1.0.23
SetupIconFile=logo_png\08-app-icon.ico
UninstallDisplayIcon={app}\Reciva.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Iconos adicionales:"

[Files]
Source: "dist\Reciva\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Reciva";              Filename: "{app}\Reciva.exe"; WorkingDir: "{app}"
Name: "{group}\Desinstalar Reciva";  Filename: "{uninstallexe}"
Name: "{userdesktop}\Reciva";        Filename: "{app}\Reciva.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Dirs]
Name: "{userappdata}\Reciva"

[INI]
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "database"; Key: "host";  String: "gateway01.us-east-1.prod.aws.tidbcloud.com"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "database"; Key: "port";  String: "4000"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "database"; Key: "user";  String: "4882cNdDeK3wmj1.root"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "database"; Key: "pass";  String: "xfIReoIfFsIszl6l"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "database"; Key: "name";  String: "reciva_db"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "smtp";     Key: "host";  String: "smtp.gmail.com"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "smtp";     Key: "port";  String: "587"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "smtp";     Key: "user";  String: "pqringesamaseo@gmail.com"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "smtp";     Key: "pass";  String: "clpehtjjuzxbuwqk"
Filename: "{userappdata}\Reciva\reciva.ini"; Section: "app";      Key: "primer_uso"; String: "false"

[Run]
Filename: "{app}\Reciva.exe"; Description: "Iniciar Reciva ahora"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

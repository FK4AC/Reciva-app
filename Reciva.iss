[Setup]
AppName=Reciva
AppVersion=1.0.21
AppPublisher=INGESAM ASEO S.A.S E.S.P.
AppPublisherURL=https://ingesam.com.co
AppSupportURL=https://ingesam.com.co
DefaultDirName={autopf}\Reciva
DefaultGroupName=Reciva
OutputDir=installer
OutputBaseFilename=Reciva_Setup_v1.0.21
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

[Run]
Filename: "{app}\Reciva.exe"; Description: "Iniciar Reciva ahora"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

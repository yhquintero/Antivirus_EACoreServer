; ============================================
; Instalador Inno Setup para Antivirus EACoreServer
; Compilar con: ISCC.exe installer.iss
; ============================================

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}
AppName=Antivirus EACoreServer
AppVersion=1.1.0
DefaultDirName={pf}\Antivirus EACoreServer
DefaultGroupName=Antivirus EACoreServer
OutputDir=dist
OutputBaseFilename=Antivirus_EACoreServer_Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Antivirus_EACoreServer.exe
SetupIconFile=icono.ico
ChangesEnvironment=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "dist\Antivirus_EACoreServer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Antivirus EACoreServer"; Filename: "{app}\Antivirus_EACoreServer.exe"; Comment: "Protección contra malware USB"
Name: "{group}\Desinstalar Antivirus EACoreServer"; Filename: "{uninstallexe}"; Comment: "Desinstalar Antivirus EACoreServer"
Name: "{autodesktop}\Antivirus EACoreServer"; Filename: "{app}\Antivirus_EACoreServer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Antivirus_EACoreServer.exe"; Description: "Ejecutar Antivirus EACoreServer"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Antivirus_EACoreServer.exe"; Parameters: "/quit"; Flags: runhidden

[Registry]
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "InstallDir"; ValueString: "{app}"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "Version"; ValueString: "1.1.0"
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "Publisher"; ValueString: "EACoreServer Security"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if not IsAdminLoggedOn then
    begin
      MsgBox('Se requieren permisos de administrador para instalar esta aplicación.', mbError, MB_OK);
      CancelSetup();
    end;
  end;
end;

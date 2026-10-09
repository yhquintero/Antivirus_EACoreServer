; ============================================
; Instalador Inno Setup para Antivirus EACoreServer
; Compilar con: ISCC.exe installer.iss
;
; IMPORTANTE: El ejecutable dist\Antivirus_EACoreServer.exe debe haberse
; construido previamente con build.bat, que exige Python 3.8 de 32 bits.
; Sin este paso, el ejecutable falla en Windows 7 con el error:
;   "Falta api-ms-win-core-path-l1-1-0.dll en el equipo."
; ============================================

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}
AppName=Antivirus EACoreServer
AppVersion=1.2.0
AppPublisher=Yosvany Hernández Quintero
AppPublisherURL=https://github.com/yhquintero/Antivirus_EACoreServer
DefaultDirName={pf}\Antivirus EACoreServer
DefaultGroupName=Antivirus EACoreServer
OutputDir=dist
OutputBaseFilename=Antivirus_EACoreServer_Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Antivirus_EACoreServer.exe
SetupIconFile=icono.ico
ChangesEnvironment=no
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
; Requiere al menos Windows 7 (NT 6.1). El ejecutable no arranca en XP/Vista
; sin parches adicionales, y Python 3.8 es el mínimo soportado por la app.
MinVersion=6.1sp1
; Arquitectura objetivo: x86 (32 bits). Funciona tanto en Windows de 32 como
; de 64 bits, y es la única forma de compatibilizar con Windows 7/8.
ArchitecturesAllowed=x86 x64
ArchitecturesInstallModeIn64=x86

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "dist\Antivirus_EACoreServer.exe"; DestDir: "{app}"; Flags: ignoreversion
; Nota: si se usa el modo onefile de PyInstaller solo hay un ejecutable.
; Si se cambia a onedir, reemplace la línea anterior por:
;   Source: "dist\Antivirus_EACoreServer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Antivirus EACoreServer"; Filename: "{app}\Antivirus_EACoreServer.exe"; Comment: "Protección contra malware USB y gestión de procesos EACoreServer"
Name: "{group}\Desinstalar Antivirus EACoreServer"; Filename: "{uninstallexe}"; Comment: "Desinstalar Antivirus EACoreServer"
Name: "{autodesktop}\Antivirus EACoreServer"; Filename: "{app}\Antivirus_EACoreServer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Antivirus_EACoreServer.exe"; Description: "Ejecutar Antivirus EACoreServer"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Antivirus_EACoreServer.exe"; Parameters: "/quit"; Flags: runhidden

[Registry]
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "InstallDir"; ValueString: "{app}"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "Version"; ValueString: "1.2.0"
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "Publisher"; ValueString: "Yosvany Hernández Quintero"
Root: HKLM; Subkey: "SOFTWARE\AntivirusEACoreServer"; ValueType: string; ValueName: "PythonBuild"; ValueString: "3.8 x86 (compatible con Windows 7+)"

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

procedure InitializeWizard();
begin
  WizardForm.Bevel1.Visible := False;
  WizardForm.PageNameLabel.FontColor := clNavy;
  WizardForm.PageNameLabel.FontHeight := 12;
  WizardForm.PageNameLabel.FontStyle := [fsBold];
end;

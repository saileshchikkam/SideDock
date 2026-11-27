; SideDock v1.0 — per-user installer (Inno Setup 6)
; Never remove or migrate %USERPROFILE%\SideDockData in the installer/uninstaller.
#ifndef MyAppVersion
  #define MyAppVersion "1.0.1"
#endif

[Setup]
AppId=SideDock.saileshchikkam
AppName=SideDock
AppVersion={#MyAppVersion}
AppPublisher=Sailesh Chikkam
AppPublisherURL=https://github.com/saileshchikkam/SideDock
AppSupportURL=https://github.com/saileshchikkam/SideDock/issues
AppUpdatesURL=https://github.com/saileshchikkam/SideDock/releases
VersionInfoVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\SideDock
DefaultGroupName=SideDock
PrivilegesRequired=lowest
LicenseFile=..\LICENSE
SetupIconFile=..\build\release\SideDock.ico
UninstallDisplayIcon={app}\SideDock.exe
OutputDir=..\dist
OutputBaseFilename=SideDock-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start SideDock automatically when I sign in to Windows"; GroupDescription: "Windows startup:"

[Registry]
; Per-user sign-in startup checked by default (not before Windows login).
; On-disk PyInstaller runtime avoids re-extracting Qt and OCR at every logon.
; The app tray can disable or re-enable the same HKCU Run value at any time.
; Do not use uninsdeletevalue: the uninstall code checks the full path first.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SideDock"; ValueData: """{app}\SideDock.exe"""; Tasks: autostart

[Files]
Source: "..\dist\SideDock\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\SideDock"; Filename: "{app}\SideDock.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\SideDock"; Filename: "{app}\SideDock.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\SideDock.exe"; Description: "{cm:LaunchProgram,SideDock}"; Flags: nowait postinstall skipifsilent

[Code]
{ Only remove the autorun entry when it refers to THIS installed executable.
  Never delete SideDockData or other users' portable startup preferences. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Value: string;
  Executable: string;
  RunKey: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    Executable := ExpandConstant('{app}\SideDock.exe');
    RunKey := 'Software\Microsoft\Windows\CurrentVersion\Run';
    if RegQueryStringValue(HKCU, RunKey, 'SideDock', Value) then
    begin
      if (CompareText(Trim(Value), '"' + Executable + '"') = 0) or
         (CompareText(Trim(Value), Executable) = 0) then
        RegDeleteValue(HKCU, RunKey, 'SideDock');
    end;
  end;
end;

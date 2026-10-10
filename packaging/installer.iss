#define AppVersion "0.1.0"
[Setup]
AppId={{7D6D4689-A1CF-4ED3-A189-2078C598B382}
AppName=Study Desk
AppVersion={#AppVersion}
AppPublisher=Study Desk
DefaultDirName={localappdata}\Programs\StudyDesk
DefaultGroupName=Study Desk
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=StudyDesk-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\StudyDesk.exe
CloseApplications=yes

[Files]
Source: "..\dist\StudyDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Icons]
Name: "{group}\Study Desk"; Filename: "{app}\StudyDesk.exe"
Name: "{autodesktop}\Study Desk"; Filename: "{app}\StudyDesk.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StudyDesk.exe"; Description: "Launch Study Desk"; Flags: nowait postinstall skipifsilent

; User data in LocalAppData\StudyDesk is intentionally never deleted on uninstall.

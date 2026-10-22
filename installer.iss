; Installateur Inno Setup. Compilation : iscc /DAppVersion=1.0.0 installer.iss
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B7C1E2A4-5D3F-4B8A-9E61-3A7C0D1F5E22}
AppName=VLC Redesign
AppVersion={#AppVersion}
DefaultDirName={autopf}\VLC Redesign
DefaultGroupName=VLC Redesign
; Installation sans droits administrateur (nécessaire pour les mises à jour silencieuses)
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=VLC_Redesign_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\VLC Redesign.exe
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible
#ifexist "icon.ico"
SetupIconFile=icon.ico
#endif

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; Flags: unchecked

[Files]
Source: "dist\VLC Redesign\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VLC Redesign"; Filename: "{app}\VLC Redesign.exe"
Name: "{autodesktop}\VLC Redesign"; Filename: "{app}\VLC Redesign.exe"; Tasks: desktopicon

[Run]
; Sans « skipifsilent » : l'application se relance aussi après une mise à jour silencieuse
Filename: "{app}\VLC Redesign.exe"; Description: "Lancer VLC Redesign"; Flags: nowait postinstall

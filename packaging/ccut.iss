; Inno Setup — bộ cài C-Cut cho Windows (cài cho người dùng hiện tại, không cần quyền admin)
#define AppVer GetEnv("CCUT_VERSION")
#if AppVer == ""
  #define AppVer "1.1"
#endif
[Setup]
AppId={{6C2E3A41-9B7D-4F1E-A0C5-CC07C0C0C001}
AppName=C-Cut
AppVersion={#AppVer}
AppPublisher=C-Cut
DefaultDirName={localappdata}\Programs\C-Cut
DefaultGroupName=C-Cut
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=C-Cut-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\C-Cut.exe
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\build\pyi\C-Cut\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "guide\Huong dan su dung C-Cut.pdf"; DestDir: "{app}"

[Icons]
Name: "{group}\C-Cut"; Filename: "{app}\C-Cut.exe"
Name: "{group}\Hướng dẫn sử dụng"; Filename: "{app}\Huong dan su dung C-Cut.pdf"
Name: "{userdesktop}\C-Cut"; Filename: "{app}\C-Cut.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình"

[Run]
Filename: "{app}\C-Cut.exe"; Description: "Mở C-Cut"; Flags: nowait postinstall skipifsilent

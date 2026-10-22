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
CloseApplications=force
AppVerName=C-Cut {#AppVer}

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\build\pyi\C-Cut\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "guide\Huong dan su dung C-Cut.pdf"; DestDir: "{app}"

[Icons]
Name: "{group}\C-Cut"; Filename: "{app}\C-Cut.exe"; IconFilename: "{app}\C-Cut.exe"; AppUserModelID: "vn.ccut.app"
Name: "{group}\Hướng dẫn sử dụng"; Filename: "{app}\Huong dan su dung C-Cut.pdf"
Name: "{userdesktop}\C-Cut"; Filename: "{app}\C-Cut.exe"; IconFilename: "{app}\C-Cut.exe"; AppUserModelID: "vn.ccut.app"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình"

[Run]
; làm mới bộ nhớ đệm biểu tượng của Windows → thanh taskbar / lối tắt đã ghim hiện biểu tượng mới ngay sau khi cập nhật
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden waituntilterminated skipifdoesntexist
Filename: "{app}\C-Cut.exe"; Description: "Mở C-Cut"; Flags: nowait postinstall skipifsilent
Filename: "{app}\C-Cut.exe"; Flags: nowait skipifnotsilent

[Code]
{ tắt C-Cut và các tiến trình con còn chạy ngầm, để cài đè không bị khóa file }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var R: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM C-Cut.exe /IM ccut-py.exe', '', SW_HIDE, ewWaitUntilTerminated, R);
  Sleep(800);
  Result := '';
end;

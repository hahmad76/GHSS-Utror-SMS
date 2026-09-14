#define APP_ARCH "x86"
[Setup]
AppId={{A2C9DDA1-8E11-4F2B-9D40-GSMS10}}
AppName=GSMS SMS Software
AppVersion=1.0
AppPublisher=Govt. Higher Secondary School Utror Swat
DefaultDirName={autopf}\GSMS SMS Software
DefaultGroupName=GSMS SMS Software
OutputDir=dist\installer
OutputBaseFilename=GSMS_SMS_v1.0_Setup_x86
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern

[Files]
Source: "dist\GSMS_SMS_v1.0_Windows_7_10_11_x86.exe"; DestDir: "{app}"; DestName: "GSMS_SMS.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\GSMS SMS Software"; Filename: "{app}\GSMS_SMS.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\GSMS SMS Software"; Filename: "{app}\GSMS_SMS.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\GSMS_SMS.exe"; Description: "Launch GSMS SMS Software"; Flags: nowait postinstall skipifsilent

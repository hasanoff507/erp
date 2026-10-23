; ERP Do'kon agenti — Inno Setup 6 script (34 §4.2). Per-user, no admin rights (qaror #38).
; Built only by build-installer.ps1 on the signing PC (34 §2.5); never in CI with a private key.
; Defines passed by build-installer.ps1:  /DAppVersion=1.0.0 /DPublisher="<OV publisher>" /DBinDir=..\artifacts\bin

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Publisher
  #define Publisher "ERP"
#endif
#ifndef BinDir
  #define BinDir "..\artifacts\bin"
#endif

[Setup]
AppId={{6B2E1C34-0A7D-4E1B-9C55-3F0E8D2A1C11}
AppName=ERP 1C Agent
AppVersion={#AppVersion}
AppPublisher={#Publisher}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
DefaultDirName={userpf}\ErpOneCAgent
DisableDirPage=yes
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
MinVersion=6.1.7601
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
RestartApplications=no
SignTool=erpsign
SetupLogging=yes
OutputDir=..\artifacts\setup
OutputBaseFilename=erp-onec-agent-{#AppVersion}-setup
UninstallDisplayIcon={app}\ErpOneCAgent.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BinDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs; Excludes: "*.pdb,*.xml"

[Icons]
Name: "{userprograms}\ERP 1C Agent"; Filename: "{app}\ErpOneCAgent.exe"
Name: "{userdesktop}\ERP 1C Agent"; Filename: "{app}\ErpOneCAgent.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "ErpOneCAgent"; ValueData: """{app}\ErpOneCAgent.exe"" --hidden"; \
  Flags: uninsdeletevalue; Check: IsFirstInstall

[Run]
Filename: "{app}\ErpOneCAgent.exe"; Parameters: "{code:RunArgs}"; Flags: nowait; Check: ShouldStartAgent

[UninstallRun]
Filename: "{app}\ErpOneCAgent.exe"; Parameters: "--uninstall-hook {code:KeepArg}"; Flags: runhidden waituntilterminated; RunOnceId: "unpair"

[Code]
var
  FirstInstall: Boolean;
  KeepSettings: Boolean;

function IsDotNet48Installed(): Boolean;
var
  Release: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Release) and (Release >= 528040);
end;

function HasParam(const Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Name) = 0 then
      Result := True;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  Exe: String;
  Waited: Integer;
begin
  Result := True;
  if not IsDotNet48Installed() then
  begin
    SuppressibleMsgBox('.NET Framework 4.8 kerak / требуется .NET Framework 4.8:' + #13#10 +
      'https://dotnet.microsoft.com/download/dotnet-framework/net48', mbCriticalError, MB_OK, IDOK);
    Result := False;
    exit;
  end;
  FirstInstall := not FileExists(ExpandConstant('{userpf}\ErpOneCAgent\ErpOneCAgent.exe'));
  { 34 §3.7 / §4.2: ask a running agent to exit (Local\ErpOneCAgent-Exit-<SID>) through its own --shutdown }
  Exe := ExpandConstant('{userpf}\ErpOneCAgent\ErpOneCAgent.exe');
  if FileExists(Exe) then
  begin
    Exec(Exe, '--shutdown', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Waited := 0;
    while CheckForMutexes('Local\ErpOneCAgent-Running') and (Waited < 60) do
    begin
      Sleep(1000);
      Waited := Waited + 1;
    end;
    if CheckForMutexes('Local\ErpOneCAgent-Running') then
    begin
      if WizardSilent() then
        Result := False { the update waits for the next idle moment (34 §4.2) }
      else
        SuppressibleMsgBox('ERP agentini yoping / Закройте ERP агент', mbInformation, MB_OK, IDOK);
    end;
  end;
end;

function IsFirstInstall(): Boolean;
begin
  { an update does not re-enable the autostart the user switched off }
  Result := FirstInstall;
end;

function ShouldStartAgent(): Boolean;
begin
  Result := (not WizardSilent()) or HasParam('/restart');
end;

function RunArgs(Param: String): String;
begin
  if HasParam('/hidden') then
    Result := '--hidden --after-update'
  else if WizardSilent() then
    Result := '--after-update'
  else
    Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  KeepSettings := True;
  if not UninstallSilent() then
    KeepSettings := MsgBox('Sozlamalar (qurilmalar ro''yxati) saqlansinmi? Qayta o''rnatilsa kompyuterni baribir qayta ulash kerak bo''ladi.' + #13#10 +
      'Сохранить настройки (список оборудования)? При переустановке компьютер всё равно нужно будет подключить заново.',
      mbConfirmation, MB_YESNO) = IDYES;
end;

function KeepArg(Param: String): String;
begin
  if KeepSettings then
    Result := '--keep-settings'
  else
    Result := '';
end;

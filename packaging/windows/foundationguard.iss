; The Windows download (AI-made, Claude, 2026-11-19; beta gate line 4: the beta does not need a Python install).
; One normal download the owner opens. It installs for this user only, with no administrator question, into
; %LOCALAPPDATA%\FoundationGuard: python\ (python.org's small Python, unchanged), fg\ (the kit) and the guides.
; Built from build\stage (packaging/windows/build.py) by the "windows-download" job; unsigned in the beta, so Windows
; shows "Windows protected your PC" first ("More info", then "Run anyway").

#define AppVer GetEnv("FG_VERSION")
#if AppVer == ""
  #define AppVer "beta"
#endif

[Setup]
AppId={{6E0B8C4E-5C1D-4E7B-9B5A-F0D1A7C3B2E1}
AppName=FoundationGuard
AppVersion={#AppVer}
AppPublisher=FoundationGuard
DefaultDirName={localappdata}\FoundationGuard
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\..\build
OutputBaseFilename=FoundationGuard-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=FoundationGuard (safety checks for AI helpers)

[Files]
Source: "..\..\build\stage\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\FoundationGuard - the sentence for your AI helper"; Filename: "{app}\PASTE_TO_YOUR_HELPER.txt"

[UninstallDelete]
Type: files; Name: "{app}\PASTE_TO_YOUR_HELPER.txt"
Type: filesandordirs; Name: "{app}\fg\__pycache__"

[Code]
var
  HelperPage: TWizardPage;
  HelperMemo: TNewMemo;
  CopyButton: TNewButton;
  CopiedLabel: TNewStaticText;

function Sentence(): String;
var
  App: String;
begin
  App := ExpandConstant('{app}');
  Result := 'Set up FoundationGuard on my project. First read "' + App + '\AGENT_SETUP.md" and follow it. ' +
            'Wherever it says python, use "' + App + '\python\python.exe", and wherever it says fg/setup.py, use "' +
            App + '\fg\setup.py", run from my project''s top folder.';
end;

function SentenceFile(): String;
begin
  Result := ExpandConstant('{app}\PASTE_TO_YOUR_HELPER.txt');
end;

procedure CopyClick(Sender: TObject);
var
  Path: String;
  Code: Integer;
begin
  Path := SentenceFile();
  StringChangeEx(Path, '''', '''''', True);
  if Exec('powershell.exe', '-NoProfile -NonInteractive -Command "Get-Content -Raw -Encoding UTF8 -LiteralPath ''' + Path +
          ''' | Set-Clipboard"', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0) then
    CopiedLabel.Caption := 'Copied. Paste it into your AI helper''s chat.'
  else
    CopiedLabel.Caption := 'Could not copy it. Select the sentence above and press Ctrl+C.';
end;

procedure InitializeWizard();
begin
  HelperPage := CreateCustomPage(wpInfoAfter, 'One sentence for your AI helper',
    'Open your AI helper in your project''s folder and paste this sentence. The helper does the rest.');
  HelperMemo := TNewMemo.Create(HelperPage);
  HelperMemo.Parent := HelperPage.Surface;
  HelperMemo.Left := 0;
  HelperMemo.Top := 0;
  HelperMemo.Width := HelperPage.SurfaceWidth;
  HelperMemo.Height := ScaleY(120);
  HelperMemo.ReadOnly := True;
  HelperMemo.WordWrap := True;
  HelperMemo.ScrollBars := ssVertical;
  CopyButton := TNewButton.Create(HelperPage);
  CopyButton.Parent := HelperPage.Surface;
  CopyButton.Left := 0;
  CopyButton.Top := HelperMemo.Top + HelperMemo.Height + ScaleY(10);
  CopyButton.Width := ScaleX(140);
  CopyButton.Height := ScaleY(26);
  CopyButton.Caption := 'Copy the sentence';
  CopyButton.OnClick := @CopyClick;
  CopiedLabel := TNewStaticText.Create(HelperPage);
  CopiedLabel.Parent := HelperPage.Surface;
  CopiedLabel.Left := CopyButton.Width + ScaleX(12);
  CopiedLabel.Top := CopyButton.Top + ScaleY(6);
  CopiedLabel.Caption := 'It is also kept in the Start menu, under FoundationGuard.';
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = HelperPage.ID then
    HelperMemo.Text := Sentence();
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringsToUTF8File(SentenceFile(), [Sentence()], False);
end;

function InitializeUninstall(): Boolean;
begin
  Result := SuppressibleMsgBox('Every project you set up with FoundationGuard calls the Python in this folder. ' +
    'If you remove it, the safety checks in those projects stop running, and nothing will tell you. ' +
    'To take the kit out of a project properly, see "Removing the kit" in docs\GUIDE.md first.' + #13#10 + #13#10 +
    'Remove FoundationGuard from this computer anyway?', mbConfirmation, MB_YESNO, IDYES) = IDYES;
end;

# flowmaker 설치 — 아무것도 없는 윈도우에서 이 한 줄이면 끝난다.
#
# ★이 파일은 반드시 **UTF-8 BOM** 으로 저장한다. 윈도우 기본 PowerShell 5.1 은 BOM 이 없으면
#   .ps1 을 ANSI(한국어 = cp949)로 읽어 한글 주석이 깨지고 구문 오류로 죽는다(실측).
#   powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
# 파이썬이 없으면 winget 으로 깔고, 그다음 `python -m flowmaker setup` 에 넘긴다
# (가상환경·파이썬 패키지·크로미엄·ffmpeg·.env·자막 폰트는 setup 이 맡는다).
#
# 윈도우에서 "파이썬 찾기"는 생각보다 까다롭다 — 실측으로 확인한 함정들:
#   · WindowsApps 의 python.exe 가 0바이트짜리 앱 실행 별칭일 수 있다(스토어만 열린다)
#   · `py -3` 이 아무 말 없이 끝나는 런처가 있다
# 그래서 후보를 "실제로 실행해 버전을 찍어보고" 고른다.
$ErrorActionPreference = "Continue"

# PowerShell 이 직접 찍는 줄도 utf-8 로 — 안 하면 출력을 파일·파이프로 받을 때(에이전트가
# 결과를 읽는 방식) 한글이 cp949 로 나가 깨진다. 파이썬 쪽은 setup 이 따로 고정한다.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }
$OutputEncoding = New-Object System.Text.UTF8Encoding $false

$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $repo

function Get-PyVersion([string]$exe, [string[]]$pre) {
  try {
    $a = @()
    if ($pre) { $a += $pre }
    $a += @("-c", "import sys;print('%d.%d' % sys.version_info[:2])")
    $out = & $exe @a 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    $v = ($out | Select-Object -Last 1).ToString().Trim()
    if ($v -match '^(\d+)\.(\d+)$') {
      if ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 10)) {
        return @{ Exe = $exe; Pre = $pre; Ver = $v }
      }
    }
  } catch { }
  return $null
}

function Find-Python {
  $cands = @()
  $cands += ,@("$repo\.venv\Scripts\python.exe", @())          # 이미 만들어 둔 가상환경
  foreach ($v in @("3.14","3.13","3.12","3.11","3.10")) { $cands += ,@("py", @("-$v")) }
  $cands += ,@("py", @("-3"))
  $cands += ,@("python", @())
  $cands += ,@("python3", @())
  foreach ($g in @("$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
                   "$env:LOCALAPPDATA\Python\pythoncore-*\python.exe",
                   "$env:ProgramFiles\Python3*\python.exe")) {
    foreach ($f in (Get-Item $g -ErrorAction SilentlyContinue)) { $cands += ,@($f.FullName, @()) }
  }
  foreach ($c in $cands) {
    $exe = $c[0]
    if ($exe -notmatch '^(py|python|python3)$' -and -not (Test-Path $exe)) { continue }
    if ($exe -match '^(py|python|python3)$' -and -not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $hit = Get-PyVersion $exe $c[1]
    if ($hit) { return $hit }
  }
  return $null
}

function Add-PythonPaths {
  # 방금 깐 파이썬은 이미 떠 있는 셸의 PATH 에 없다 — 흔한 설치 위치를 붙여 준다
  $extra = @("$env:LOCALAPPDATA\Microsoft\WindowsApps",
             "$env:LOCALAPPDATA\Programs\Python\Launcher")
  foreach ($g in @("$env:LOCALAPPDATA\Programs\Python\Python3*",
                   "$env:LOCALAPPDATA\Python\pythoncore-*")) {
    foreach ($d in (Get-Item $g -ErrorAction SilentlyContinue)) {
      $extra += $d.FullName; $extra += "$($d.FullName)\Scripts"
    }
  }
  foreach ($d in $extra) {
    if ((Test-Path $d) -and ($env:PATH -split ';') -notcontains $d) { $env:PATH += ";$d" }
  }
}

Write-Host "flowmaker 설치 — 파이썬을 찾는 중"
$py = Find-Python

if (-not $py) {
  Write-Host "파이썬 3.10 이상이 없다 — winget 으로 먼저 깐다"
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget 이 없다. https://www.python.org/downloads/ 에서 파이썬을 받고"
    Write-Host "설치할 때 'Add python.exe to PATH' 를 켠 뒤 이 스크립트를 다시 실행하라."
    exit 1
  }
  Write-Host "  `$ winget install --id Python.Python.3.13 -e --scope user"
  & winget install --id Python.Python.3.13 -e --source winget `
      --accept-package-agreements --accept-source-agreements --scope user
  Add-PythonPaths
  $py = Find-Python
  if (-not $py) {
    Write-Host ""
    Write-Host "파이썬을 깔았는데도 못 찾겠다 — **새 터미널(PowerShell)을 열고** 다시 실행하라."
    Write-Host "(설치 직후에는 PATH 가 지금 창에 반영되지 않는다)"
    exit 1
  }
}

$shown = $py.Exe; if ($py.Pre) { $shown += " " + ($py.Pre -join " ") }
Write-Host "파이썬: $shown (버전 $($py.Ver))"
Write-Host ""

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$args2 = @()
if ($py.Pre) { $args2 += $py.Pre }
$args2 += @("-m", "flowmaker", "setup")
if ($args) { $args2 += $args }
& $py.Exe @args2
exit $LASTEXITCODE

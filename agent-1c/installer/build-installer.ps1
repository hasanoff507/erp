<#
.SYNOPSIS
  Builds the signed ERP Do'kon agenti setup (34 §2.5 steps 1-4). Runs ONLY on the signing PC (OV certificate on a
  hardware token / CA cloud signing, 26 #105) - never in CI. The update manifest is signed separately with the
  offline agent_update root key (step 5, erp1c-release; 33 §9.4).

.EXAMPLE
  .\build-installer.ps1 -Version 1.0.0 -Channel stable -ServerBase https://erp.example.uz `
      -AppOrigins https://app.erp.example.uz -Publisher "Example MChJ" -SignCommand 'signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /n "Example MChJ" $f'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
    [ValidateSet('pilot', 'stable')][string]$Channel = 'pilot',
    [Parameter(Mandatory = $true)][ValidatePattern('^https://')][string]$ServerBase,
    [Parameter(Mandatory = $true)][ValidatePattern('^https://')][string]$AppOrigins,
    [string]$LocalPorts = '47110',
    [Parameter(Mandatory = $true)][string]$Publisher,
    [Parameter(Mandatory = $true)][string]$SignCommand,
    [string]$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$bin = Join-Path $root 'artifacts\bin'

# 1. Release build + unit tests (no DEV build is ever shipped: AgentChannel != dev disables --server and fakes).
dotnet test (Join-Path $root 'ErpOneCAgent.sln') -c Release
if ($LASTEXITCODE -ne 0) { throw 'tests failed' }
if (Test-Path $bin) { Remove-Item -Recurse -Force $bin }
dotnet publish (Join-Path $root 'src\Erp1C.Agent\Erp1C.Agent.csproj') -c Release -o $bin `
    -p:AgentVersion=$Version -p:AgentChannel=$Channel -p:AgentServerBase=$ServerBase `
    -p:AgentAppOrigins=$AppOrigins -p:AgentLocalPorts=$LocalPorts -p:AgentPublisher="$Publisher" -p:ContinuousIntegrationBuild=true
if ($LASTEXITCODE -ne 0) { throw 'publish failed' }

# 2. Authenticode: our exe/dll and unsigned third-party DLLs (RFC 3161 timestamp in the sign command).
Get-ChildItem $bin -Include *.exe, *.dll -Recurse | ForEach-Object {
    $sig = Get-AuthenticodeSignature $_.FullName
    if ($sig.Status -ne 'Valid') {
        $f = '"' + $_.FullName + '"'
        Invoke-Expression ($SignCommand -replace '\$f', $f)
        if ($LASTEXITCODE -ne 0) { throw "signing failed: $($_.Name)" }
    }
}

# 3. Installer (Inno SignTool=erpsign signs setup and unins000.exe).
& $Iscc "/DAppVersion=$Version" "/DPublisher=$Publisher" "/DBinDir=$bin" "/Serpsign=$($SignCommand -replace '\$f', '$f')" (Join-Path $PSScriptRoot 'ErpOneCAgent.iss')
if ($LASTEXITCODE -ne 0) { throw 'ISCC failed' }

# 4. Verify every signature and the publisher name.
$setup = Join-Path $root "artifacts\setup\erp-onec-agent-$Version-setup.exe"
Get-ChildItem $bin -Include *.exe, *.dll -Recurse | ForEach-Object { $_.FullName } | ForEach-Object {
    $s = Get-AuthenticodeSignature $_
    if ($s.Status -ne 'Valid') { throw "not signed: $_" }
}
$s = Get-AuthenticodeSignature $setup
if ($s.Status -ne 'Valid' -or $s.SignerCertificate.GetNameInfo('SimpleName', $false) -ne $Publisher) { throw 'setup signature / publisher mismatch' }

$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "setup: $setup"
Write-Host "size:  $((Get-Item $setup).Length)"
Write-Host "sha256: $hash   (sign the manifest offline with the agent_update root key - 34 §2.5 step 5)"

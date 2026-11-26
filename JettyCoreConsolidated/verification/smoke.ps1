param(
    [Parameter(Mandatory)]
    [string] $Maven,

    [Parameter(Mandatory)]
    [string] $Jdk,

    [Parameter(Mandatory)]
    [string] $Repository,

    [switch] $Offline
)
$ErrorActionPreference = 'Stop'
$Maven = (Get-Item -LiteralPath $Maven).FullName
$Jdk = (Get-Item -LiteralPath $Jdk).FullName
$Repository = (Get-Item -LiteralPath $Repository).FullName
$work = Join-Path ([IO.Path]::GetTempPath()) ('jetty-consumer-' + [Guid]::NewGuid().ToString('N'))
$java = Join-Path $work 'src/main/java/verification'
New-Item -ItemType Directory -Path $java -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'templates/consumer-pom.xml') -Destination (Join-Path $work 'pom.xml')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'templates/ConsumerSmoke.java') -Destination $java

$keys = 'JAVA_HOME','Path','JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','MAVEN_ARGS'
$previous = @{}
foreach ($key in $keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}
Push-Location -LiteralPath $work
try {
    $env:JAVA_HOME = $Jdk
    $env:Path = "$(Join-Path $Jdk 'bin');$($previous['Path'])"
    foreach ($key in 'JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','MAVEN_ARGS') {
        [Environment]::SetEnvironmentVariable($key, $null, 'Process')
    }
    & (Join-Path $Jdk 'bin/keytool.exe') -genkeypair -alias localhost -keyalg RSA -keysize 2048 -validity 10 -storetype PKCS12 -keystore (Join-Path $work 'localhost.p12') -storepass fixture-password -dname 'CN=localhost' -ext 'SAN=dns:localhost,ip:127.0.0.1'
    if ($LASTEXITCODE -ne 0) { throw "keytool terminó con $LASTEXITCODE" }
    $options = @('-B', '-ntp', "-Dmaven.repo.local=$Repository")
    if ($Offline) { $options += '-o' }
    & $Maven @options verify org.apache.maven.plugins:maven-dependency-plugin:3.10.0:tree
    if ($LASTEXITCODE -ne 0) { throw "Maven terminó con $LASTEXITCODE" }
    Write-Output "Consumidor independiente en $work"
}
finally {
    Pop-Location
    foreach ($key in $keys) {
        [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
    }
}

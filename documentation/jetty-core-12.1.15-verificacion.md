# Reproducción de las pruebas de Jetty Core 12.1.15 para SecurityAuth

Esta guía corresponde al tag `jetty-12.1.15` y al commit `770f5e4d1c39673d6356163118a1e6bf1117ced3`. La carpeta `Jetty` contiene el checkout `JettyCore12.1.15`. La raíz Maven y Git es `Jetty/JettyCore12.1.15`, donde está [pom.xml](../pom.xml). Los comandos y rutas de módulos parten de esa raíz o de una copia de ella. La prueba se hace en una copia limpia con repositorio Maven propio para conservar el checkout y los informes anteriores.

- [Preparar el reactor](#preparar-una-copia-limpia)
- [Corrida inicial con JDK 17](#corrida-inicial-con-jdk-17)
- [Corrida focalizada de hilos virtuales con JDK 21](#corrida-focalizada-de-hilos-virtuales-con-jdk-21)
- [Incidentes y comprobaciones](#incidentes-y-comprobaciones)
- [Repetir una selección de diagnóstico](#repetir-una-selección-de-diagnóstico-con-jdk-17)
- [Apéndice con selectores, planes y diffs](#apéndice-de-reproducción)

## Requisitos

| Grupo | Entorno y configuración |
|---|---|
| Reactor Core y diagnósticos originales | Windows x64 con Oracle JDK 17.0.11 y Maven 3.9.12 en las corridas registradas. El Enforcer del [POM raíz](../pom.xml) admite Maven desde 3.9.2 y JDK desde 17. Se requiere acceso de lectura a JAR, escritura bajo `target/` y conexiones loopback entre los clientes y servidores de prueba. |
| Hilos virtuales en Windows | Microsoft OpenJDK 21.0.13.1+2 x64 y Maven 3.9.12. Se conserva la compilación de las fuentes ordinarias con `--release 17`. El proceso de Maven y el fork de Surefire usan Java 21. |
| Tres variantes `H3_QUICHE` pendientes | Linux con JDK 21, Maven 3.9.12, Quiche/JNA compatible con la arquitectura y UDP loopback. [AbstractTest.transports()](../jetty-core/jetty-tests/jetty-test-client-transports/src/test/java/org/eclipse/jetty/test/client/transport/AbstractTest.java) quita `H3_QUICHE` en Windows antes de crear los parámetros. |
| Perfil `enable-foreign` | El [POM de transportes](../jetty-core/jetty-tests/jetty-test-client-transports/pom.xml), el [POM de RFC](../jetty-core/jetty-tests/jetty-test-rfc/pom.xml) y la rama de Quiche activan FFM en `[22,)`. Los perfiles JNA se activan en `[17,22)`. Para validar FFM se requiere JDK 22 o superior, el proveedor nativo compatible y un reactor que incluya sus fuentes. Esa validación quedó fuera de las corridas de esta guía. |

Para un checkout desde cero también se necesitan Git, el Maven indicado y acceso a los repositorios de dependencias durante la primera descarga. Los comandos Windows usan PowerShell y Python 3 para la copia y el resumen de XML. Las corridas de JDK 21 se verificaron con un token Windows normal (`administrador=False`).

## Preparar una copia limpia

Desde `Jetty`, entra en el checkout existente. Si falta, la línea comentada muestra cómo reconstruirlo con los archivos del tag oficial. Un checkout parcial necesita las fuentes, POM, recursos y pruebas de las dependencias que `-am` agrega. Un POM presente permite descubrir el módulo, pero puede terminar en `No sources to compile` si faltan los blobs de fuentes.

```powershell
# Desde Jetty, solo si falta el checkout:
# git clone --filter=blob:none --single-branch --branch jetty-12.1.15 https://github.com/jetty/jetty.project.git JettyCore12.1.15

Set-Location -LiteralPath .\JettyCore12.1.15
$commit = '770f5e4d1c39673d6356163118a1e6bf1117ced3'
$original = (Get-Location).Path
$actual = git rev-parse HEAD
$tag = git rev-parse 'jetty-12.1.15^{commit}'
if ($actual -ne $commit -or $tag -ne $commit -or !(Test-Path -LiteralPath .\pom.xml)) {
    throw 'La raíz o la revisión del checkout no coincide'
}
if (git status --porcelain --untracked-files=no) { throw 'Hay archivos versionados modificados' }
$work = Join-Path $env:LOCALAPPDATA ('jcv-770f5e4-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$repo = Join-Path $work 'm2'
$src = Join-Path $work 'jdk17-src'
$src21 = Join-Path $work 'jdk21-src'
New-Item -ItemType Directory -Path $work,$repo | Out-Null

function Copy-Reactor([string]$target) {
    if (Test-Path -LiteralPath $target) { throw 'La copia debe empezar sin resultados previos' }
    python -c 'import shutil,sys; shutil.copytree(sys.argv[1],sys.argv[2],ignore=shutil.ignore_patterns("target"))' $original $target
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo copiar el reactor' }
    $copiedCommit = git -C $target rev-parse HEAD
    if ($copiedCommit -ne $commit -or (git -C $target status --porcelain --untracked-files=no)) {
        throw 'La copia no coincide con la revisión limpia'
    }
}
Copy-Reactor $src

# Indicar las rutas locales. Ninguna se incorpora al PATH permanente.
$mvn = (Get-Command mvn.cmd -ErrorAction Stop).Source
$jdk17 = 'C:\Program Files\Java\jdk-17'
# Si Maven está en una extracción independiente, usar su ruta a bin\mvn.cmd.
```

Si Git rechaza la propiedad de una copia, confirma la ruta y el propietario antes de añadir la excepción `safe.directory` solo al comando o al entorno de ese proceso. Repite la verificación de `HEAD`, del tag y de los cambios versionados. Para cada reintento crea una copia nueva. El repositorio Maven `$repo` puede reutilizarse dentro del mismo conjunto de corridas y se verifica que no contenga artefactos Jetty 12.1.15 instalados.

### JDK 21 portátil en Windows

Reutiliza un JDK 21 instalado si existe. Para reproducir el binario verificado, descarga el ZIP de la [distribución oficial de Microsoft](https://learn.microsoft.com/en-us/java/openjdk/download). El bloque guarda el ZIP y el JDK en una carpeta del usuario y coteja el SHA-256 publicado y el registrado en la corrida.

```powershell
$jdkDir = Join-Path $env:LOCALAPPDATA 'jdks\jetty-openjdk-21.0.13.1'
New-Item -ItemType Directory -Path $jdkDir -Force | Out-Null
$uri = 'https://aka.ms/download-jdk/microsoft-jdk-21.0.13.1-windows-x64.zip'
$zip = Join-Path $jdkDir 'jdk.zip'
$sha = Join-Path $jdkDir 'jdk.sha256.txt'
curl.exe --fail --location --output $zip $uri
if ($LASTEXITCODE -ne 0) { throw 'Falló la descarga del JDK' }
curl.exe --fail --location --output $sha "$uri.sha256sum.txt"
if ($LASTEXITCODE -ne 0) { throw 'Falló la descarga del SHA-256' }
$published = [regex]::Match((Get-Content -LiteralPath $sha -Raw), '[0-9a-fA-F]{64}').Value
$actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
if ($actual -ne $published -or $actual -ne '071C10E8E7FA62CFEF83137B152F5F40E37012DD48E4D5586C5125667CF0B8DE') {
    throw 'El SHA-256 del JDK no coincide'
}
Expand-Archive -LiteralPath $zip -DestinationPath $jdkDir
$jdk21 = Join-Path $jdkDir 'jdk-21.0.13.1+2'
& (Join-Path $jdk21 'bin\java.exe') -version
```

### Reactor compartido

Los primeros 14 elementos son los módulos seleccionados. Los restantes agregan el BOM, JMX, las seis suites y recursos. Maven incluye las dependencias transitivas con `-am`, incluidos los auxiliares de cliente, ALPN y los módulos que necesita la suite de transportes. El reactor original y el de JDK 21 tuvieron 68 proyectos.

```powershell
$core14 = @(
    'jetty-core/jetty-server'
    'jetty-core/jetty-http'
    'jetty-core/jetty-io'
    'jetty-core/jetty-util'
    'jetty-core/jetty-alpn/jetty-alpn-server'
    'jetty-core/jetty-alpn/jetty-alpn-java-server'
    'jetty-core/jetty-http2/jetty-http2-server'
    'jetty-core/jetty-http2/jetty-http2-common'
    'jetty-core/jetty-http2/jetty-http2-hpack'
    'jetty-core/jetty-security'
    'jetty-core/jetty-rewrite'
    'jetty-core/jetty-compression/jetty-compression-server'
    'jetty-core/jetty-compression/jetty-compression-common'
    'jetty-core/jetty-compression/jetty-compression-gzip'
)
$modules = ($core14 + @(
    'jetty-core/jetty-bom'
    'jetty-core/jetty-jmx'
    'jetty-core/jetty-http2/jetty-http2-tests'
    'jetty-core/jetty-compression/jetty-compression-tests'
    'jetty-core/jetty-tests/jetty-test-client-transports'
    'jetty-core/jetty-tests/jetty-test-rfc'
    'jetty-core/jetty-tests/jetty-test-jmx'
    'tests/test-integration'
    'tests/jetty-test-multipart'
    'build/build-resources'
)) -join ','
$common = @(
    '-B', '-ntp', '-fae', '-am', "-Dmaven.repo.local=$repo",
    '-Dmaven.build.cache.enabled=false', '-Dspotless.skip=true', '-Dcheckstyle.skip=true'
)
$forkBase = '-Dfile.encoding=UTF-8 -Duser.language=en -Duser.region=US'

# Guarda y repone el entorno del proceso, incluso al fallar Maven.
function Invoke-JettyVerify([string]$checkout, [string]$jdk, [string]$heapMaven,
    [string]$log, [string[]]$mavenArgs) {
    $keys = 'JAVA_HOME','Path','MAVEN_OPTS','MAVEN_SKIP_RC','MAVEN_ARGS',
            'JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','TEMP','TMP'
    $before = @{}
    foreach ($key in $keys) { $before[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
    Push-Location -LiteralPath $checkout
    try {
        $env:JAVA_HOME = $jdk
        $env:Path = "$(Join-Path $jdk 'bin');$($before['Path'])"
        $env:MAVEN_OPTS = $heapMaven
        $env:MAVEN_SKIP_RC = 'true'
        foreach ($key in 'MAVEN_ARGS','JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS') {
            [Environment]::SetEnvironmentVariable($key, $null, 'Process')
        }
        $forkTemp = Join-Path $work ('runtime-' + [IO.Path]::GetFileNameWithoutExtension($log))
        New-Item -ItemType Directory -Path $forkTemp -Force | Out-Null
        $env:TEMP = $forkTemp
        $env:TMP = $forkTemp
        java -version 2>&1 | Tee-Object -FilePath "$log.versions.txt"
        & $mvn -version 2>&1 | Tee-Object -FilePath "$log.versions.txt" -Append
        $mavenArgs | ConvertTo-Json | Set-Content -LiteralPath "$log.args.json" -Encoding utf8
        & $mvn @mavenArgs 2>&1 | Tee-Object -FilePath $log
        $code = $LASTEXITCODE
        $code | Set-Content -LiteralPath "$log.exit-code"
        "Maven exit code $code"
    }
    finally {
        Pop-Location
        foreach ($key in $keys) {
            [Environment]::SetEnvironmentVariable($key, $before[$key], 'Process')
        }
    }
}
```

## Corrida inicial con JDK 17

Ejecuta una sola vez el ciclo hasta `verify`. La corrida inicial eligió los perfiles por defecto. En Java 17, JNA queda activo en las suites que lo usan y FFM queda fuera. `maven.test.failure.ignore` se usó para recoger resultados de todo el reactor. Por eso el código de Maven y el resultado de las pruebas se registran por separado.

```powershell
$log17 = Join-Path $work 'jdk17-verify.log'
$args17 = $common + @(
    '-pl', $modules, '-Dmaven.test.failure.ignore=true',
    "-Djetty.surefire.argLine=$forkBase -Xms64m -Xmx768m", 'verify'
)
Invoke-JettyVerify $src $jdk17 '-Xms64m -Xmx640m' $log17 $args17
```

Resultado registrado en Windows con JDK 17.0.11: Maven `0` y `19 192` entradas en XML, con **18 905 aprobadas, 15 fallos, 3 errores y 269 omitidas**. Los 36 casos de cliente que quedaron sin XML por agotamiento de heap se inventariaron aparte. Las omisiones registradas incluyen condiciones de JUnit por sistema operativo y JDK, pruebas deshabilitadas en el código y supuestos de plataforma o transporte. Las 269 no incluyen ni el perfil FFM inactivo ni las exclusiones de corridas focalizadas.

Surefire anotó `Disabled on JRE version: 17.0.11` en seis métodos de `VirtualThreadPoolTest`, uno de `QoSHandlerTest` y tres métodos parametrizados de `VirtualThreadsTest`. Esos tres métodos se omitieron antes de expandirse. `ExecutionStrategyTest.pooledStrategies()` filtró `VirtualThreadPool` en JDK 17, por lo que sus doce invocaciones virtuales tampoco aparecen como filas omitidas.

## Corrida focalizada de hilos virtuales con JDK 21

Reutiliza `$repo` después de la corrida JDK 17. El JDK 21 no sustituye al JDK del sistema. [VirtualThreadPoolTest](../jetty-core/jetty-util/src/test/java/org/eclipse/jetty/util/thread/VirtualThreadPoolTest.java) y [QoSHandlerTest](../jetty-core/jetty-server/src/test/java/org/eclipse/jetty/server/handler/QoSHandlerTest.java) excluyen hasta Java 20. [VirtualThreadsTest](../jetty-core/jetty-tests/jetty-test-client-transports/src/test/java/org/eclipse/jetty/test/client/transport/VirtualThreadsTest.java) excluye hasta Java 18. Java 21 permite ejecutar los tres grupos sin preview.

### Recrear el selector temporal

En [ExecutionStrategyTest.pooledStrategies()](../jetty-core/jetty-util/src/test/java/org/eclipse/jetty/util/thread/strategy/ExecutionStrategyTest.java), cada uno de los cuatro métodos produce tres estrategias por pool. En este commit los índices `1–6` corresponden a los pools de plataforma ya probados, y `7–9` a `VirtualThreadPool`. La extensión JUnit que se incluye en el apéndice deshabilita únicamente los seis primeros índices de esa clase. La carga automática de extensiones está habilitada en el POM raíz.

Copia el primer bloque Java del apéndice a `$work\VirtualInvocationSelection.java` en UTF-8 y compílalo con el JDK 21. El descriptor del servicio permite a JUnit descubrirlo en el fork. El repositorio Maven de la línea base ya contiene ambos JAR. Si empiezas con un repositorio vacío, descárgalos desde Maven Central en las rutas esperadas por el bloque. La primera pasada del reactor necesita acceso a sus propias dependencias.

Con un repositorio vacío, ejecuta primero este bloque desde la misma sesión. Con ambos JAR presentes, continúa con la compilación del selector.

```powershell
$dependencies = @{
    'org/junit/jupiter/junit-jupiter-api/6.1.3/junit-jupiter-api-6.1.3.jar' = 'junit-jupiter-api'
    'org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar' = 'apiguardian-api'
}
foreach ($relative in $dependencies.Keys) {
    $artifact = Join-Path $repo $relative
    if (!(Test-Path -LiteralPath $artifact)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $artifact) -Force | Out-Null
        curl.exe --fail --location --output $artifact "https://repo.maven.apache.org/maven2/$relative"
        if ($LASTEXITCODE -ne 0) { throw "No se pudo recuperar $($dependencies[$relative])" }
    }
}
```
<!-- El resto de las dependencias las resuelve Maven. Para una primera corrida quitar -o. -->

```powershell
$selectorDir = Join-Path $work 'vt-selector-classes'
$services = Join-Path $selectorDir 'META-INF/services'
New-Item -ItemType Directory -Path $services -Force | Out-Null
$junit = Join-Path $repo 'org/junit/jupiter/junit-jupiter-api/6.1.3/junit-jupiter-api-6.1.3.jar'
$api = Join-Path $repo 'org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar'
& (Join-Path $jdk21 'bin\javac.exe') -cp "$junit;$api" -d $selectorDir (Join-Path $work 'VirtualInvocationSelection.java')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar el selector' }
'jcv.VirtualInvocationSelection' | Set-Content -LiteralPath (Join-Path $services 'org.junit.jupiter.api.extension.Extension') -Encoding ascii
$selectorJar = Join-Path $work 'virtual-invocations.jar'
& (Join-Path $jdk21 'bin\jar.exe') --create --file $selectorJar -C $selectorDir .
if ($LASTEXITCODE -ne 0) { throw 'No se pudo empaquetar el selector' }

Copy-Reactor $src21
$log21 = Join-Path $work 'jdk21-verify.log'
$tests21 = @(
    'org.eclipse.jetty.util.thread.VirtualThreadPoolTest'
    'org.eclipse.jetty.server.handler.QoSHandlerTest#testRequestInVirtualThreadIsResumedInVirtualThread'
    'org.eclipse.jetty.test.client.transport.VirtualThreadsTest'
    'org.eclipse.jetty.util.thread.strategy.ExecutionStrategyTest'
) -join ','
$offline = @('-o')  # Quitar solo si faltan dependencias en el repositorio privado.
$args21 = $common + $offline + @(
    '-pl', $modules, '-P!enable-foreign',
    '-Dsurefire.failIfNoSpecifiedTests=false', '-Dfailsafe.failIfNoSpecifiedTests=false',
    "-Dtest=$tests21", "-Dit.test=$tests21", "-Djvm=$(Join-Path $jdk21 'bin\java.exe')",
    "-Dmaven.test.additionalClasspath=$selectorJar",
    "-Djetty.surefire.argLine=$forkBase -showversion -Xms64m -Xmx1024m", 'verify'
)
Invoke-JettyVerify $src21 $jdk21 '-Xms64m -Xmx768m' $log21 $args21
java -version  # Debe volver a mostrar el Java predeterminado. En el equipo de referencia, 17.0.11.
git -C $original status --porcelain --untracked-files=no
```

### Resultado acreditado y variante Linux

| XML de Surefire | Entradas | Aprobadas | Omitidas |
|---|---:|---:|---:|
| `TEST-org.eclipse.jetty.util.thread.VirtualThreadPoolTest.xml` | 6 | 6 | 0 |
| `TEST-org.eclipse.jetty.server.handler.QoSHandlerTest.xml` | 1 | 1 | 0 |
| `TEST-org.eclipse.jetty.test.client.transport.VirtualThreadsTest.xml` | 14 | 14 | 0 |
| `TEST-org.eclipse.jetty.util.thread.strategy.ExecutionStrategyTest.xml` | 36 | 12 | 24 |
| **Total** | **57** | **33** | **24** |

Los cuatro XML registraron Java `21.0.13.1`, cero fallos y cero errores. La corrida válida terminó con código Maven `0`. Las 24 omisiones corresponden al selector de plataforma. En transportes, el handler tuvo cuatro variantes (`HTTP`, `HTTPS`, `H2C` y `H2`). Cada grupo de listeners probó las mismas cuatro más `FCGI`.

Las tres invocaciones `H3_QUICHE` son las de `testHandlerInvokedOnVirtualThread`, `testBlockingClientListenersInvokedOnVirtualThread` y `testNonBlockingClientListenersInvokedOnPlatformThread`. En el orden del enum de este commit ocupan el índice `5` de cada método cuando el proveedor incluye H3. En Windows ese mismo índice corresponde a FCGI en los métodos de listeners. Valida el argumento `H3_QUICHE` además del índice. En Linux con JDK 21 usa el grupo `VirtualThreadsTest`, `-P!enable-foreign` y el selector genérico del apéndice limitado a `#5` en los tres métodos. Sustituye `;` por `:` en el classpath de compilación y fija `JAVA_HOME` y `PATH` en un subshell para la compilación del selector y `mvn`. En Linux los tres casos siguen pendientes. La secuencia exacta en ese entorno está por verificar.


En Linux, desde la raíz de una copia limpia al commit indicado, establece la ruta del JDK 21 en `JDK21_HOME`. Copia `PendingCondition.java` del bloque sin instrumentación y el TSV de tres variantes a una carpeta nueva y guarda su ruta absoluta en `JETTY_TEST_WORK`. La carpeta debe quedar fuera de la copia. El siguiente comando focaliza el reactor en la suite y sus dependencias.

```bash
(
  set -euo pipefail
  test "$(git rev-parse HEAD)" = 770f5e4d1c39673d6356163118a1e6bf1117ced3
  export JAVA_HOME="$JDK21_HOME"
  export PATH="$JAVA_HOME/bin:$PATH"
  export MAVEN_SKIP_RC=true MAVEN_OPTS='-Xms64m -Xmx768m'
  unset JAVA_TOOL_OPTIONS JDK_JAVA_OPTIONS _JAVA_OPTIONS MAVEN_ARGS
  work="$JETTY_TEST_WORK"
  repo="$work/m2"
  junit='org/junit/jupiter/junit-jupiter-api/6.1.3/junit-jupiter-api-6.1.3.jar'
  api='org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar'
  for artifact in "$junit" "$api"; do
    mkdir -p "$(dirname "$repo/$artifact")"
    if [ ! -s "$repo/$artifact" ]; then
      curl -fsSL -o "$repo/$artifact" "https://repo.maven.apache.org/maven2/$artifact"
    fi
  done
  classes="$work/h3-selector"
  mkdir -p "$classes/META-INF/services"
  javac -cp "$repo/$junit:$repo/$api" -d "$classes" "$work/PendingCondition.java"
  printf '%s\n' jettypending.PendingCondition > "$classes/META-INF/services/org.junit.jupiter.api.extension.Extension"
  cp "$work/pending-cases.tsv" "$classes/META-INF/pending-cases.tsv"
  jar --create --file "$work/h3-selector.jar" -C "$classes" .
  java -version
  mvn -version
  tests='org.eclipse.jetty.test.client.transport.VirtualThreadsTest'
  mvn -B -ntp -fae -pl jetty-core/jetty-tests/jetty-test-client-transports -am \
    '-P!enable-foreign' "-Dmaven.repo.local=$repo" -Dmaven.build.cache.enabled=false \
    -Dspotless.skip=true -Dcheckstyle.skip=true -Dsurefire.failIfNoSpecifiedTests=false \
    -Dfailsafe.failIfNoSpecifiedTests=false "-Dtest=$tests" "-Dit.test=$tests" \
    "-Djvm=$JAVA_HOME/bin/java" "-Dmaven.test.additionalClasspath=$work/h3-selector.jar" \
    '-Djetty.surefire.argLine=-Dfile.encoding=UTF-8 -Duser.language=en -Duser.region=US -showversion -Xms64m -Xmx1024m' \
    verify 2>&1 | tee "$work/linux-h3-verify.log"
)
```


## Qué revisar al terminar

- `<módulo>/target/surefire-reports/TEST-*.xml` y, para suites que lo vinculen, `<módulo>/target/failsafe-reports/`, dentro de la copia. Las suites compartidas de estas corridas aportaron evidencia de Surefire.
- En cada XML, coteja los `testcase` con el selector. `failure` es un fallo de prueba, `error` es un error de ejecución y `skipped` contiene la condición. Un caso sin fila queda sin evidencia. Revisa `java.version` y `java.home` para confirmar el fork, junto al registro de `mvn -version` del lanzador.
- En el informe Maven confirma `BUILD SUCCESS`, el código de salida y la ausencia del objetivo `install`. En `surefire.test.class.path`, `java.class.path` y `jdk.module.path` comprueba que las salidas o JAR de estos módulos Jetty 12.1.15 proceden de `target/` de esta copia. No debe haber JAR ni POM Jetty 12.1.15 instalados en `$repo`. En la corrida válida JDK 21 se comprobaron 42 rutas de JAR Jetty de la misma copia y los 14 JAR principales en `target/`.
- Guarda el comando, versiones, código de salida, log y XML juntos. Los archivos históricos `verify.log`, `command.json`, `results-summary.json` y los cuatro XML de `jcv-vt21-770f5e4-verify` se cotejaron al preparar esta guía. Los datos anteriores permiten repetir la corrida aunque desaparezca ese directorio.


## Incidentes y comprobaciones

Los ajustes se aplicaron en copias descartables. Las corridas inicial y de hilos virtuales usaron las fuentes y pruebas del commit.

| Incidente | Causa y evidencia | Cambio y verificación |
|---|---|---|
| Agotamiento del heap del cliente | `OutOfMemoryError: Java heap space` en `ArrayByteBufferPool.Tracking.dumpLeaks` durante el teardown de JUnit con el fork limitado a 768 MiB. El error del motor dejó 36 casos sin resultado terminal en `ContentDecoderFactoriesTest`, `HttpClientGZIPTest`, `OriginTest` y `SPNEGOAuthenticationTest`. | Repetición focalizada con `-Xms64m -Xmx1792m` y `-Djunit.jupiter.execution.parallel.enabled=false`. Los 36 casos aprobaron. La comparación no aísla cuánto aportó el heap frente al paralelismo o a la reducción de casos. |
| Lectura de JAR bloqueada antes de probar | `AccessDeniedException` al resolver la ruta real del JAR de JUnit en `javac`. Maven mostró `cannot read file … slf4j-api-2.0.17.jar` y `module not found: org.slf4j`. El intento final con JDK 17 y el primero con JDK 21 terminaron con código `1` sin XML de los casos seleccionados. | Usar una copia nueva en una ruta accesible a Java con el token normal del usuario. En el entorno de ejecución se autorizó salir de la restricción de lectura, sin elevar el token de Windows. El segundo intento JDK 21 compiló y generó los cuatro XML. Verifica el acceso de Java a los JAR antes de diagnosticar una dependencia ausente. |
| Limpieza de las cuatro descargas | La descarga de 1 MiB dejó un archivo que bloqueó su `AfterEach`. Las tres siguientes fallaron inicialmente al limpiar la misma ruta. En diagnósticos posteriores las aserciones de contenido llegaron al final, pero `FS.ensureEmpty()` rechazó el destino fuera del `target/tests` efectivo. Un segmento `target/tests` anidado en otra ruta también fue rechazado. | Crear un directorio nuevo por invocación con `Files.createTempDirectory(MavenPaths.targetTests(), …)` en el `BeforeEach`. Mantener las aserciones de igualdad de bytes y el `AfterEach` oficial. En la copia ajustada, las variantes de 0 y 1024 bytes completaron la limpieza. |
| Borrado de dos descargas de 1 MiB | `ResourceHandler` instala `FileMappingHttpContentFactory`, cuyo umbral predeterminado es 1 MiB. Un control Win32 obtuvo `WinError 5` mientras había una vista mapeada, incluso tras cerrar el handle de apertura. La JVM de Surefire conservó la vista en ambos fixtures tras detener el servidor y vaciar la caché. | En la copia experimental se detuvo el servidor, se llamó a `flushCache()` y se solicitó GC durante un máximo de ocho segundos, muestreando la vista antes del teardown oficial. Ambos XML aprobaron y el log registró `after-gc-1` sin vista y `DIAG_DOWNLOAD_CLEANUP official=passed entries=0`. El plazo de liberación observado no constituye una garantía del GC. |
| `ConcurrentRequestsTest` y `RST_STREAM(NO_ERROR)` | La traza correlacionó por conexión y flujo 51 resets con `/bad` en conexiones separadas y cuatro en la compartida. En la compartida el flujo 15 de `/bad-3` aún estaba activo cuando recibió un reset tras el 400. Las 65 y 291 solicitudes `/good`, respectivamente, completaron 200 con fin de flujo. | La corrida diagnóstica aprobó conexiones separadas y falló la compartida. La copia experimental trasladó `END_STREAM` al camino de metadatos rechazados de `HTTP2ServerSession` y aprobó la variante compartida. Queda por acreditar la repetibilidad y el resultado del commit oficial sin ese cambio. |
| `testUtf8Dir` | En Windows `isSameName` y `Files.isSameFile` devolvieron verdadero para el directorio mientras la comparación de URI enfrentó `bãm/` con `b%C3%A3m/`. La primera normalización también ocultó el alias exigido del hijo. | La copia final ajustó `PathResource.resolveAlias()`. El directorio usa una comparación ASCII cuando difieren las URI. Para el archivo del sistema de archivos predeterminado en Windows se conserva la URI nativa del destino. Surefire aprobó las dos aserciones originales. |
| `FormTest[8]` | La línea base observó estado `0` en HTTPS con límite 128. En la corrida diagnóstica `HttpGenerator` produjo 413, la escritura terminó y el cliente leyó 413. | El caso aprobó sin cambiar código. Falta una traza que vuelva a observar estado `0` para localizar su origen. |
| `testDoubleReadFromPart` | `PrintWriter.println()` generó CRLF en la aplicación Windows. El cliente recibió esos bytes y el valor esperado usa LF. | En una copia se usó `print(... + "\n")`, manteniendo ambas lecturas y las aserciones. El XML aprobó. |
| `testManyParts` y EOF | Se superó el límite de claves (1025 frente a 1024). En la traza el servidor completó un 400. En la ejecución fallida el receptor no llegó a leer el estado y `HttpReceiverOverHTTP.earlyEOF()` entregó `java.io.EOFException` donde la prueba exige `org.eclipse.jetty.io.EofException`. | En la copia experimental la prueba multipart aprobó al recibir 400. Otra copia sustituyó el tipo que usa `earlyEOF()` y añadió `testEOFBeforeResponseStatus`, con EOF simulado antes del estado. Su XML aprobó y comprobó el tipo exacto de la causa. |

Referencias del diagnóstico de archivos. [ResourceHandler](../jetty-core/jetty-server/src/main/java/org/eclipse/jetty/server/handler/ResourceHandler.java) · [FileMappingHttpContentFactory](../jetty-core/jetty-http/src/main/java/org/eclipse/jetty/http/content/FileMappingHttpContentFactory.java) · [PathResponseListenerTest](../jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java)

## Resultados históricos por corrida

| Evidencia histórica | Maven | Resultado de los casos previstos según los XML |
|---|---:|---|
| `jcv-770f5e4` | 0 | 18 905 aprobados, 15 fallos, 3 errores y 269 omisiones. |
| `jcv-pending-770f5e4` | 0 | 53 casos, 43 aprobados y 10 fallos. Otros 35 quedaron excluidos por selección. |
| `jcv-diag-770f5e4` | 0 | 2 aprobados y 8 fallos. Aprobaron `FormTest[8]` y HTTP/2 con conexiones separadas. |
| `jcv-eight-770f5e4-5ewPgB` | 0 | 8 fallos. Las cuatro descargas volvieron a chocar con el límite de limpieza. |
| `jcv-fix-770f5e4-sVRM7o` | 0 | 5 aprobados y 3 fallos en la copia con cambios. Aprobaron dos descargas pequeñas, HTTP/2 compartido y los dos casos multipart. Fallaron las dos descargas de 1 MiB en limpieza y `testUtf8Dir` en su aserción. |
| `jcv-final-770f5e4-IgaOCI` | 1 | 4 casos sin XML por bloqueo de apertura de JAR. |
| `jetty-verify-ehqea4` | 0 | 4 aprobados en la copia experimental. Las dos descargas de 1 MiB, `testUtf8Dir` y el control EOF. |
| `jcv-vt21-770f5e4-028d84` | 1 | Primer intento JDK 21 sin XML por bloqueo de apertura de JAR. |
| `jcv-vt21-770f5e4-verify` | 0 | 33 aprobados, 24 excluidos deliberadamente y 3 variantes H3 pendientes en Linux. |

La causa de una intermitencia sigue abierta cuando solo se dispone de una repetición aprobada. Las pruebas con parches diagnósticos acreditan el comportamiento de sus copias.

## Repetir una selección de diagnóstico con JDK 17

Crea una copia nueva, conserva `$repo` y guarda una tabla TSV del apéndice en `pending-cases.tsv`. Cada fila contiene `clase#método`, una tabulación y el índice de JUnit. Usa `0` para un método ordinario. El filtro admite la expansión de los métodos parametrizados y aplica la selección a cada invocación. Guarda `PendingCondition.java` del apéndice en `$work`. El filtro reducido sirve para seleccionar pruebas oficiales. Para repetir los experimentos Windows usa el filtro y el diff indicados en el apéndice. Aplica el diff solo a la copia experimental y compruébalo antes con `git apply --check`.

```powershell
$plan = Join-Path $work 'pending-cases.tsv'
$junit = Join-Path $repo 'org/junit/jupiter/junit-jupiter-api/6.1.3/junit-jupiter-api-6.1.3.jar'
$api = Join-Path $repo 'org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar'
$caseRows = Get-Content -LiteralPath $plan | ForEach-Object {
    $key,$index = $_ -split '\t',2
    $class,$method = $key -split '#',2
    [pscustomobject]@{ Class=$class; Method=$method; Index=[int]$index }
}
$testFilter = ($caseRows | Group-Object Class | ForEach-Object {
    $_.Name + '#' + (($_.Group.Method | Sort-Object -Unique) -join '+')
}) -join ','
$diagClasses = Join-Path $work 'diag-classes'
$servicePath = Join-Path $diagClasses 'META-INF/services'
New-Item -ItemType Directory -Path $servicePath -Force | Out-Null
& (Join-Path $jdk17 'bin\javac.exe') -cp "$junit;$api" -d $diagClasses (Join-Path $work 'PendingCondition.java')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar el selector diagnóstico' }
'jettypending.PendingCondition' | Set-Content -LiteralPath (Join-Path $servicePath 'org.junit.jupiter.api.extension.Extension') -Encoding ascii
Get-Content -LiteralPath $plan | Set-Content -LiteralPath (Join-Path $diagClasses 'META-INF/pending-cases.tsv') -Encoding ascii
$diagJar = Join-Path $work 'diag-filter.jar'
& (Join-Path $jdk17 'bin\jar.exe') --create --file $diagJar -C $diagClasses .
if ($LASTEXITCODE -ne 0) { throw 'No se pudo empaquetar el selector diagnóstico' }

$diagSrc = Join-Path $work 'jdk17-diag-src'
Copy-Reactor $diagSrc
# Para una copia experimental, guardar el diff indicado como experimento.patch:
# git -C $diagSrc apply --check (Join-Path $work 'experimento.patch')
# git -C $diagSrc apply (Join-Path $work 'experimento.patch')

# Ejecutar ahora el bloque "Módulos, trazado y modo por corrida" del apéndice.
# Continuar después con las líneas siguientes, usando los valores de esa variante.
$argsDiag = $common + $diagOffline + @(
    '-pl', $diagModules, '-Dmaven.test.failure.ignore=true',
    '-Dsurefire.failIfNoSpecifiedTests=false', '-Dfailsafe.failIfNoSpecifiedTests=false',
    "-Dtest=$testFilter", "-Dit.test=$testFilter", "-Dmaven.test.additionalClasspath=$diagJar",
    '-Djunit.jupiter.execution.parallel.enabled=false',
    "-Djetty.surefire.argLine=$forkBase -Xms64m -Xmx1792m"
) + $diagnostics + @('verify')
Invoke-JettyVerify $diagSrc $jdk17 '-Xms64m -Xmx640m' (Join-Path $work 'jdk17-diag.log') $argsDiag
```

## Apéndice de reproducción
### Selector de hilos virtuales

Guardar como `VirtualInvocationSelection.java`.

```java
package jcv;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;
import java.util.regex.Pattern;

public final class VirtualInvocationSelection implements ExecutionCondition {
    private static final Pattern INVOCATION = Pattern.compile("\\[test-template-invocation:#([0-9]+)]$");
    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        if (context.getTestClass().filter(c ->
                c.getName().equals("org.eclipse.jetty.util.thread.strategy.ExecutionStrategyTest")).isPresent()) {
            var match = INVOCATION.matcher(context.getUniqueId());
            if (match.find() && Integer.parseInt(match.group(1)) <= 6)
                return ConditionEvaluationResult.disabled(
                    "vt21-selection: platform invocation covered in the JDK 17 reactor");
        }
        return ConditionEvaluationResult.enabled("selected original invocation");
    }
}
```


### Selector por invocación sin instrumentación

Guardar como PendingCondition.java para la corrida de 53 o la selección en Linux. Para Linux usa JDK 21 al compilarlo y el classpath separado por dos puntos.

```java
package jettypending;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;

public final class PendingCondition implements ExecutionCondition {
    private static final Map<String, Set<Integer>> SELECTED = load();
    private static final Pattern INVOCATION = Pattern.compile("\\[test-template-invocation:#(\\d+)]$");
    private static final String EXCLUDED = "pending-selection: previously complete or outside selection";

    private static Map<String, Set<Integer>> load() {
        var input = PendingCondition.class.getResourceAsStream("/META-INF/pending-cases.tsv");
        if (input == null) {
            throw new IllegalStateException("Missing pending-cases.tsv");
        }
        var table = new HashMap<String, Set<Integer>>();
        try (var reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                var fields = line.split("\\t", 2);
                table.computeIfAbsent(fields[0], ignored -> new HashSet<>()).add(Integer.parseInt(fields[1]));
            }
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        return table;
    }

    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        var method = context.getTestMethod();
        if (method.isEmpty()) {
            return ConditionEvaluationResult.enabled("test container");
        }
        String key = context.getRequiredTestClass().getName() + "#" + method.get().getName();
        var indices = SELECTED.get(key);
        if (indices == null) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        var matcher = INVOCATION.matcher(context.getUniqueId());
        if (matcher.find()) {
            int index = Integer.parseInt(matcher.group(1));
            if (!indices.contains(index)) {
                return ConditionEvaluationResult.disabled(EXCLUDED);
            }
            System.out.println("PENDING_SELECTED " + key + " #" + index);
            return ConditionEvaluationResult.enabled("pending invocation");
        }
        if (context.getUniqueId().contains("[test-template:")) {
            return ConditionEvaluationResult.enabled("template for pending invocations");
        }
        if (!indices.contains(0)) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        System.out.println("PENDING_SELECTED " + key + " #0");
        return ConditionEvaluationResult.enabled("pending method");
    }
}
```


### Planes TSV

Copia solo las filas del bloque elegido. Los espacios entre clave e índice son tabuladores.

**53 casos de JDK 17.** Incluye los 36 casos sin XML por el heap, los fallos y errores de prueba seleccionados.

```text
org.eclipse.jetty.client.ContentDecoderFactoriesTest#testAcceptEncodingDoesNotDependOnDefaultLocale	1
org.eclipse.jetty.client.ContentDecoderFactoriesTest#testAcceptEncodingDoesNotDependOnDefaultLocale	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentCorrupted	1
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentCorrupted	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentEncoding	1
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentEncoding	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentFragmentedAtTrailer	1
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentFragmentedAtTrailer	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentFragmentedBeforeTrailer	1
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentFragmentedBeforeTrailer	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentOneByteAtATime	1
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentOneByteAtATime	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentSentTwiceInOneWrite	1
org.eclipse.jetty.client.HttpClientGZIPTest#testGZIPContentSentTwiceInOneWrite	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGarbageGzipResponse	1
org.eclipse.jetty.client.HttpClientGZIPTest#testGarbageGzipResponse	2
org.eclipse.jetty.client.HttpClientGZIPTest#testGarbageGzipResponse	3
org.eclipse.jetty.client.HttpClientGZIPTest#testGarbageGzipResponse	4
org.eclipse.jetty.client.HttpClientGZIPTest#testGarbageGzipResponse	5
org.eclipse.jetty.client.HttpClientGZIPTest#testGarbageGzipResponse	6
org.eclipse.jetty.client.HttpClientGZIPTest#testLargeGZIPContentAsync	1
org.eclipse.jetty.client.HttpClientGZIPTest#testLargeGZIPContentAsync	2
org.eclipse.jetty.client.HttpClientGZIPTest#testLargeGZIPContentDoesNotPolluteByteBufferPool	1
org.eclipse.jetty.client.HttpClientGZIPTest#testLargeGZIPContentDoesNotPolluteByteBufferPool	2
org.eclipse.jetty.client.HttpClientGZIPTest#testMultipleContentEncodingsFooGZIP	1
org.eclipse.jetty.client.HttpClientGZIPTest#testMultipleContentEncodingsFooGZIP	2
org.eclipse.jetty.client.HttpClientGZIPTest#testMultipleContentEncodingsGZIPFoo	1
org.eclipse.jetty.client.HttpClientGZIPTest#testMultipleContentEncodingsGZIPFoo	2
org.eclipse.jetty.client.OriginTest#testAddressAsStringDoesNotDependOnDefaultLocale	1
org.eclipse.jetty.client.OriginTest#testAddressAsStringDoesNotDependOnDefaultLocale	2
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownload	3
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	1
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	2
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	3
org.eclipse.jetty.client.util.SPNEGOAuthenticationTest#testAuthenticationExpiration	1
org.eclipse.jetty.client.util.SPNEGOAuthenticationTest#testAuthenticationExpiration	2
org.eclipse.jetty.client.util.SPNEGOAuthenticationTest#testKeyTabSPNEGOAuthentication	1
org.eclipse.jetty.client.util.SPNEGOAuthenticationTest#testKeyTabSPNEGOAuthentication	2
org.eclipse.jetty.client.util.SPNEGOAuthenticationTest#testPasswordSPNEGOAuthentication	1
org.eclipse.jetty.client.util.SPNEGOAuthenticationTest#testPasswordSPNEGOAuthentication	2
org.eclipse.jetty.http2.tests.ConcurrentRequestsTest#testConcurrentGoodRequestsWithBadRequestsWithDifferentConnections	0
org.eclipse.jetty.http2.tests.ConcurrentRequestsTest#testConcurrentGoodRequestsWithBadRequestsWithSameConnection	0
org.eclipse.jetty.proxy.ForwardProxyWithDynamicTransportTest#testProxyConcurrentLoad	14
org.eclipse.jetty.server.HttpChannelTest#testBlockingPOST	0
org.eclipse.jetty.server.handler.MinimumDataRateHandlerTest#testMinimumDataWriteRateWithSingleLastWrite	0
org.eclipse.jetty.test.client.transport.FormTest#testMaxFormContentSizeExceeded	5
org.eclipse.jetty.test.client.transport.FormTest#testMaxFormContentSizeExceeded	8
org.eclipse.jetty.util.resource.FileSystemResourceTest#testUtf8Dir	0
org.eclipse.jetty.util.thread.QueuedThreadPoolTest#testMaxStopTime	0
org.eclipse.jetty.util.thread.ThreadFactoryTest#testThreadFactory	0
org.eclipse.jetty.test.CoreMultiPartTest#testDoubleReadFromPart	0
org.eclipse.jetty.test.CoreMultiPartTest#testLargePart	0
org.eclipse.jetty.test.CoreMultiPartTest#testManyParts	0
```


**10 casos de diagnóstico.**

```text
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownload	3
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	1
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	2
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	3
org.eclipse.jetty.http2.tests.ConcurrentRequestsTest#testConcurrentGoodRequestsWithBadRequestsWithDifferentConnections	0
org.eclipse.jetty.http2.tests.ConcurrentRequestsTest#testConcurrentGoodRequestsWithBadRequestsWithSameConnection	0
org.eclipse.jetty.test.client.transport.FormTest#testMaxFormContentSizeExceeded	8
org.eclipse.jetty.util.resource.FileSystemResourceTest#testUtf8Dir	0
org.eclipse.jetty.test.CoreMultiPartTest#testDoubleReadFromPart	0
org.eclipse.jetty.test.CoreMultiPartTest#testManyParts	0
```


**8 casos.** Mismo plan para la corrida de montaje y para el experimento intermedio.

```text
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownload	3
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	1
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	2
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	3
org.eclipse.jetty.http2.tests.ConcurrentRequestsTest#testConcurrentGoodRequestsWithBadRequestsWithSameConnection	0
org.eclipse.jetty.util.resource.FileSystemResourceTest#testUtf8Dir	0
org.eclipse.jetty.test.CoreMultiPartTest#testDoubleReadFromPart	0
org.eclipse.jetty.test.CoreMultiPartTest#testManyParts	0
```


**4 casos del experimento final.**

```text
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownload	3
org.eclipse.jetty.client.PathResponseListenerTest#testFileDownloadWithCompletable	3
org.eclipse.jetty.util.resource.FileSystemResourceTest#testUtf8Dir	0
org.eclipse.jetty.client.http.HttpReceiverOverHTTPTest#testEOFBeforeResponseStatus	0
```


**3 variantes H3 en Linux.** El índice 5 debe figurar con el argumento H3_QUICHE.

```text
org.eclipse.jetty.test.client.transport.VirtualThreadsTest#testHandlerInvokedOnVirtualThread	5
org.eclipse.jetty.test.client.transport.VirtualThreadsTest#testBlockingClientListenersInvokedOnVirtualThread	5
org.eclipse.jetty.test.client.transport.VirtualThreadsTest#testNonBlockingClientListenersInvokedOnPlatformThread	5
```


### Módulos, trazado y modo por corrida

Ejecuta este bloque tras preparar la copia y antes de construir la línea Maven. El valor de la variante identifica el plan y el filtro. Las corridas de ocho casos se registraron con token elevado. Los bloqueos de limpieza persistieron en la corrida de montaje incluso con ese token. Los comandos aquí permiten probar con permisos normales.

```powershell
$variant = '53'  # 53, 10, 8-montaje, 8-fix o final

if ($variant -eq '53') {
    $diagModules = ($core14 + @(
        'jetty-core/jetty-bom'
        'jetty-core/jetty-jmx'
        'tests/jetty-test-multipart'
        'build/build-resources'
        'jetty-core/jetty-client'
        'jetty-core/jetty-http2/jetty-http2-tests'
        'jetty-core/jetty-proxy'
        'jetty-core/jetty-tests/jetty-test-client-transports'
        'tests/test-integration'
    )) -join ','
    $diagOffline = @()
    $diagnostics = @(
    )
}

if ($variant -eq '10') {
    $diagModules = ($core14 + @(
        'jetty-core/jetty-bom'
        'jetty-core/jetty-jmx'
        'tests/jetty-test-multipart'
        'build/build-resources'
        'jetty-core/jetty-client'
        'jetty-core/jetty-http2/jetty-http2-tests'
        'jetty-core/jetty-tests/jetty-test-client-transports'
        'tests/test-integration'
    )) -join ','
    $diagOffline = @()
    $diagnostics = @(
        "-Djetty.diag.python=$((Get-Command python -ErrorAction Stop).Source)"
        "-Djetty.diag.fileProbe=$(Join-Path $work 'fileprobe.py')"
        "-Djetty.diag.dir=$(Join-Path $work 'download-fixtures')"
        '-Dorg.eclipse.jetty.http2.HTTP2Session.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.HTTP2Stream.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.HTTP2Flusher.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.server.internal.HttpStreamOverHTTP2.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.server.internal.HTTP2ServerSession.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.client.internal.HTTP2ClientSession.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.server.internal.HttpConnection.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.server.internal.HttpChannelState.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http.HttpGenerator.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.internal.HttpSenderOverHTTP.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.internal.HttpReceiverOverHTTP.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.HttpSender.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.HttpReceiver.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.InputStreamResponseListener.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.server.FormFields.LEVEL=DEBUG'
    )
    New-Item -ItemType Directory -Path (Join-Path $work 'download-fixtures') -Force | Out-Null
}

if ($variant -eq '8-montaje') {
    $diagModules = ($core14 + @(
        'jetty-core/jetty-bom'
        'jetty-core/jetty-jmx'
        'tests/jetty-test-multipart'
        'build/build-resources'
        'jetty-core/jetty-client'
        'jetty-core/jetty-http2/jetty-http2-tests'
        'tests/test-integration'
    )) -join ','
    $diagOffline = @()
    $diagnostics = @(
        "-Djetty.diag.python=$((Get-Command python -ErrorAction Stop).Source)"
        "-Djetty.diag.fileProbe=$(Join-Path $work 'fileprobe.py')"
        "-Djetty.diag.dir=$(Join-Path $diagSrc 'jetty-core/jetty-client/target/isolated-downloads')"
        '-Dorg.eclipse.jetty.http2.HTTP2Session.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.HTTP2Stream.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.HTTP2Flusher.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.server.internal.HttpStreamOverHTTP2.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.server.internal.HTTP2ServerSession.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.client.internal.HTTP2ClientSession.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.server.internal.HttpConnection.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.server.internal.HttpChannelState.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http.HttpGenerator.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.internal.HttpSenderOverHTTP.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.internal.HttpReceiverOverHTTP.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.HttpSender.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.HttpReceiver.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.InputStreamResponseListener.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http.content.FileMappingHttpContentFactory.LEVEL=DEBUG'
    )
    New-Item -ItemType Directory -Path (Join-Path $diagSrc 'jetty-core/jetty-client/target/isolated-downloads') -Force | Out-Null
}

if ($variant -eq '8-fix') {
    $diagModules = ($core14 + @(
        'jetty-core/jetty-bom'
        'jetty-core/jetty-jmx'
        'tests/jetty-test-multipart'
        'build/build-resources'
        'jetty-core/jetty-client'
        'jetty-core/jetty-http2/jetty-http2-tests'
        'tests/test-integration'
    )) -join ','
    $diagOffline = @()
    $diagnostics = @(
        "-Djetty.diag.python=$((Get-Command python -ErrorAction Stop).Source)"
        "-Djetty.diag.fileProbe=$(Join-Path $work 'fileprobe.py')"
        '-Dorg.eclipse.jetty.http2.HTTP2Session.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.HTTP2Stream.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.HTTP2Flusher.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.server.internal.HttpStreamOverHTTP2.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.server.internal.HTTP2ServerSession.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http2.client.internal.HTTP2ClientSession.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.server.internal.HttpConnection.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.server.internal.HttpChannelState.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http.HttpGenerator.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.internal.HttpSenderOverHTTP.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.internal.HttpReceiverOverHTTP.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.HttpSender.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.transport.HttpReceiver.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.client.InputStreamResponseListener.LEVEL=DEBUG'
        '-Dorg.eclipse.jetty.http.content.FileMappingHttpContentFactory.LEVEL=DEBUG'
    )
}

if ($variant -eq 'final') {
    $diagModules = ($core14 + @(
        'jetty-core/jetty-bom'
        'jetty-core/jetty-jmx'
        'build/build-resources'
        'jetty-core/jetty-client'
    )) -join ','
    $diagOffline = @('-o')
    $diagnostics = @(
        "-Djetty.diag.python=$((Get-Command python -ErrorAction Stop).Source)"
        "-Djetty.diag.fileProbe=$(Join-Path $work 'fileprobe.py')"
        '-Dorg.eclipse.jetty.client.transport.internal.HttpReceiverOverHTTP.LEVEL=DEBUG'
    )
}
```


### Instrumentación de la variante 10

El montaje histórico crea un fixture fuera del target/tests efectivo. Conserva esa ruta si quieres reproducir el fallo de montaje.

**PendingCondition.java**

```java
package jettypending;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.InvocationInterceptor;
import org.junit.jupiter.api.extension.ReflectiveInvocationContext;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;

public final class PendingCondition implements ExecutionCondition, InvocationInterceptor {
    private static final Map<String, Set<Integer>> SELECTED = load();
    private static final Pattern INVOCATION = Pattern.compile("\\[test-template-invocation:#(\\d+)]$");
    private static final String EXCLUDED = "pending-selection: previously complete or outside selection";

    private static Map<String, Set<Integer>> load() {
        var input = PendingCondition.class.getResourceAsStream("/META-INF/pending-cases.tsv");
        if (input == null) {
            throw new IllegalStateException("Missing pending-cases.tsv");
        }
        var table = new HashMap<String, Set<Integer>>();
        try (var reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                var fields = line.split("\\t", 2);
                table.computeIfAbsent(fields[0], ignored -> new HashSet<>()).add(Integer.parseInt(fields[1]));
            }
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        return table;
    }

    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        var method = context.getTestMethod();
        if (method.isEmpty()) {
            return ConditionEvaluationResult.enabled("test container");
        }
        String key = context.getRequiredTestClass().getName() + "#" + method.get().getName();
        var indices = SELECTED.get(key);
        if (indices == null) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        var matcher = INVOCATION.matcher(context.getUniqueId());
        if (matcher.find()) {
            int index = Integer.parseInt(matcher.group(1));
            if (!indices.contains(index)) {
                return ConditionEvaluationResult.disabled(EXCLUDED);
            }
            System.out.println("PENDING_SELECTED " + key + " #" + index);
            return ConditionEvaluationResult.enabled("pending invocation");
        }
        if (context.getUniqueId().contains("[test-template:")) {
            return ConditionEvaluationResult.enabled("template for pending invocations");
        }
        if (!indices.contains(0)) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        System.out.println("PENDING_SELECTED " + key + " #0");
        return ConditionEvaluationResult.enabled("pending method");
    }

    private static final ExtensionContext.Namespace DIAG = ExtensionContext.Namespace.create(PendingCondition.class, "diagnostics");
    private static boolean download(ExtensionContext c) {
        return c.getRequiredTestClass().getName().equals("org.eclipse.jetty.client.PathResponseListenerTest");
    }

    @Override
    public void interceptBeforeEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        if (!download(context) || !invocation.getExecutable().getName().equals("startServer")) {
            call.proceed();
            return;
        }
        // The official setup still creates and empties its directory for this invocation.
        Path root = Files.createTempDirectory(Path.of(System.getProperty("jetty.diag.dir")), context.getRequiredTestMethod().getName() + "-");
        context.getStore(DIAG).put("download-root", root);
        var helper = Class.forName("org.eclipse.jetty.toolchain.test.MavenTestingUtils", true, context.getRequiredTestClass().getClassLoader());
        var target = helper.getDeclaredField("targetPath");
        target.setAccessible(true);
        var previous = target.get(null);
        target.set(null, root);
        System.out.println("DIAG_DOWNLOAD_ISOLATED " + context.getUniqueId() + " " + root);
        try {
            call.proceed();
        } finally {
            target.set(null, previous);
        }
    }

    @Override
    public void interceptAfterEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        try {
            call.proceed();
        } catch (Throwable failure) {
            if (download(context) && invocation.getExecutable().getName().equals("stopServer")) {
                try {
                    Path root = context.getStore(DIAG).get("download-root", Path.class);
                    if (root != null) {
                        var process = new ProcessBuilder(System.getProperty("jetty.diag.python"), "-X", "utf8",
                            System.getProperty("jetty.diag.fileProbe"), root.toString()).redirectErrorStream(true).start();
                        if (process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) {
                            System.out.print(new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8));
                        } else {
                            process.destroyForcibly();
                            System.out.println("DIAG_HELPER_FAILED delete probe timed out");
                        }
                    }
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
            throw failure;
        }
    }

    @Override
    public void interceptTestMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        try {
            call.proceed();
        } finally {
            if ("testUtf8Dir".equals(context.getRequiredTestMethod().getName())) {
                try {
                    Object work = invocation.getArguments().get(0);
                    Path base = (Path)work.getClass().getMethod("getPath").invoke(work);
                    Path requested = base.resolve("b\u00e3m");
                    Path real = requested.toRealPath();
                    var factoryClass = Class.forName("org.eclipse.jetty.util.resource.ResourceFactory", true, context.getRequiredTestClass().getClassLoader());
                    var factory = factoryClass.getMethod("root").invoke(null);
                    var resource = factoryClass.getMethod("newResource", Path.class).invoke(factory, requested);
                    var resourceClass = Class.forName("org.eclipse.jetty.util.resource.Resource", true, context.getRequiredTestClass().getClassLoader());
                    var uri = (java.net.URI)resourceClass.getMethod("getURI").invoke(resource);
                    var realURI = (java.net.URI)resourceClass.getMethod("getRealURI").invoke(resource);
                    Object alias = resourceClass.getMethod("isAlias").invoke(resource);
                    var pathClass = Class.forName("org.eclipse.jetty.util.resource.PathResource", true, context.getRequiredTestClass().getClassLoader());
                    Object sameName = pathClass.getMethod("isSameName", Path.class, Path.class).invoke(null, requested, real);
                    System.out.printf("DIAG_ALIAS raw=%s realRaw=%s uriEquals=%s sameName=%s sameFile=%s alias=%s requested=%s realPath=%s%n",
                        uri.getRawPath(), realURI.getRawPath(), uri.equals(realURI), sameName, Files.isSameFile(requested, real), alias, requested, real);
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
        }
    }
}
```


**fileprobe.py**

```python
import ctypes as c,json,sys
from ctypes import wintypes as w
from pathlib import Path
delete=c.WinDLL("kernel32",use_last_error=True).DeleteFileW
delete.argtypes=[w.LPCWSTR]
delete.restype=w.BOOL
root=Path(sys.argv[1]).resolve()
base=Path(__file__).resolve().parent / "download-fixtures"
if not root.is_relative_to(base) or root==base:
    raise RuntimeError("Out of diagnostic directory")
for p in root.glob("tests/test-PathResponseListenerTest/file-*.bin"):
    if p.is_symlink():
        continue
    size=p.stat().st_size
    outcome=bool(delete(str(p)))
    code=0 if outcome else c.get_last_error()
    print("DIAG_DELETE_WIN32 "+json.dumps({"fixture":str(p),"size":size,"delete":outcome,"winerror":code},ensure_ascii=True))
```


### Instrumentación de la variante 8-montaje

El fixture histórico contiene target/tests anidado bajo target/isolated-downloads. Conserva el caso como control del rechazo de FS.ensureEmpty().

**PendingCondition.java**

```java
package jettypending;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.InvocationInterceptor;
import org.junit.jupiter.api.extension.ReflectiveInvocationContext;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;

public final class PendingCondition implements ExecutionCondition, InvocationInterceptor {
    private static final Map<String, Set<Integer>> SELECTED = load();
    private static final Pattern INVOCATION = Pattern.compile("\\[test-template-invocation:#(\\d+)]$");
    private static final String EXCLUDED = "pending-selection: previously complete or outside selection";

    private static Map<String, Set<Integer>> load() {
        var input = PendingCondition.class.getResourceAsStream("/META-INF/pending-cases.tsv");
        if (input == null) {
            throw new IllegalStateException("Missing pending-cases.tsv");
        }
        var table = new HashMap<String, Set<Integer>>();
        try (var reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                var fields = line.split("\\t", 2);
                table.computeIfAbsent(fields[0], ignored -> new HashSet<>()).add(Integer.parseInt(fields[1]));
            }
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        return table;
    }

    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        var method = context.getTestMethod();
        if (method.isEmpty()) {
            return ConditionEvaluationResult.enabled("test container");
        }
        String key = context.getRequiredTestClass().getName() + "#" + method.get().getName();
        var indices = SELECTED.get(key);
        if (indices == null) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        var matcher = INVOCATION.matcher(context.getUniqueId());
        if (matcher.find()) {
            int index = Integer.parseInt(matcher.group(1));
            if (!indices.contains(index)) {
                return ConditionEvaluationResult.disabled(EXCLUDED);
            }
            System.out.println("PENDING_SELECTED " + key + " #" + index);
            return ConditionEvaluationResult.enabled("pending invocation");
        }
        if (context.getUniqueId().contains("[test-template:")) {
            return ConditionEvaluationResult.enabled("template for pending invocations");
        }
        if (!indices.contains(0)) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        System.out.println("PENDING_SELECTED " + key + " #0");
        return ConditionEvaluationResult.enabled("pending method");
    }

    private static final ExtensionContext.Namespace DIAG = ExtensionContext.Namespace.create(PendingCondition.class, "diagnostics");
    private static boolean download(ExtensionContext c) {
        return c.getRequiredTestClass().getName().equals("org.eclipse.jetty.client.PathResponseListenerTest");
    }

    @Override
    public void interceptBeforeEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        if (!download(context) || !invocation.getExecutable().getName().equals("startServer")) {
            call.proceed();
            return;
        }
        // The official setup still creates and empties its directory for this invocation.
        Path parent = Files.createDirectories(Path.of(System.getProperty("jetty.diag.dir")));
        Path root = Files.createDirectories(Files.createTempDirectory(parent, context.getRequiredTestMethod().getName() + "-").resolve("target"));
        context.getStore(DIAG).put("download-root", root);
        var helper = Class.forName("org.eclipse.jetty.toolchain.test.MavenTestingUtils", true, context.getRequiredTestClass().getClassLoader());
        var target = helper.getDeclaredField("targetPath");
        target.setAccessible(true);
        var previous = target.get(null);
        target.set(null, root);
        System.out.println("DIAG_DOWNLOAD_ISOLATED " + context.getUniqueId() + " " + root);
        try {
            call.proceed();
        } finally {
            target.set(null, previous);
        }
    }

    @Override
    public void interceptAfterEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        try {
            call.proceed();
        } catch (Throwable failure) {
            if (download(context) && invocation.getExecutable().getName().equals("stopServer")) {
                try {
                    Path root = context.getStore(DIAG).get("download-root", Path.class);
                    if (root != null) {
                        var process = new ProcessBuilder(System.getProperty("jetty.diag.python"), "-X", "utf8",
                            System.getProperty("jetty.diag.fileProbe"), root.toString(), Long.toString(ProcessHandle.current().pid())).redirectErrorStream(true).start();
                        if (process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) {
                            System.out.print(new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8));
                        } else {
                            process.destroyForcibly();
                            System.out.println("DIAG_HELPER_FAILED delete probe timed out");
                        }
                    }
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
            throw failure;
        }
    }

    @Override
    public void interceptTestMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        try {
            call.proceed();
        } finally {
            if ("testUtf8Dir".equals(context.getRequiredTestMethod().getName())) {
                try {
                    Object work = invocation.getArguments().get(0);
                    Path base = (Path)work.getClass().getMethod("getPath").invoke(work);
                    Path requested = base.resolve("b\u00e3m");
                    Path real = requested.toRealPath();
                    var factoryClass = Class.forName("org.eclipse.jetty.util.resource.ResourceFactory", true, context.getRequiredTestClass().getClassLoader());
                    var factory = factoryClass.getMethod("root").invoke(null);
                    var resource = factoryClass.getMethod("newResource", Path.class).invoke(factory, requested);
                    var resourceClass = Class.forName("org.eclipse.jetty.util.resource.Resource", true, context.getRequiredTestClass().getClassLoader());
                    var uri = (java.net.URI)resourceClass.getMethod("getURI").invoke(resource);
                    var realURI = (java.net.URI)resourceClass.getMethod("getRealURI").invoke(resource);
                    Object alias = resourceClass.getMethod("isAlias").invoke(resource);
                    var pathClass = Class.forName("org.eclipse.jetty.util.resource.PathResource", true, context.getRequiredTestClass().getClassLoader());
                    Object sameName = pathClass.getMethod("isSameName", Path.class, Path.class).invoke(null, requested, real);
                    String rawComparison = real.toUri().toASCIIString();
                    if (Files.isDirectory(real) && !rawComparison.endsWith("/"))
                        rawComparison += "/";
                    var comparison = java.net.URI.create(rawComparison);
                    System.out.printf("DIAG_ALIAS requestedUri=%s comparisonUri=%s comparisonEquals=%s realRaw=%s sameName=%s sameFile=%s alias=%s%n",
                        uri, comparison, uri.equals(comparison), realURI.getRawPath(), sameName, Files.isSameFile(requested, real), alias);
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
        }
    }
}
```


**fileprobe.py**

```python
from ctypes import WinDLL, Structure, POINTER, byref, sizeof, create_unicode_buffer, c_size_t, c_void_p, get_last_error
from ctypes import wintypes as w
from collections import defaultdict
from pathlib import Path
import json, sys

class Region(Structure):
    _fields_ = [("base", c_void_p), ("allocation", c_void_p), ("protect", w.DWORD),
                ("partition", w.WORD), ("size", c_size_t), ("state", w.DWORD),
                ("current_protect", w.DWORD), ("type", w.DWORD)]

def mapped_files(pid):
    k = WinDLL("kernel32", use_last_error=True)
    p = WinDLL("psapi", use_last_error=True)
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.VirtualQueryEx.argtypes = [w.HANDLE, c_void_p, POINTER(Region), c_size_t]
    k.VirtualQueryEx.restype = c_size_t
    k.CloseHandle.argtypes = [w.HANDLE]
    p.GetMappedFileNameW.argtypes = [w.HANDLE, c_void_p, w.LPWSTR, w.DWORD]
    p.GetMappedFileNameW.restype = w.DWORD
    h = k.OpenProcess(0x0410, False, pid)
    if not h:
        return {}, get_last_error()
    results = defaultdict(list)
    try:
        address = 0
        r = Region()
        name = create_unicode_buffer(32768)
        while k.VirtualQueryEx(h, address, byref(r), sizeof(r)):
            if r.state == 0x1000 and r.type == 0x40000 and p.GetMappedFileNameW(h, r.base, name, len(name)):
                results[name.value.casefold()].append({"address": hex(r.base or 0), "size": r.size})
            next_address = (r.base or 0) + r.size
            if next_address <= address:
                break
            address = next_address
    finally:
        k.CloseHandle(h)
    return results, 0

root, pid = Path(sys.argv[1]), int(sys.argv[2])
maps, error = mapped_files(pid)
for f in sorted(root.glob("tests/**/file-*.bin")):
    suffix = str(f)[len(f.drive):].casefold()
    found = [dict(device_path=k, regions=v) for k,v in maps.items() if k.endswith(suffix)]
    print("DIAG_JVM_MAPPING " + json.dumps({"pid":pid,"fixture":str(f),"bytes":f.stat().st_size,"maps":found,"query_winerror":error}))
```


### Instrumentación de la variante 8-fix

Aplica el diff del experimento intermedio en la copia antes de verificar.

**PendingCondition.java**

```java
package jettypending;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.InvocationInterceptor;
import org.junit.jupiter.api.extension.ReflectiveInvocationContext;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;

public final class PendingCondition implements ExecutionCondition, InvocationInterceptor {
    private static final Map<String, Set<Integer>> SELECTED = load();
    private static final Pattern INVOCATION = Pattern.compile("\\[test-template-invocation:#(\\d+)]$");
    private static final String EXCLUDED = "pending-selection: previously complete or outside selection";

    private static Map<String, Set<Integer>> load() {
        var input = PendingCondition.class.getResourceAsStream("/META-INF/pending-cases.tsv");
        if (input == null) {
            throw new IllegalStateException("Missing pending-cases.tsv");
        }
        var table = new HashMap<String, Set<Integer>>();
        try (var reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                var fields = line.split("\\t", 2);
                table.computeIfAbsent(fields[0], ignored -> new HashSet<>()).add(Integer.parseInt(fields[1]));
            }
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        return table;
    }

    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        var method = context.getTestMethod();
        if (method.isEmpty()) {
            return ConditionEvaluationResult.enabled("test container");
        }
        String key = context.getRequiredTestClass().getName() + "#" + method.get().getName();
        var indices = SELECTED.get(key);
        if (indices == null) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        var matcher = INVOCATION.matcher(context.getUniqueId());
        if (matcher.find()) {
            int index = Integer.parseInt(matcher.group(1));
            if (!indices.contains(index)) {
                return ConditionEvaluationResult.disabled(EXCLUDED);
            }
            System.out.println("PENDING_SELECTED " + key + " #" + index);
            return ConditionEvaluationResult.enabled("pending invocation");
        }
        if (context.getUniqueId().contains("[test-template:")) {
            return ConditionEvaluationResult.enabled("template for pending invocations");
        }
        if (!indices.contains(0)) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        System.out.println("PENDING_SELECTED " + key + " #0");
        return ConditionEvaluationResult.enabled("pending method");
    }

    private static final ExtensionContext.Namespace DIAG = ExtensionContext.Namespace.create(PendingCondition.class, "diagnostics");
    private static boolean download(ExtensionContext c) {
        return c.getRequiredTestClass().getName().equals("org.eclipse.jetty.client.PathResponseListenerTest");
    }

    @Override
    public void interceptBeforeEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        if (!download(context) || !invocation.getExecutable().getName().equals("startServer")) {
            call.proceed();
            return;
        }
        var paths = Class.forName("org.eclipse.jetty.toolchain.test.MavenPaths", true, context.getRequiredTestClass().getClassLoader());
        Path targetTests = (Path)paths.getMethod("targetTests").invoke(null);
        Set<Path> existing;
        try (var children = Files.list(targetTests)) {
            existing = new HashSet<>(children.toList());
        }
        call.proceed();
        try (var children = Files.list(targetTests)) {
            Path fixture = children.filter(child -> !existing.contains(child))
                .filter(child -> child.getFileName().toString().startsWith("PathResponseListenerTest-"))
                .findFirst().orElseThrow();
            if (!fixture.toRealPath().startsWith(targetTests.toRealPath()))
                throw new IllegalStateException("Fixture rejected by Surefire target/tests boundary");
            context.getStore(DIAG).put("download-root", fixture);
            System.out.println("DIAG_DOWNLOAD_ROOT targetTests=" + targetTests + " fixture=" + fixture);
        }
    }

    @Override
    public void interceptAfterEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        try {
            call.proceed();
            if (download(context) && invocation.getExecutable().getName().equals("stopServer")) {
                Path fixture = context.getStore(DIAG).get("download-root", Path.class);
                if (fixture != null) {
                    long entries = 0;
                    if (Files.isDirectory(fixture)) {
                        try (var files = Files.list(fixture)) { entries = files.count(); }
                    }
                    System.out.println("DIAG_DOWNLOAD_CLEANUP official=passed entries=" + entries + " fixture=" + fixture);
                }
            }
        } catch (Throwable failure) {
            if (download(context) && invocation.getExecutable().getName().equals("stopServer")) {
                try {
                    Path root = context.getStore(DIAG).get("download-root", Path.class);
                    if (root != null) {
                        System.out.println("DIAG_DOWNLOAD_CLEANUP official=failed cause=" + failure);
                        var process = new ProcessBuilder(System.getProperty("jetty.diag.python"), "-X", "utf8",
                            System.getProperty("jetty.diag.fileProbe"), root.toString(), Long.toString(ProcessHandle.current().pid())).redirectErrorStream(true).start();
                        if (process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) {
                            System.out.print(new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8));
                        } else {
                            process.destroyForcibly();
                            System.out.println("DIAG_HELPER_FAILED delete probe timed out");
                        }
                    }
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
            throw failure;
        }
    }

    @Override
    public void interceptTestMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        try {
            call.proceed();
        } finally {
            if ("testUtf8Dir".equals(context.getRequiredTestMethod().getName())) {
                try {
                    Object work = invocation.getArguments().get(0);
                    Path base = (Path)work.getClass().getMethod("getPath").invoke(work);
                    Path requested = base.resolve("b\u00e3m");
                    Path real = requested.toRealPath();
                    var factoryClass = Class.forName("org.eclipse.jetty.util.resource.ResourceFactory", true, context.getRequiredTestClass().getClassLoader());
                    var factory = factoryClass.getMethod("root").invoke(null);
                    var resource = factoryClass.getMethod("newResource", Path.class).invoke(factory, requested);
                    var resourceClass = Class.forName("org.eclipse.jetty.util.resource.Resource", true, context.getRequiredTestClass().getClassLoader());
                    var uri = (java.net.URI)resourceClass.getMethod("getURI").invoke(resource);
                    var realURI = (java.net.URI)resourceClass.getMethod("getRealURI").invoke(resource);
                    Object alias = resourceClass.getMethod("isAlias").invoke(resource);
                    var pathClass = Class.forName("org.eclipse.jetty.util.resource.PathResource", true, context.getRequiredTestClass().getClassLoader());
                    Object sameName = pathClass.getMethod("isSameName", Path.class, Path.class).invoke(null, requested, real);
                    String rawComparison = real.toUri().toASCIIString();
                    if (Files.isDirectory(real) && !rawComparison.endsWith("/"))
                        rawComparison += "/";
                    var comparison = java.net.URI.create(rawComparison);
                    System.out.printf("DIAG_ALIAS requestedUri=%s comparisonUri=%s comparisonEquals=%s realRaw=%s sameName=%s sameFile=%s alias=%s%n",
                        uri, comparison, uri.equals(comparison), realURI.getRawPath(), sameName, Files.isSameFile(requested, real), alias);
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
        }
    }
}
```


**fileprobe.py**

```python
from ctypes import WinDLL, Structure, POINTER, byref, sizeof, create_unicode_buffer, c_size_t, c_void_p, get_last_error
from ctypes import wintypes as w
from collections import defaultdict
from pathlib import Path
import json, sys

class Region(Structure):
    _fields_ = [("base", c_void_p), ("allocation", c_void_p), ("protect", w.DWORD),
                ("partition", w.WORD), ("size", c_size_t), ("state", w.DWORD),
                ("current_protect", w.DWORD), ("type", w.DWORD)]

def mapped_files(pid):
    k = WinDLL("kernel32", use_last_error=True)
    p = WinDLL("psapi", use_last_error=True)
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.VirtualQueryEx.argtypes = [w.HANDLE, c_void_p, POINTER(Region), c_size_t]
    k.VirtualQueryEx.restype = c_size_t
    k.CloseHandle.argtypes = [w.HANDLE]
    p.GetMappedFileNameW.argtypes = [w.HANDLE, c_void_p, w.LPWSTR, w.DWORD]
    p.GetMappedFileNameW.restype = w.DWORD
    h = k.OpenProcess(0x0410, False, pid)
    if not h:
        return {}, get_last_error()
    results = defaultdict(list)
    try:
        address = 0
        r = Region()
        name = create_unicode_buffer(32768)
        while k.VirtualQueryEx(h, address, byref(r), sizeof(r)):
            if r.state == 0x1000 and r.type == 0x40000 and p.GetMappedFileNameW(h, r.base, name, len(name)):
                results[name.value.casefold()].append({"address": hex(r.base or 0), "size": r.size})
            next_address = (r.base or 0) + r.size
            if next_address <= address:
                break
            address = next_address
    finally:
        k.CloseHandle(h)
    return results, 0

root, pid = Path(sys.argv[1]), int(sys.argv[2])
maps, error = mapped_files(pid)
for f in sorted(root.glob("file-*.bin")):
    suffix = str(f)[len(f.drive):].casefold()
    found = [dict(device_path=k, regions=v) for k,v in maps.items() if k.endswith(suffix)]
    print("DIAG_JVM_MAPPING " + json.dumps({"pid":pid,"fixture":str(f),"bytes":f.stat().st_size,"maps":found,"query_winerror":error}))
```


### Instrumentación de la variante final

Aplica el diff final en una copia limpia. La condición conserva el teardown oficial y usa la sonda para observar la liberación antes del borrado.

**PendingCondition.java**

```java
package jettypending;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.InvocationInterceptor;
import org.junit.jupiter.api.extension.ReflectiveInvocationContext;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;

public final class PendingCondition implements ExecutionCondition, InvocationInterceptor {
    private static final Map<String, Set<Integer>> SELECTED = load();
    private static final Pattern INVOCATION = Pattern.compile("\\[test-template-invocation:#(\\d+)]$");
    private static final String EXCLUDED = "pending-selection: previously complete or outside selection";

    private static Map<String, Set<Integer>> load() {
        var input = PendingCondition.class.getResourceAsStream("/META-INF/pending-cases.tsv");
        if (input == null) {
            throw new IllegalStateException("Missing pending-cases.tsv");
        }
        var table = new HashMap<String, Set<Integer>>();
        try (var reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                var fields = line.split("\\t", 2);
                table.computeIfAbsent(fields[0], ignored -> new HashSet<>()).add(Integer.parseInt(fields[1]));
            }
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        return table;
    }

    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        var method = context.getTestMethod();
        if (method.isEmpty()) {
            return ConditionEvaluationResult.enabled("test container");
        }
        String key = context.getRequiredTestClass().getName() + "#" + method.get().getName();
        var indices = SELECTED.get(key);
        if (indices == null) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        var matcher = INVOCATION.matcher(context.getUniqueId());
        if (matcher.find()) {
            int index = Integer.parseInt(matcher.group(1));
            if (!indices.contains(index)) {
                return ConditionEvaluationResult.disabled(EXCLUDED);
            }
            System.out.println("PENDING_SELECTED " + key + " #" + index);
            return ConditionEvaluationResult.enabled("pending invocation");
        }
        if (context.getUniqueId().contains("[test-template:")) {
            return ConditionEvaluationResult.enabled("template for pending invocations");
        }
        if (!indices.contains(0)) {
            return ConditionEvaluationResult.disabled(EXCLUDED);
        }
        System.out.println("PENDING_SELECTED " + key + " #0");
        return ConditionEvaluationResult.enabled("pending method");
    }

    private static final ExtensionContext.Namespace DIAG = ExtensionContext.Namespace.create(PendingCondition.class, "diagnostics");
    private static boolean download(ExtensionContext c) {
        return c.getRequiredTestClass().getName().equals("org.eclipse.jetty.client.PathResponseListenerTest");
    }

    @Override
    public void interceptBeforeEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        if (!download(context) || !invocation.getExecutable().getName().equals("startServer")) {
            call.proceed();
            return;
        }
        var paths = Class.forName("org.eclipse.jetty.toolchain.test.MavenPaths", true, context.getRequiredTestClass().getClassLoader());
        Path targetTests = (Path)paths.getMethod("targetTests").invoke(null);
        Set<Path> existing;
        try (var children = Files.list(targetTests)) {
            existing = new HashSet<>(children.toList());
        }
        call.proceed();
        try (var children = Files.list(targetTests)) {
            Path fixture = children.filter(child -> !existing.contains(child))
                .filter(child -> child.getFileName().toString().startsWith("PathResponseListenerTest-"))
                .findFirst().orElseThrow();
            if (!fixture.toRealPath().startsWith(targetTests.toRealPath()))
                throw new IllegalStateException("Fixture rejected by Surefire target/tests boundary");
            context.getStore(DIAG).put("download-root", fixture);
            System.out.println("DIAG_DOWNLOAD_ROOT targetTests=" + targetTests + " fixture=" + fixture);
        }
    }

    private static int sampleMappings(Path fixture, String phase) throws Exception {
        var process = new ProcessBuilder(System.getProperty("jetty.diag.python"), "-X", "utf8",
            System.getProperty("jetty.diag.fileProbe"), fixture.toString(),
            Long.toString(ProcessHandle.current().pid()), phase).redirectErrorStream(true).start();
        if (!process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) {
            process.destroyForcibly();
            System.out.println("DIAG_MAPPING_PROBE timeout phase=" + phase);
            return 3;
        }
        System.out.print(new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8));
        return process.exitValue();
    }

    @Override
    public void interceptAfterEachMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        if (!download(context) || !invocation.getExecutable().getName().equals("stopServer")) {
            call.proceed();
            return;
        }
        Path fixture = context.getStore(DIAG).get("download-root", Path.class);
        if (fixture != null) {
            try {
                int before = sampleMappings(fixture, "before-release");
                context.getRequiredTestClass().getMethod("releaseServerContent").invoke(context.getRequiredTestInstance());
                int current = sampleMappings(fixture, "after-stop-and-cache-flush");
                long deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(8);
                for (int attempt = 1; current == 2 && System.nanoTime() < deadline; attempt++) {
                    // Test fixture only. MappedByteBuffer on Java 17 has no portable close operation.
                    System.gc();
                    current = sampleMappings(fixture, "after-gc-" + attempt);
                }
                System.out.println("DIAG_MAPPING_RELEASE before=" + before + " beforeOfficialDelete=" + current);
            } catch (Exception diagnosticError) {
                System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                if (diagnosticError.getCause() != null)
                    System.out.println("DIAG_HELPER_CAUSE " + diagnosticError.getCause());
            }
        }
        try {
            call.proceed();
        } catch (Throwable failure) {
            System.out.println("DIAG_DOWNLOAD_CLEANUP official=failed cause=" + failure);
            if (fixture != null) {
                try {
                    sampleMappings(fixture, "after-official-delete-failure");
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
            throw failure;
        }
        if (fixture != null) {
            long entries = 0;
            if (Files.isDirectory(fixture)) {
                try (var files = Files.list(fixture)) { entries = files.count(); }
            }
            System.out.println("DIAG_DOWNLOAD_CLEANUP official=passed entries=" + entries + " fixture=" + fixture);
        }
    }

    @Override
    public void interceptTestMethod(Invocation<Void> call, ReflectiveInvocationContext<Method> invocation, ExtensionContext context) throws Throwable {
        try {
            call.proceed();
        } finally {
            if ("testUtf8Dir".equals(context.getRequiredTestMethod().getName())) {
                try {
                    Object work = invocation.getArguments().get(0);
                    Path base = (Path)work.getClass().getMethod("getPath").invoke(work);
                    Path requested = base.resolve("b\u00e3m");
                    Path real = requested.toRealPath();
                    var factoryClass = Class.forName("org.eclipse.jetty.util.resource.ResourceFactory", true, context.getRequiredTestClass().getClassLoader());
                    var factory = factoryClass.getMethod("root").invoke(null);
                    var resource = factoryClass.getMethod("newResource", Path.class).invoke(factory, requested);
                    var resourceClass = Class.forName("org.eclipse.jetty.util.resource.Resource", true, context.getRequiredTestClass().getClassLoader());
                    var uri = (java.net.URI)resourceClass.getMethod("getURI").invoke(resource);
                    var realURI = (java.net.URI)resourceClass.getMethod("getRealURI").invoke(resource);
                    Object alias = resourceClass.getMethod("isAlias").invoke(resource);
                    Object child = resourceClass.getMethod("resolve", String.class).invoke(resource, "file.txt");
                    System.out.printf("DIAG_CHILD uri=%s realUri=%s alias=%s%n", resourceClass.getMethod("getURI").invoke(child), resourceClass.getMethod("getRealURI").invoke(child), resourceClass.getMethod("isAlias").invoke(child));
                    var pathClass = Class.forName("org.eclipse.jetty.util.resource.PathResource", true, context.getRequiredTestClass().getClassLoader());
                    Object sameName = pathClass.getMethod("isSameName", Path.class, Path.class).invoke(null, requested, real);
                    String rawComparison = real.toUri().toASCIIString();
                    if (Files.isDirectory(real) && !rawComparison.endsWith("/"))
                        rawComparison += "/";
                    var comparison = java.net.URI.create(rawComparison);
                    System.out.printf("DIAG_ALIAS requestedUri=%s comparisonUri=%s comparisonEquals=%s realRaw=%s sameName=%s sameFile=%s alias=%s%n",
                        uri, comparison, uri.equals(comparison), realURI.getRawPath(), sameName, Files.isSameFile(requested, real), alias);
                } catch (Exception diagnosticError) {
                    System.out.println("DIAG_HELPER_FAILED " + diagnosticError);
                }
            }
        }
    }
}
```


**fileprobe.py**

```python
from ctypes import WinDLL, Structure, POINTER, byref, sizeof, create_unicode_buffer, c_size_t, c_void_p, get_last_error
from ctypes import wintypes as w
from collections import defaultdict
from pathlib import Path
import json, sys

class Region(Structure):
    _fields_ = [("base", c_void_p), ("allocation", c_void_p), ("protect", w.DWORD),
                ("partition", w.WORD), ("size", c_size_t), ("state", w.DWORD),
                ("current_protect", w.DWORD), ("type", w.DWORD)]

def mapped_files(pid):
    k = WinDLL("kernel32", use_last_error=True)
    p = WinDLL("psapi", use_last_error=True)
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.VirtualQueryEx.argtypes = [w.HANDLE, c_void_p, POINTER(Region), c_size_t]
    k.VirtualQueryEx.restype = c_size_t
    k.CloseHandle.argtypes = [w.HANDLE]
    p.GetMappedFileNameW.argtypes = [w.HANDLE, c_void_p, w.LPWSTR, w.DWORD]
    p.GetMappedFileNameW.restype = w.DWORD
    h = k.OpenProcess(0x0410, False, pid)
    if not h:
        return {}, get_last_error()
    results = defaultdict(list)
    try:
        address = 0
        r = Region()
        name = create_unicode_buffer(32768)
        while k.VirtualQueryEx(h, address, byref(r), sizeof(r)):
            if r.state == 0x1000 and r.type == 0x40000 and p.GetMappedFileNameW(h, r.base, name, len(name)):
                results[name.value.casefold()].append({"address": hex(r.base or 0), "size": r.size})
            next_address = (r.base or 0) + r.size
            if next_address <= address:
                break
            address = next_address
    finally:
        k.CloseHandle(h)
    return results, 0

root, pid, phase = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
maps, error = mapped_files(pid)
fixtures = sorted(root.glob("file-*.bin"))
any_mapped = False
for f in fixtures:
    suffix = str(f)[len(f.drive):].casefold()
    found = [dict(device_path=k, regions=v) for k,v in maps.items() if k.endswith(suffix)]
    any_mapped |= bool(found)
    print("DIAG_JVM_MAPPING " + json.dumps({"phase":phase,"pid":pid,"fixture":str(f),"bytes":f.stat().st_size,"maps":found,"query_winerror":error}))

sys.exit(3 if error or not fixtures else 2 if any_mapped else 0)
```


### Diff experimental intermedio

Guarda el bloque como experimento.patch con UTF-8 sin BOM y aplícalo solo en la copia de pruebas. Usa una copia limpia por cada diff.

```diff
diff --git a/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java b/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java
index fe71363..41b13c3 100644
--- a/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java
+++ b/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java
@@ -13,7 +13,6 @@
 
 package org.eclipse.jetty.client.transport.internal;
 
-import java.io.EOFException;
 import java.nio.ByteBuffer;
 import java.util.concurrent.atomic.LongAdder;
 
@@ -33,6 +32,7 @@ import org.eclipse.jetty.http.HttpVersion;
 import org.eclipse.jetty.io.ByteBufferPool;
 import org.eclipse.jetty.io.Content;
 import org.eclipse.jetty.io.EndPoint;
+import org.eclipse.jetty.io.EofException;
 import org.eclipse.jetty.io.RetainableByteBuffer;
 import org.eclipse.jetty.util.BufferUtil;
 import org.eclipse.jetty.util.Callback;
@@ -553,7 +553,7 @@ public class HttpReceiverOverHTTP extends HttpReceiver implements HttpParser.Res
         if (exchange == null || unsolicited)
             connection.close();
         else
-            failAndClose(new EOFException(String.valueOf(connection)));
+            failAndClose(new EofException(String.valueOf(connection)));
     }
 
     @Override
diff --git a/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java b/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java
index d5a4a7b..c447561 100644
--- a/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java
+++ b/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java
@@ -27,7 +27,7 @@ import org.eclipse.jetty.server.Server;
 import org.eclipse.jetty.server.ServerConnector;
 import org.eclipse.jetty.server.handler.ResourceHandler;
 import org.eclipse.jetty.toolchain.test.FS;
-import org.eclipse.jetty.toolchain.test.MavenTestingUtils;
+import org.eclipse.jetty.toolchain.test.MavenPaths;
 import org.eclipse.jetty.util.component.LifeCycle;
 import org.eclipse.jetty.util.resource.ResourceFactory;
 import org.eclipse.jetty.util.thread.QueuedThreadPool;
@@ -52,7 +52,7 @@ public class PathResponseListenerTest
         serverThreads.setName("server");
         server = new Server(serverThreads);
         ResourceHandler resourceHandler = new ResourceHandler();
-        resourceDir = MavenTestingUtils.getTargetTestingPath(PathResponseListenerTest.class.getSimpleName());
+        resourceDir = Files.createTempDirectory(MavenPaths.targetTests(), "PathResponseListenerTest-");
         FS.ensureEmpty(resourceDir);
         resourceHandler.setBaseResource(ResourceFactory.of(server).newResource(resourceDir));
         resourceHandler.setDirAllowed(false);
diff --git a/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java b/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java
index 124a0bd..bc2c176 100644
--- a/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java
+++ b/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java
@@ -119,6 +119,9 @@ public class HTTP2ServerSession extends HTTP2Session implements ServerParser.Lis
                         Throwable metaDataFailure = MetaData.Failed.getFailure(metaData);
                         if (metaDataFailure != null)
                         {
+                            // Carry the wire EOF through the bad request path, which skips normal HEADERS processing.
+                            if (frame.isEndStream())
+                                stream.process(Stream.Data.eof(streamId));
                             // It's a bad request, request content will be dropped.
                             stream.updateClose(true, CloseState.Event.RECEIVED);
                             notifyStreamFailure(stream, new HttpException.RuntimeException(HttpStatus.BAD_REQUEST_400, metaDataFailure.getMessage(), metaDataFailure), Callback.NOOP);
diff --git a/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java b/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java
index af9571f..f47149c 100644
--- a/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java
+++ b/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java
@@ -540,7 +540,12 @@ public class PathResource extends Resource
              *  child.getPath().toUri()       == "file:///C:/temp/aa/foo.txt"
              *  child.getRealURI()            == "file:///C:/temp/aa/foo.txt"
              */
-            alias = !isSameName(path, realPath) || !Objects.equals(uri, toUri(realPath));
+            URI realUri = toUri(realPath);
+            URI requestedUri = uri;
+            // Directory paths from Windows may use raw non-ASCII characters.
+            if (!uri.equals(realUri) && Files.isDirectory(realPath))
+                requestedUri = URI.create(uri.toASCIIString());
+            alias = !isSameName(path, realPath) || !requestedUri.equals(realUri);
         }
     }
 
diff --git a/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java b/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java
index 6302233..5e77fcb 100644
--- a/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java
+++ b/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java
@@ -540,11 +540,11 @@ public class CoreMultiPartTest
                 for (MultiPart.Part part : getParts(request, config))
                 {
                     String partContent = IO.toString(Content.Source.asInputStream(part.createContentSource()));
-                    writer.println("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent);
+                    writer.print("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent + "\n");
 
                     // We can only consume the getContentSource() once so we must use newContentSource().
                     partContent = IO.toString(Content.Source.asInputStream(part.createContentSource()));
-                    writer.println("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent);
+                    writer.print("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent + "\n");
                 }
 
                 writer.close();
```


### Diff experimental final

Guarda el bloque como experimento.patch con UTF-8 sin BOM y aplícalo solo en la copia de pruebas. Usa una copia limpia por cada diff.

```diff
diff --git a/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java b/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java
index fe71363..41b13c3 100644
--- a/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java
+++ b/jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/transport/internal/HttpReceiverOverHTTP.java
@@ -13,7 +13,6 @@
 
 package org.eclipse.jetty.client.transport.internal;
 
-import java.io.EOFException;
 import java.nio.ByteBuffer;
 import java.util.concurrent.atomic.LongAdder;
 
@@ -33,6 +32,7 @@ import org.eclipse.jetty.http.HttpVersion;
 import org.eclipse.jetty.io.ByteBufferPool;
 import org.eclipse.jetty.io.Content;
 import org.eclipse.jetty.io.EndPoint;
+import org.eclipse.jetty.io.EofException;
 import org.eclipse.jetty.io.RetainableByteBuffer;
 import org.eclipse.jetty.util.BufferUtil;
 import org.eclipse.jetty.util.Callback;
@@ -553,7 +553,7 @@ public class HttpReceiverOverHTTP extends HttpReceiver implements HttpParser.Res
         if (exchange == null || unsolicited)
             connection.close();
         else
-            failAndClose(new EOFException(String.valueOf(connection)));
+            failAndClose(new EofException(String.valueOf(connection)));
     }
 
     @Override
diff --git a/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java b/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java
index d5a4a7b..1d7f861 100644
--- a/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java
+++ b/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/PathResponseListenerTest.java
@@ -23,11 +23,12 @@ import java.nio.file.StandardOpenOption;
 import java.util.concurrent.ThreadLocalRandom;
 import java.util.concurrent.TimeUnit;
 
+import org.eclipse.jetty.http.content.CachingHttpContentFactory;
 import org.eclipse.jetty.server.Server;
 import org.eclipse.jetty.server.ServerConnector;
 import org.eclipse.jetty.server.handler.ResourceHandler;
 import org.eclipse.jetty.toolchain.test.FS;
-import org.eclipse.jetty.toolchain.test.MavenTestingUtils;
+import org.eclipse.jetty.toolchain.test.MavenPaths;
 import org.eclipse.jetty.util.component.LifeCycle;
 import org.eclipse.jetty.util.resource.ResourceFactory;
 import org.eclipse.jetty.util.thread.QueuedThreadPool;
@@ -52,7 +53,7 @@ public class PathResponseListenerTest
         serverThreads.setName("server");
         server = new Server(serverThreads);
         ResourceHandler resourceHandler = new ResourceHandler();
-        resourceDir = MavenTestingUtils.getTargetTestingPath(PathResponseListenerTest.class.getSimpleName());
+        resourceDir = Files.createTempDirectory(MavenPaths.targetTests(), "PathResponseListenerTest-");
         FS.ensureEmpty(resourceDir);
         resourceHandler.setBaseResource(ResourceFactory.of(server).newResource(resourceDir));
         resourceHandler.setDirAllowed(false);
@@ -69,6 +70,15 @@ public class PathResponseListenerTest
         LifeCycle.stop(server);
     }
 
+    // The diagnostic calls this before the original teardown to release cache references.
+    public void releaseServerContent() throws Exception
+    {
+        LifeCycle.stop(server);
+        ResourceHandler handler = (ResourceHandler)server.getHandler();
+        if (handler.getHttpContentFactory() instanceof CachingHttpContentFactory cache)
+            cache.flushCache();
+    }
+
     private Path createServerFile(int length) throws IOException
     {
         Path path = Files.createTempFile(resourceDir, "file-", ".bin");
diff --git a/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/http/HttpReceiverOverHTTPTest.java b/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/http/HttpReceiverOverHTTPTest.java
index c2a7cea..b3cad48 100644
--- a/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/http/HttpReceiverOverHTTPTest.java
+++ b/jetty-core/jetty-client/src/test/java/org/eclipse/jetty/client/http/HttpReceiverOverHTTPTest.java
@@ -40,8 +40,10 @@ import org.eclipse.jetty.http.HttpFields;
 import org.eclipse.jetty.http.HttpHeader;
 import org.eclipse.jetty.http.HttpVersion;
 import org.eclipse.jetty.io.ByteArrayEndPoint;
+import org.eclipse.jetty.io.EofException;
 import org.eclipse.jetty.util.Promise;
 import org.junit.jupiter.api.AfterEach;
+import org.junit.jupiter.api.Test;
 import org.junit.jupiter.params.ParameterizedTest;
 import org.junit.jupiter.params.provider.Arguments;
 import org.junit.jupiter.params.provider.MethodSource;
@@ -167,6 +169,18 @@ public class HttpReceiverOverHTTPTest
         assertEquals(content, received);
     }
 
+    @Test
+    public void testEOFBeforeResponseStatus() throws Exception
+    {
+        init(HttpCompliance.RFC7230);
+        CompletableFuture<ContentResponse> response = startExchange();
+        endPoint.addInputEOF();
+        connection.getHttpChannel().receive();
+
+        ExecutionException failure = assertThrows(ExecutionException.class, () -> response.get(5, TimeUnit.SECONDS));
+        assertEquals(EofException.class, failure.getCause().getClass());
+    }
+
     @ParameterizedTest
     @MethodSource("complianceModes")
     public void testReceiveResponseContentEarlyEOF(HttpCompliance compliance) throws Exception
diff --git a/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java b/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java
index 124a0bd..bc2c176 100644
--- a/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java
+++ b/jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java
@@ -119,6 +119,9 @@ public class HTTP2ServerSession extends HTTP2Session implements ServerParser.Lis
                         Throwable metaDataFailure = MetaData.Failed.getFailure(metaData);
                         if (metaDataFailure != null)
                         {
+                            // Carry the wire EOF through the bad request path, which skips normal HEADERS processing.
+                            if (frame.isEndStream())
+                                stream.process(Stream.Data.eof(streamId));
                             // It's a bad request, request content will be dropped.
                             stream.updateClose(true, CloseState.Event.RECEIVED);
                             notifyStreamFailure(stream, new HttpException.RuntimeException(HttpStatus.BAD_REQUEST_400, metaDataFailure.getMessage(), metaDataFailure), Callback.NOOP);
diff --git a/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java b/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java
index af9571f..04ad42c 100644
--- a/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java
+++ b/jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java
@@ -13,9 +13,11 @@
 
 package org.eclipse.jetty.util.resource;
 
+import java.io.File;
 import java.io.IOException;
 import java.net.URI;
 import java.nio.file.DirectoryIteratorException;
+import java.nio.file.FileSystems;
 import java.nio.file.Files;
 import java.nio.file.LinkOption;
 import java.nio.file.Path;
@@ -540,7 +542,15 @@ public class PathResource extends Resource
              *  child.getPath().toUri()       == "file:///C:/temp/aa/foo.txt"
              *  child.getRealURI()            == "file:///C:/temp/aa/foo.txt"
              */
-            alias = !isSameName(path, realPath) || !Objects.equals(uri, toUri(realPath));
+            URI realUri = toUri(realPath);
+            URI requestedUri = uri;
+            // Directory paths from Windows may use raw non-ASCII characters.
+            if (!uri.equals(realUri) && Files.isDirectory(realPath))
+                requestedUri = URI.create(uri.toASCIIString());
+            else if (File.separatorChar == '\\' && realPath.getFileSystem() == FileSystems.getDefault() && !Files.isDirectory(realPath))
+                // Keep the native URI for files so an encoded request is still checked for aliasing.
+                realUri = realPath.toUri();
+            alias = !isSameName(path, realPath) || !requestedUri.equals(realUri);
         }
     }
 
diff --git a/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java b/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java
index 6302233..5e77fcb 100644
--- a/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java
+++ b/tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java
@@ -540,11 +540,11 @@ public class CoreMultiPartTest
                 for (MultiPart.Part part : getParts(request, config))
                 {
                     String partContent = IO.toString(Content.Source.asInputStream(part.createContentSource()));
-                    writer.println("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent);
+                    writer.print("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent + "\n");
 
                     // We can only consume the getContentSource() once so we must use newContentSource().
                     partContent = IO.toString(Content.Source.asInputStream(part.createContentSource()));
-                    writer.println("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent);
+                    writer.print("Part: name=" + part.getName() + ", size=" + part.getLength() + ", content=" + partContent + "\n");
                 }
 
                 writer.close();
```

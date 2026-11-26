# Jetty Core consolidado 12.1.15

Este proyecto Maven compila en un único JAR las fuentes de los 14 módulos seleccionados del tag `jetty-12.1.15`, commit `770f5e4d1c39673d6356163118a1e6bf1117ced3`. Es un componente local basado en Jetty y conserva los paquetes `org.eclipse.jetty.*`. Su POM y sus fuentes son independientes del checkout hermano.

## Compilar y consumir

Con Maven 3.9.12 y JDK 17, desde este directorio:

```powershell
$repo = Join-Path $env:LOCALAPPDATA 'JettyCoreConsolidated\m2'
mvn -B "-Dmaven.repo.local=$repo" clean verify
mvn -B "-Dmaven.repo.local=$repo" -DskipTests install
```

La instalación de este artefacto no implica aceptar fallos de pruebas. Revisa los XML de la primera corrida antes de usar el JAR. Si Maven no publica un auxiliar de pruebas, construye primero el reactor upstream del mismo commit con la guía de verificación y prepara un repositorio aislado con los auxiliares. La preparación se puede reproducir con `python verification/seed-test-repository.py <reactor-upstream-compilado> <repositorio-aislado>`. El script excluye los JAR originales de los módulos seleccionados y conserva los auxiliares de prueba. Las dependencias auxiliares se declaran con alcance `test`; el POM publicado requiere SLF4J y permite añadir JMX opcionalmente. El proyecto consumidor debe usar el mismo repositorio local o un repositorio donde se haya publicado el artefacto. También se puede instalar directamente el JAR verificado, con el POM adjunto:

```powershell
mvn -B "-Dmaven.repo.local=$repo" org.apache.maven.plugins:maven-install-plugin:3.1.4:install-file `
    "-Dfile=target/jetty-core-consolidated-12.1.15.jar" "-DpomFile=pom.xml"
```

```xml
<dependency>
    <groupId>com.example</groupId>
    <artifactId>jetty-core-consolidated</artifactId>
    <version>12.1.15</version>
</dependency>
```

No combines este artefacto con los JAR originales de los 14 componentes. Si un cliente u otro auxiliar Jetty los trae transitivamente, exclúyelos del grafo consumidor. Para JMX opcional, declara `org.eclipse.jetty:jetty-jmx:12.1.15` con exclusión de `org.eclipse.jetty:jetty-util` y úsalo en el classpath. El proveedor SLF4J lo elige el consumidor. Si la aplicación requiere MDC, usa un backend que lo implemente.

## Empaquetado

- `src/main/java` contiene las fuentes de Jetty. [Inventario de origen](upstream/source-inventory.json) registra módulo, ruta y SHA-256 de cada archivo copiado. No se relocalizan paquetes.
- `META-INF/services` reúne ALPN Java, gzip y los preencoders HTTP/1.0, HTTP/1.1 y HPACK. El manifiesto fija el nombre automático `com.example.jetty.core.consolidated`, los metadatos OSGi para el nuevo bundle y el commit de origen. `org/eclipse/jetty/version/build.properties` contiene la versión y el commit de Jetty.
- Un JAR solo puede definir una identidad JPMS. Los 14 descriptores originales quedan en `upstream/descriptors` como referencia. Los consumidores que usan `requires` deben usar el nuevo nombre. Los límites de exportación de los módulos originales y su resolución simultánea quedan fuera de esa compatibilidad. No se verificó un despliegue OSGi ni JMX sobre el module path.
- Los recursos de distribución se conservan como plantillas en `META-INF/jetty/config` y se excluyen los keystores de prueba, como en el reactor original. Las plantillas conservan referencias upstream. Para el consumo previsto se configuran conectores y handlers mediante Java; usar `start.jar` y reproducir una distribución Jetty completa requiere su propio ensamblaje.
- `LICENSE` y `NOTICE.txt` de Jetty se conservan en el proyecto y se incluyen en `META-INF`. El POM declara EPL 2.0 y Apache 2.0.

## Cómo se ejecutan las pruebas

El perfil predeterminado `upstream-tests` conserva las fuentes, los fixtures y las aserciones de las 11 suites propias con tests y de las seis suites compartidas que figuran en el inventario. Los dos auxiliares de fixtures no publicados como parte de este núcleo se compilan solo para las pruebas. Las suites se ejecutan en forks separados y usan directorios de trabajo separados en `target/fixtures` para mantener el `target/tests` efectivo y evitar colisiones como `keystore.p12`, `example.jar` y `jetty-logging.properties`. Un listener de sesión JUnit, exclusivo de las pruebas, vincula el directorio efectivo antes del descubrimiento. Surefire repone `basedir` y las utilidades upstream usan tanto `basedir` como `project.basedir` para resolver los fixtures. Se usa el classpath de pruebas consolidado. Los auxiliares Jetty de prueba excluyen las dependencias de los 14 módulos originales. El montaje copia el XML oficial de apagado a la ruta que usa la suite de servidor y expone los paquetes compilados de util en el `target/classes` de su fixture para el proceso hijo de `PasswordTest`. La suite de integración recibe un `test-classes` propio que reúne sus clases y fixtures. Las pruebas de alias resuelven la raíz mediante `getResource(".")` y necesitan encontrarlos juntos.

El perfil `focused-tests` permite elegir el directorio del fixture con `-Djetty.test.fixture=…` y una selección Surefire con `-Dtest=…`. Los resultados están en `target/surefire-reports/<suite>/` o `target/surefire-reports/focused-<suite>/`. Contrasta `java.version` y `java.home` de los XML con `mvn -version`. Si usas `-Dmaven.test.failure.ignore=true` para recopilar informes de todas las suites, Maven puede terminar con código 0 aunque Surefire haya registrado fallos.

### Corrida de referencia con JDK 17

En Windows, Maven 3.9.12 usó JDK 17.0.11. El fork paralelo inicial quedó esperando en el cierre del selector durante una prueba TLS. La verificación que terminó usó ejecución secuencial y límites de espera de JUnit. Las fuentes y las aserciones oficiales se conservan.

```powershell
mvn -B "-Dmaven.repo.local=$repo" '-Djunit.jupiter.execution.parallel.enabled=false' `
    '-Djunit.jupiter.execution.timeout.aftereach.method.default=60 s' `
    '-Djunit.jupiter.execution.timeout.test.method.default=120 s' `
    '-Djunit.jupiter.execution.timeout.testtemplate.method.default=120 s' `
    '-Dmaven.test.failure.ignore=true' verify
```

Usa `maven.test.failure.ignore=true` solo para reunir evidencia de las 17 suites en la misma corrida. El registro de Maven y los XML distinguen la ejecución del ciclo del resultado de cada prueba. Para que un fallo detenga la compilación, omite esa opción.

La corrida completa terminó con código 0 y 17.489 invocaciones registradas por Surefire. El recuento original fue de 17.138 aprobadas, 84 fallos de aserción, 6 errores y 261 omisiones. Después del ajuste de fixtures se repitieron solo los casos afectados. `ShutdownServiceTest#testShutdownXml` y `PasswordTest#testCommandLineUsage` pasaron. En integración, sus 133 casos terminaron con 132 aprobados y un fallo de saltos de línea en `CoreMultiPartTest#testDoubleReadFromPart`. Al sustituir estos resultados en el recuento, quedan 17.219 aprobadas, 6 fallos de aserción, 3 errores y 261 omisiones. El recuento final combina la corrida general y las repeticiones focalizadas.

- La línea base oficial ya registraba fallos de `ConcurrentRequestsTest`, `testUtf8Dir`, `QueuedThreadPoolTest#testMaxStopTime`, `MinimumDataRateHandlerTest#testMinimumDataWriteRateWithSingleLastWrite`, `FormTest[8]` y multipart.
- `LargeHeaderTest#testLargeHeaderNewConnectionsConcurrent` registró un reset TCP en la corrida general. Pasó al ejecutarlo por separado en ambas versiones, igual que los cuatro casos TLS de `testHoldContent` implicados en el bloqueo inicial.
- El H2C de `HttpClientStreamTest#testDownloadWithFailure[3]` registró `ClosedChannelException`. La repetición con las mismas condiciones en ambas versiones reprodujo la excepción. El reactor original también la registró en su variante TLS `[4]`.
- Las omisiones de JDK 17 se conservan con su motivo en XML. Linux, FFM, una distribución `start.jar` y la ejecución OSGi están fuera de las comprobaciones realizadas.

[Resumen por ejecución y suite](verification/results/test-summary.json) · [XML de Surefire con JDK 17](verification/results/surefire-jdk17.zip) · [Log de verify](verification/results/verify17-bounded.log)

Para repetir únicamente la suite de integración montada en su raíz de clases, desde este directorio:

```powershell
$fixture = Join-Path (Get-Location).Path 'target/fixtures/test-integration/target/test-classes'
mvn -B "-Dmaven.repo.local=$repo" '-Pfocused-tests' '-Djetty.test.fixture=test-integration' `
    "-Djetty.test.classesDirectory=$fixture" `
    '-Dtest=AliasCheckerMultipleResourceTest,AliasCheckerSymlinkTest,AmbiguousPathTest,CoreMultiPartTest,MultiAuthenticatorTest' `
    '-Djunit.jupiter.execution.parallel.enabled=false' '-Dmaven.test.failure.ignore=true' verify
```

### Hilos virtuales

Configura `JAVA_HOME` y `PATH` de JDK 21 solo en el proceso de prueba. En Windows, la fuente del selector que excluye las 24 variantes de plataforma ya acreditadas está en `verification/templates/VirtualInvocationSelection.java`. El descriptor JUnit de servicio debe contener `jcv.VirtualInvocationSelection`. Las tres corridas focalizadas se hicieron con las suites util, servidor y transportes, respectivamente.

```powershell
$helper = Join-Path $env:TEMP ('jetty-virtual-' + [guid]::NewGuid().ToString('N'))
$service = Join-Path $helper 'META-INF/services'
New-Item -ItemType Directory -Path $service -Force | Out-Null
$junit = Join-Path $repo 'org/junit/jupiter/junit-jupiter-api/6.1.3/junit-jupiter-api-6.1.3.jar'
$api = Join-Path $repo 'org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar'
javac -cp "$junit;$api" -d $helper verification/templates/VirtualInvocationSelection.java
'jcv.VirtualInvocationSelection' | Set-Content -LiteralPath (Join-Path $service 'org.junit.jupiter.api.extension.Extension') -Encoding ascii
$selector = "$helper.jar"
jar --create --file $selector -C $helper .
$opts = @('-B', "-Dmaven.repo.local=$repo", '-Pfocused-tests',
    '-Djetty.surefire.argLine=-Dfile.encoding=UTF-8 -Duser.language=en -Duser.region=US -showversion -Xms64m -Xmx1024m')
mvn @opts '-Djetty.test.fixture=jetty-util' "-Djetty.test.extension=$selector" '-Dtest=VirtualThreadPoolTest,ExecutionStrategyTest' verify
mvn @opts '-Djetty.test.fixture=jetty-server' '-Dtest=QoSHandlerTest#testRequestInVirtualThreadIsResumedInVirtualThread' verify
mvn @opts '-Djetty.test.fixture=jetty-test-client-transports' '-Dtest=VirtualThreadsTest' verify
```

Con JDK 21.0.13.1, Surefire registró 33 aprobadas y 24 omisiones intencionales del selector, sin fallos ni errores. Los XML se conservan en [resultados de JDK 21](verification/results/virtual-21).

En Windows, el proveedor de parámetros de `VirtualThreadsTest` retira `H3_QUICHE` antes de la generación de invocaciones. Quedan pendientes las tres variantes en Linux. La configuración de pruebas se ha acotado al proveedor JNA de la referencia con JDK 17 y 21. La rama FFM de JDK 22 o superior queda fuera de estas corridas.

### Comparar la variante 8 de FormTest

La comparación usó el JDK 17 en ambas copias y desactivó el paralelismo de JUnit. Los dos XML focalizados registraron un aprobado y las otras 15 invocaciones excluidas por el selector. La variante 8 también pasó al ejecutar la clase completa por separado en ambas copias. En esa comparación aparecieron fallos con estado 0 en la variante 5 de ambas copias y en la 7 del consolidado. En la corrida general del consolidado falló la variante 8 con el mismo estado. Esta variación deja pendiente atribuir los resets a una diferencia de implementación. El caso corresponde a HTTPS, límite de 128 bytes, formulario de 200001 bytes y estado esperado 413.

Reutiliza el procedimiento de compilación del selector de hilos virtuales con un directorio temporal nuevo. Sustituye el archivo Java por `verification/templates/FormInvocationSelection.java` y el contenido del descriptor JUnit por `verification.FormInvocationSelection`. Ejecuta lo siguiente desde cada copia, con `$selector` apuntando al mismo JAR auxiliar y `$repo` al mismo repositorio aislado. El reactor upstream requiere descargar o montar sus módulos auxiliares de pruebas.

```powershell
$form = @('-B', "-Dmaven.repo.local=$repo",
    '-Dtest=org.eclipse.jetty.test.client.transport.FormTest#testMaxFormContentSizeExceeded',
    '-Djunit.jupiter.execution.parallel.enabled=false',
    '-Djetty.surefire.argLine=-Dfile.encoding=UTF-8 -Duser.language=en -Duser.region=US -Xms64m -Xmx1792m')

# Copia del reactor upstream.
mvn @form -pl jetty-core/jetty-tests/jetty-test-client-transports -am `
    "-Dmaven.test.additionalClasspath=$selector" '-Dsurefire.failIfNoSpecifiedTests=false' `
    '-Dmaven.build.cache.enabled=false' '-Dspotless.skip=true' '-Dcheckstyle.skip=true' verify

# Módulo consolidado.
mvn @form '-Pfocused-tests' '-Djetty.test.fixture=jetty-test-client-transports' `
    "-Djetty.test.extension=$selector" clean verify
```

### Verificar el consumo independiente

Ejecuta `verification/smoke.ps1` con las rutas de Maven, del JDK y del repositorio aislado tras instalar. El script crea un proyecto temporal con una sola dependencia Jetty y un certificado de prueba nuevo para localhost. Comprueba el origen de clases de los 14 módulos, detección de proveedores, HTTP/1.1, HTTP/2 con TLS y ALPN, gzip, y los bytes UTF-8 una vez descomprimidos. El proyecto consumidor usa el JAR instalado. `verification/audit-jar.py` compara los bytes de las fuentes vendorizadas y las entradas del JAR con un reactor de referencia oficial compilado. La auditoría recuperó las 1.601 clases originales, incluidas 1.578 idénticas byte a byte. El desensamblado de las otras 23 coincide en instrucciones y firmas. El JAR incluye además 23 descriptores `package-info.class` sin anotaciones que javac genera con la configuración del POM consolidado. Consulta [la auditoría del JAR](verification/results/jar-audit-final.json) y [la comparación de clases](verification/results/class-compare.json).


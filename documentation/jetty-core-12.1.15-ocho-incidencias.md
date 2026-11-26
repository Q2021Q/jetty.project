# Investigación de ocho incidencias de Jetty Core 12.1.15

Fecha de actualización 2026-11-26.

## Decisión y alcance

El entorno destino es Linux. La decisión del propietario es documentar los
hallazgos y aplazar las correcciones hasta que los fallos se reproduzcan allí.
Las propuestas de este informe quedan como alternativas para una planificación
posterior. Esta actualización es exclusivamente documental.

El propietario confirmó que los ocho casos aprobaron en una corrida Linux
ejecutada en GitHub. Su resultado se registra como **«fallo no reproducido en esa
corrida»** para cada caso. La confirmación es evidencia reportada por el propietario.
En esta revisión no se dispuso de sus XML, logs, identificador de ejecución,
commit, versiones ni comando, por lo que el aprobado Linux todavía no está
verificado documentalmente a ese nivel.

La consulta pública de las ejecuciones de Actions del repositorio, realizada
en esta revisión, devolvió únicamente la corrida Windows 45869391313. No se pudo
identificar la corrida Linux mediante ese inventario. Queda pendiente asociar la
confirmación del propietario con sus archivos o su enlace de ejecución.

Los antecedentes intermitentes continúan abiertos. Un aprobado individual
acredita que el fallo no se reprodujo en las condiciones de esa corrida.
LargeHeaderTest continúa aplazado y queda fuera de estos ocho casos.

Cuando se emplea «ambos entornos» para describir los fallos recientes de Windows,
se refiere a **Windows local y Windows de GitHub Actions**.

## Identidad y fuentes de autoridad

- Repositorio Q2021Q/jetty.project, rama jetty-12.1.15-validacion.
- Base oficial jetty-12.1.15, commit 770f5e4d1c39673d6356163118a1e6bf1117ced3.
- Commit de las dos corridas Windows ee3f05ef372185b14e4b0ce97d3a12096e82dd3e.
- El manifiesto de ocho casos está en [run.py](../.github/jetty-pending/run.py).
- La selección de invocaciones está en [PendingCases.java](../.github/jetty-pending/PendingCases.java).
- El recorrido Windows está en [el workflow](../.github/workflows/jetty-eight-windows.yml).
- El procedimiento y los límites están en [la guía del lanzador](../.github/jetty-pending/README.md)
  y en [la guía general](jetty-core-12.1.15-verificacion.md).

El propósito concreto de cada prueba se deriva de sus fuentes y aserciones.
Los ocho tests upstream no acreditan por sí solos la integración de autenticación,
correlación, MDC ni el cumplimiento G1–G7 de SecurityAuth y SecurityExceptions.
Esta documentación conserva las obligaciones existentes y mantiene G5 abierto.

## Resultados y calidad de la evidencia

| Entorno | Resultado de los ocho casos | Calidad de la evidencia |
|---|---|---|
| Linux en GitHub | Ocho aprobados. Para cada caso, «fallo no reproducido en esa corrida». | Confirmación del propietario. XML, logs, ID, commit y entorno Linux pendientes de vincular y revisar. |
| Windows de GitHub Actions | Cuatro aprobados y cuatro fallos de aserción. Sin errores ni casos solicitados omitidos o ausentes. | Se revisaron summary.json y los XML del artefacto de la corrida 45869391313. |
| Windows local elevado | Dos aprobados, cinco fallos de aserción y un error. Sin casos solicitados omitidos o ausentes. | Se revisaron XML, logs, comandos, versiones y comprobaciones de tokens de PowerShell y Python. |

Las dos corridas Windows incluyeron además 19 omisiones intencionales del
selector. Son otras invocaciones parametrizadas y se contabilizan aparte.
Maven devolvió 0 en ambas corridas por maven.test.failure.ignore=true.
El resumen local devolvió 1 y la corrida GitHub terminó con conclusion=failure.
Los resultados de prueba proceden de los XML.

## Tabla por caso

En la columna Linux, NR-R significa «fallo no reproducido en esa corrida»,
con aprobado reportado por el propietario y XML todavía pendientes de revisar.

| Caso y propósito | Linux | Windows GitHub / local elevado | Causa identificada, hipótesis y certeza | Posible intervención futura y comprobaciones que deben conservarse |
|---|---|---|---|---|
| ConcurrentRequestsTest#testConcurrentGoodRequestsWithBadRequestsWithDifferentConnections. Rechazar solicitudes inválidas sin perjudicar las válidas en otra conexión. | NR-R | Fallo / fallo. Resets NO_ERROR en la colección de fallos. | Mixto. Los callbacks onReset de la prueba no completan su Callback, defecto confirmado de integración del fixture. La evidencia histórica correlacionó 51 resets con solicitudes inválidas que recibieron 400 y 65 solicitudes válidas con 200 completo. Sigue pendiente separar una expectativa demasiado amplia de un defecto de estado del flujo. | Completar callbacks es una propuesta fundada, con efecto sobre el fallo aún sin verificar. Investigar el procesamiento de END_STREAM y EOF en HTTP2ServerSession antes de cambiar expectativas. Conservar 200 completo para solicitudes válidas, rechazo de las inválidas, ausencia de bloqueo y aislamiento entre conexiones. |
| ConcurrentRequestsTest#testConcurrentGoodRequestsWithBadRequestsWithSameConnection. Preservar el aislamiento dentro de una sesión. | NR-R | Fallo / fallo. Resets NO_ERROR en la colección de fallos. | Comparte los callbacks incompletos. La evidencia histórica registró cuatro resets ligados a solicitudes inválidas y 291 respuestas válidas 200 completas. Uno llegó con el flujo todavía activo en el cliente, después de registrarse el final de la respuesta 400. El orden entre callbacks y cierre requiere investigación productiva. | Completar callbacks y contrastar el orden 400, END_STREAM, reset y liberación del flujo. Conservar la continuidad de sesión y los resultados de las solicitudes válidas. Aceptar cualquier NO_ERROR no está justificado. |
| FileSystemResourceTest#testUtf8Dir. Distinguir un directorio Unicode legítimo del alias de su hijo en Windows. | NR-R | Fallo / fallo. El directorio se clasifica como alias. | Inconsistencia productiva de portabilidad identificada en PathResource. El diagnóstico previo registra sameName=true y sameFile=true, pero compara URI Unicode con representación ASCII porcentual. Certeza alta sobre esa diferencia. El comportamiento Linux reportado sigue pendiente de revisar en XML. | Revisar resolveAlias() y toUri() si se reproduce en Linux o se autoriza otra fase. Conservar las expectativas específicas de cada SO. En Windows, directorio sin alias e hijo con alias. En Linux, las aserciones existentes para ese sistema. Proteger también enlaces, nombres alternativos y navegación. |
| QueuedThreadPoolTest#testMaxStopTime. Comprobar parada acotada e interrupción de una tarea activa. | NR-R | Aprobado / fallo. Falló la espera de interrupción de la línea 698. | Carrera del fixture identificada. Se encola una tarea y se llama a stop() sin demostrar que empezó. doStop() puede retirar trabajos todavía pendientes. Certeza alta sobre la precondición ausente, sin una corrección validada. | Señalizar el inicio de la tarea y esperarlo antes de medir y detener. Conservar isStopped(), el límite original inferior a 1000 ms y la interrupción de la tarea activa. No ampliar el tiempo para ocultar una parada realmente lenta. |
| CoreMultiPartTest#testDoubleReadFromPart. Comprobar dos lecturas independientes de una parte multipart. | NR-R | Fallo / fallo. Comparación del texto producido con println() frente a un salto LF fijo. | Defecto de portabilidad del fixture confirmado. PrintWriter.println() usa el separador de plataforma. El esperado contiene LF fijo. Un aprobado Linux es compatible con ese diagnóstico, sin demostrar una corrección Windows. | Hacer explícito LF en la salida del fixture es una propuesta mínima. Conservar HTTP 200, nombre, longitud 88, contenido y ambas lecturas mediante fuentes independientes. Una segunda lectura ausente o distinta debe seguir haciendo fallar la prueba. |
| FormTest#testMaxFormContentSizeExceeded[8]. Rechazar por HTTPS un formulario de 200001 bytes frente a límite 128 con HTTP 413. | NR-R | Aprobado / aprobado. El incidente histórico sigue abierto. | Requiere investigación productiva. La traza fallida histórica registra 65288 de 200001 bytes procesados, escritura local del 413, EOF_CONTENT, cierre por Unconsumed y cliente con EOF y estado 0. Falta ubicar completamente la pérdida entre publicación, transporte y procesamiento cliente. | Mantener límites, tiempos y aserción 413. Investigar el cierre y la publicación HTTP/TLS si se reproduce en Linux. No aceptar estado 0 ni drenar sin límite como forma de aprobar. |
| HttpClientStreamTest#testDownloadWithFailure[3]. Recibir cabeceras 200 y detectar después un cuerpo incompleto en H2C. | NR-R | Aprobado / error. ExecutionException causada por ClosedChannelException en listener.get(), línea 312. | Fixture sospechoso y responsabilidad productiva pendiente. El servidor escribe parcialmente y cierra la salida de toda la conexión. La escritura local no acredita recepción de cabeceras. Una traza previa registra comienzo de respuesta 200 antes de cierre de sesión, pero el listener no llegó a entregar esa respuesta. Certeza media sobre la hipótesis de sincronización. | Investigar si una sincronización acotada con recepción de cabeceras permite ensayar la fase prevista sin ocultar una pérdida productiva. Conservar 200, error al leer el cuerpo, límite de bytes y resultado fallido. Aceptar cualquier excepción de get() alteraría el propósito actual. |
| MinimumDataRateHandlerTest#testMinimumDataWriteRateWithSingleLastWrite. Interrumpir una escritura estancada por tasa insuficiente. | NR-R | Aprobado / aprobado. Existe fallo histórico por referencia null. | Carrera de sincronización de la prueba identificada. failed() llama a super.failed(x), que alcanza completed() y libera el latch antes de writeFailureRef.set(x). El fallo histórico fue getMessage() sobre null. Certeza alta sobre el orden inseguro. | Guardar la excepción antes de delegar en super.failed(x). Conservar espera acotada, respuesta incompleta, fallo de escritura y mensaje write rate is too low. Los aprobados actuales no eliminan la carrera estructural. |

Todas las propuestas anteriores quedan aplazadas conforme a la decisión Linux.
Las tres candidatas más fundamentadas en las propias pruebas son la señal de
inicio del thread pool, el separador del fixture multipart y el orden de
publicación del fallo de tasa mínima. Ninguna se implementó en esta intervención.

## Ubicaciones para una eventual corrección

| Área | Fuentes de referencia |
|---|---|
| Solicitudes concurrentes HTTP/2 | [ConcurrentRequestsTest](../jetty-core/jetty-http2/jetty-http2-tests/src/test/java/org/eclipse/jetty/http2/tests/ConcurrentRequestsTest.java), [contrato onReset](../jetty-core/jetty-http2/jetty-http2-common/src/main/java/org/eclipse/jetty/http2/api/Stream.java), [HTTP2ServerSession](../jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HTTP2ServerSession.java), [HttpStreamOverHTTP2](../jetty-core/jetty-http2/jetty-http2-server/src/main/java/org/eclipse/jetty/http2/server/internal/HttpStreamOverHTTP2.java). |
| Alias Unicode | [FileSystemResourceTest](../jetty-core/jetty-util/src/test/java/org/eclipse/jetty/util/resource/FileSystemResourceTest.java), [PathResource](../jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/resource/PathResource.java). |
| Parada del pool | [QueuedThreadPoolTest](../jetty-core/jetty-util/src/test/java/org/eclipse/jetty/util/thread/QueuedThreadPoolTest.java), [QueuedThreadPool.doStop](../jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/thread/QueuedThreadPool.java). |
| Multipart | [CoreMultiPartTest](../tests/test-integration/src/test/java/org/eclipse/jetty/test/CoreMultiPartTest.java). |
| HTTP 413 | [FormTest](../jetty-core/jetty-tests/jetty-test-client-transports/src/test/java/org/eclipse/jetty/test/client/transport/FormTest.java), [HttpStream.consumeAvailable](../jetty-core/jetty-server/src/main/java/org/eclipse/jetty/server/HttpStream.java), [HttpConnection](../jetty-core/jetty-server/src/main/java/org/eclipse/jetty/server/internal/HttpConnection.java), [HttpChannelState](../jetty-core/jetty-server/src/main/java/org/eclipse/jetty/server/internal/HttpChannelState.java). |
| Descarga truncada H2C | [HttpClientStreamTest](../jetty-core/jetty-tests/jetty-test-client-transports/src/test/java/org/eclipse/jetty/test/client/transport/HttpClientStreamTest.java), [InputStreamResponseListener](../jetty-core/jetty-client/src/main/java/org/eclipse/jetty/client/InputStreamResponseListener.java), [HTTP2Session](../jetty-core/jetty-http2/jetty-http2-common/src/main/java/org/eclipse/jetty/http2/HTTP2Session.java). |
| Tasa mínima | [MinimumDataRateHandlerTest](../jetty-core/jetty-server/src/test/java/org/eclipse/jetty/server/handler/MinimumDataRateHandlerTest.java), [Callback.Nested](../jetty-core/jetty-util/src/main/java/org/eclipse/jetty/util/Callback.java), [MinimumDataRateHandler](../jetty-core/jetty-server/src/main/java/org/eclipse/jetty/server/handler/MinimumDataRateHandler.java). |

La elección de un separador explícito en multipart deriva de la API Java 17.
En HTTP/2, RFC 9113 contempla resets tras respuestas completas y reglas específicas
para mensajes malformados. Esa distinción debe comprobarse por flujo antes de
revisar una expectativa. [PrintWriter](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/io/PrintWriter.html),
[RFC 9113 §§8.1–8.2.1](https://www.rfc-editor.org/rfc/rfc9113.html#section-8.1).

## Entornos, comandos y condiciones acreditados

| Dato | Windows GitHub Actions | Windows local elevado | Linux en GitHub |
|---|---|---|---|
| Ejecución | 45869391313, intento 1, creada 2026-11-26T17:38:07Z | Preparación corta 2026-11-26T17:57:08Z, fin 18:01:48Z | Aprobado de ocho casos comunicado por el propietario. ID y fecha pendientes. |
| SO y arquitectura | Windows Server 2022, amd64 | Windows 10 19045, amd64 | Distribución, kernel y arquitectura pendientes de evidencia. |
| Java | Temurin 17.0.11+9 | Oracle JDK 17.0.11+7-LTS-207 | Versión, proveedor y JVM de Surefire pendientes. |
| Maven / Python | 3.9.12 / 3.12.10 | 3.9.12 / Python 3.12 del equipo | Pendientes de evidencia. |
| Elevación | El artefacto no registra el token | PowerShell y Python registran administrador=True | UID, GID y capacidades no documentados. |
| Resultado Maven | 0, 81.845 segundos | 0, 250.306 segundos | Pendiente de evidencia. |

Los puntos de entrada Windows ejecutados fueron los siguientes.

~~~text
python .github/jetty-pending/run.py run
python .github/jetty-pending/run.py summarize
~~~

El local se lanzó desde PowerShell 7.6.10 elevado mediante Start-Process -Verb
RunAs. execution-status.json y python-token.json conservan la comprobación.
Los argumentos Maven efectivos de ambas corridas son equivalentes al normalizar
las rutas del ejecutable, log, repositorio aislado y selector.

El manifiesto y la lista completa de opciones se mantienen en run.py para evitar
duplicarlos en esta documentación. Incluyen un reactor con -am hasta verify,
los 14 módulos seleccionados y auxiliares, repositorio Maven aislado, paralelismo
JUnit desactivado, sin reruns, heap Maven de 1 GiB y heap de pruebas de 1792 MiB.
El log de Maven, stdout y stderr quedan separados. La recopilación de XML se hace
aunque haya fallos. No se instaló Jetty en un repositorio Maven.

Los límites fueron 70 minutos para Maven, 600 segundos por fork, 120 segundos
por método o invocación parametrizada y 60 para after-each. El workflow limita
el job a 100 minutos. Estas condiciones no deben atribuirse a Linux hasta revisar
su comando real.

El primer montaje local se detuvo antes de Maven al consultar 17 rutas de al
menos 260 caracteres. Los archivos existían al consultarlos con prefijo extendido.
Se preparó una ruta temporal más corta y después se ejecutó un único verify.
Ese incidente de preparación no añade ocho fallos de prueba.

## Evidencias disponibles y dependencias locales

Las rutas siguientes describen ubicaciones de la cuenta donde se revisaron los
archivos. Su presencia no queda garantizada en otro clon. Esta actualización no
incorpora ni mueve los artefactos originales.

| Evidencia | Ubicación y contenido revisado | Dependencia pendiente |
|---|---|---|
| Windows GitHub | Artefacto jetty-eight-windows-45869391313-1.zip, descargado en C:\Users\Kevin\Downloads. Contiene revision.json, summary.json, XML, comandos y versiones. | Archivar una copia duradera o conservar el artefacto antes de expirar su retención. |
| Windows local elevado | C:\Users\Kevin\AppData\Local\Temp\j8-19s8af19. Contiene execution-status.json, python-token.json, comparison.json y report.md. Los logs y XML están en source/jetty-eight-results. | Depende de TEMP. El ZIP jetty-eight-elevated-results.zip agrupa la evidencia seleccionada. |
| Antecedentes HTTP/2, alias, 413 y descarga H2C | C:\Users\Kevin\AppData\Local\Temp\jcc-770f5e4\eight-diagnosis\evidencia-ocho-casos.zip. Incluye http2-summary.json, http2-resets.csv, alias-probe.txt y trazas. | Depende de TEMP. Las cifras históricas de la tabla corresponden a estas trazas, no a una instrumentación nueva de los Windows recientes. |
| Controles completos de 413 | C:\Users\Kevin\AppData\Local\Temp\j413-20261125-100253-778, árboles oficial y consolidado. | Dependen de TEMP. Mantener el vínculo entre XML, traza, comando y revisión. |
| Antecedente de la tasa mínima y consolidación | Carpeta hermana JettyCoreConsolidated/verification/results, con test-summary.json y surefire-jdk17.zip. | Está fuera de este repositorio. Sus rutas internas también remiten a corridas temporales. |
| Parches experimentales | Carpeta hermana jetty-verify-ehqea4/changes.diff y patch-manifest.json. | Constituyen propuestas separadas del árbol original. Su mera presencia no acredita la corrección de los ocho casos. |
| Linux en GitHub | Confirmación del propietario de que aprobaron los ocho casos. | Obtener enlace o ID, XML, resumen, logs, revisión, herramientas, selector y condiciones. Hasta revisarlos, el resultado sigue reportado. |

Identificadores de integridad calculados sobre los ZIP revisados.

~~~text
jetty-eight-windows-45869391313-1.zip
SHA-256 652fd879837e91b9acfa52d0c605a2d90fc20679f10e4d1b69e16c91919ae2ba

jetty-eight-elevated-results.zip
SHA-256 ba3e687221f769c176ad68ac03e97ee71c8b9d20e113444a69b0532888cd256f
~~~

La corrida Windows está disponible en
[GitHub Actions](https://github.com/Q2021Q/jetty.project/actions/runs/45869391313).
El workflow declara retención de artefactos de 30 días.

## Límites de la comparación

- El proveedor y build del JDK, SO, rutas y locale difieren entre los dos Windows.
  No se acreditó igualdad de CPU, memoria disponible, carga, almacenamiento ni
  planificación. Estas diferencias pueden afectar concurrencia y temporización.
- No existe un control local equivalente sin elevación para atribuir cambios al
  token. El resultado GitHub no sustituye ese control.
- La salida textual multipart depende del separador de plataforma. Las
  expectativas de alias de un hijo son específicas del SO.
- Los aprobados Windows de FormTest y tasa mínima conservan abiertos sus
  antecedentes intermitentes. El mismo criterio se aplica al aprobado Linux.
- Las ocho invocaciones y variantes deben corresponder a la misma selección.
  Una omisión, una variante distinta o Maven exit 0 no acredita un aprobado.
- El árbol original y los POM permanecieron intactos durante las comprobaciones.
  Esta intervención no ejecutó pruebas ni modificó configuración.

## Validación Linux pendiente

1. Recuperar primero la evidencia de la corrida Linux ya reportada. Vincular cada
   caso con exactamente un XML nuevo y distinguir omisiones, selección vacía,
   duplicados y fallos del montaje. Registrar «fallo no reproducido en esa corrida»
   para los aprobados verificados, preservando la identidad de la ejecución.
2. Precisar distribución, kernel, arquitectura y recursos del destino. Si difieren
   del runner Linux de GitHub, registrar esa diferencia antes de extrapolar.
   Conservar commit, hash de fuentes, JDK, Maven, JVM de Surefire, locale, filesystem,
   UID/GID y límites de recursos.
3. Para una futura corrida, preparar una copia completa y limpia de la rama.
   Mantener Java 17.0.11 y Maven 3.9.12 para comparación, o documentar expresamente
   la versión del destino si es otra. El perfil enable-foreign queda fuera de
   esta comparación JDK 17.
4. Planificar un lanzador Linux separado que reutilice el manifiesto y el selector.
   run.py es Windows específico por su guardia de SO, ejecutables .exe/.cmd,
   CREATE_NO_WINDOW y taskkill. Esta fase no incorpora esa adaptación.
5. Compilar el selector con separador de classpath de Linux y comprobar los
   parámetros efectivos. FormTest[8] debe ser HTTPS, 128, 200001, 413.
   HttpClientStreamTest[3] debe ser H2C. El proveedor de transportes incluye
   H3_QUICHE en Linux, por lo que se debe comprobar la selección y excluir del
   alcance las invocaciones adicionales sin confundirlas con los ocho casos.
6. Conservar el reactor y sus auxiliares, un único verify, ausencia de install,
   límites de tiempo explícitos y recopilación de logs/XML aun ante fallos.
   Registrar comandos efectivos y origen de los artefactos. Empezar con la
   selección focalizada sin asumir que el orden o la carga de una suite amplia
   son irrelevantes para los antecedentes intermitentes.
7. Si aparece un fallo Linux, correlacionarlo con la clase de fallo documentada
   antes de planificar cambios. Conservar las aserciones y sus controles negativos.
   Cualquier ampliación de contexto o instrumentación debe justificarse por
   una duda material y registrarse como diferencia.
8. Mientras no exista reproducción Linux, mantener las correcciones aplazadas
   por decisión del propietario. El aprobado reportado no cierra los hallazgos
   estructurales ni constituye aceptación integral de G5.

# Eight pending Jetty cases on Windows

This workflow tests the original reactor on branch jetty-12.1.15-validacion.
The upstream baseline is 770f5e4d1c39673d6356163118a1e6bf1117ced3.
The actual branch commit, including CI support, is recorded in revision.json.
Source and POM changes relative to the baseline cause preparation to fail.
The existing documentation commit is allowed. LargeHeaderTest stays deferred.

## Publish and start

From the local JettyCore12.1.15 checkout, inspect and publish these CI files.
The existing sparse checkout requires git add --sparse.

~~~powershell
git switch jetty-12.1.15-validacion
git add --sparse .github/workflows/jetty-eight-windows.yml .github/jetty-pending/
git diff --cached --stat
git commit -m "ci(jetty): verify eight pending cases on Windows"
git push origin jetty-12.1.15-validacion
~~~

The push event runs the workflow from the validation branch, including first
publication. GitHub Actions must be enabled for this fork. In GitHub, open Actions,
enable workflows if requested, then open "Jetty eight pending cases on Windows".
Later executions can use "Re-run all jobs" on that run, keeping the same commit.
An optional empty commit pushed to this branch also starts a new run.

workflow_dispatch is declared. GitHub documents that the workflow file must exist
on the default branch for the manual trigger to be available. To use "Run workflow",
publish this same workflow to the default branch as a separate reviewed change,
then select jetty-12.1.15-validacion. The job guard prevents testing other branches.
Publishing only to the validation branch is sufficient for push.

Official event requirements:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch

## Preparation from a clean runner

The GitHub-hosted windows-2022 runner checks out the full triggering commit,
with history and without sparse checkout. Outbound HTTPS and loopback are required.
Java is pinned to Temurin 17.0.11+9 x64. The historical Windows reference used
Oracle JDK 17.0.11. Consider this vendor difference and hosted runner resources
when interpreting intermittent failures. Java and Maven versions are checked;
the Java version is checked again in every requested XML result.

The launcher downloads Apache Maven 3.9.12 and verifies the published SHA-512.
Python 3.12 runs the launcher. The JUnit API version is read from the root POM.
JUnit API and API Guardian are downloaded from Maven Central to compile the
selection extension. Their hashes are recorded. Maven downloads ordinary
dependencies online into a fresh repository under RUNNER_TEMP.

One Maven invocation runs to verify with -am. It includes the 14 production
modules, BOM, JMX, build resources and the five modules containing the cases.
Jetty auxiliaries are built in that reactor. There is no install or developer
cache. FFM is inactive under JDK 17 and the upstream JNA profile applies.

## Exact selection and evidence

run.py contains the eight-case manifest and derives the method selectors.
PendingCases.java is a JUnit extension compiled outside upstream sources.
It keeps invocation 8 of FormTest and invocation 3 of HttpClientStreamTest.
Other parameter invocations can be reported as skipped with the reason
outside-eight-case-selection. Original methods, fixtures and assertions execute
unchanged. Ordinary nonparameterized cases execute once.

The summary requires one XML result per requested case. It checks module, class,
method, parameter index and Java version. Parameterized cases must also show
"HTTPS, 128, 200001, 413" and "H2C" in their display name or captured output.
Missing, duplicate, skipped or wrong-variant cases fail the audit. An executed
case outside the selection also fails it. Setup failures retain their XML
failure/error result; variant evidence may remain unverified.

JUnit is sequential with one reused fork per module as configured upstream.
The complete 35-class transport suite is excluded. The historical FormTest
incident occurred with only its method selected. A successful focused execution
does not close that intermittent incident.

Maven uses maven.test.failure.ignore=true to collect reports across modules.
The separate summarize step fails for any failed, errored, omitted or unverified
requested case, nonzero Maven exit, timeout, unexpected execution or invalid XML.
Maven exit code 0 alone never makes the workflow pass.

Limits: job 100 minutes, build step 85, Maven process 70, Surefire fork 10.
JUnit test/template methods have 120 seconds and after-each has 60.
On Maven timeout the launcher terminates its Windows process tree. A GitHub
step/job timeout may interrupt reports. The always-run summary and upload retain
available evidence subject to runner availability and GitHub cancellation limits.

## Download results

In the run page, download artifact jetty-eight-windows-<run_id>-<attempt>.
With GitHub CLI already authenticated:

~~~powershell
gh run list --repo Q2021Q/jetty.project --branch jetty-12.1.15-validacion --workflow jetty-eight-windows.yml
gh run download RUN_ID --repo Q2021Q/jetty.project --dir jetty-eight-results
~~~

The artifact contains summary.json, summary.md, revision.json, command records,
version logs, Maven stdout/stderr and maven.log, plus mirrored Surefire XML,
available dumps and Failsafe reports. Per-case classpaths remain in summary.json.
Preparation failure produces missing-case results and fails the workflow.
Artifact retention is 30 days.

## Static checks and remaining verification

Static validation covers YAML, Python syntax, selection consistency, original
method presence, workflow structure and selector compilation. Maven and Jetty
tests are not run during this preparation.

Recorded Windows results, the owner-reported Linux run on GitHub and the decision
to defer corrections until reproduction on Linux are documented in the
[eight-case investigation](../../documentation/jetty-core-12.1.15-ocho-incidencias.md).
Linux artifacts remain to be linked and verified. This workflow does not approve G5.

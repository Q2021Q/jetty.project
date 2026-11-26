"""Prepare a clean Windows reactor and audit exactly the eight requested XML results."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "jetty-eight-results"
BASE = "770f5e4d1c39673d6356163118a1e6bf1117ced3"
VERSION = "3.9.12"
CASES = [
    ("jetty-core/jetty-http2/jetty-http2-tests", "org.eclipse.jetty.http2.tests.ConcurrentRequestsTest", "testConcurrentGoodRequestsWithBadRequestsWithDifferentConnections", 0),
    ("jetty-core/jetty-http2/jetty-http2-tests", "org.eclipse.jetty.http2.tests.ConcurrentRequestsTest", "testConcurrentGoodRequestsWithBadRequestsWithSameConnection", 0),
    ("jetty-core/jetty-util", "org.eclipse.jetty.util.resource.FileSystemResourceTest", "testUtf8Dir", 0),
    ("jetty-core/jetty-util", "org.eclipse.jetty.util.thread.QueuedThreadPoolTest", "testMaxStopTime", 0),
    ("tests/test-integration", "org.eclipse.jetty.test.CoreMultiPartTest", "testDoubleReadFromPart", 0),
    ("jetty-core/jetty-tests/jetty-test-client-transports", "org.eclipse.jetty.test.client.transport.FormTest", "testMaxFormContentSizeExceeded", 8),
    ("jetty-core/jetty-tests/jetty-test-client-transports", "org.eclipse.jetty.test.client.transport.HttpClientStreamTest", "testDownloadWithFailure", 3),
    ("jetty-core/jetty-server", "org.eclipse.jetty.server.handler.MinimumDataRateHandlerTest", "testMinimumDataWriteRateWithSingleLastWrite", 0),
]
CORE = [
    "jetty-core/jetty-server", "jetty-core/jetty-http", "jetty-core/jetty-io",
    "jetty-core/jetty-util", "jetty-core/jetty-alpn/jetty-alpn-server",
    "jetty-core/jetty-alpn/jetty-alpn-java-server",
    "jetty-core/jetty-http2/jetty-http2-server", "jetty-core/jetty-http2/jetty-http2-common",
    "jetty-core/jetty-http2/jetty-http2-hpack", "jetty-core/jetty-security",
    "jetty-core/jetty-rewrite", "jetty-core/jetty-compression/jetty-compression-server",
    "jetty-core/jetty-compression/jetty-compression-common",
    "jetty-core/jetty-compression/jetty-compression-gzip",
]
MODULES = list(dict.fromkeys(CORE + ["jetty-core/jetty-bom", "jetty-core/jetty-jmx",
                                   "build/build-resources"] + [c[0] for c in CASES]))


def save(name, data):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True, encoding="utf-8").strip()


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=90) as response, path.open("wb") as dest:
        shutil.copyfileobj(response, dest)


def command(args, label, timeout):
    """Use file handles for both channels, including Maven/Jansi shutdown."""
    save(label + "-command.json", {"cwd": str(ROOT), "args": list(map(str, args)),
                                  "timeout_seconds": timeout})
    env = os.environ.copy()
    for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "MAVEN_ARGS",
                "MAVEN_BATCH_PAUSE", "MAVEN_TERMINATE_CMD"):
        env.pop(key, None)
    env["MAVEN_SKIP_RC"] = "true"
    env["MAVEN_OPTS"] = "-Xms128m -Xmx1024m"
    started = time.time()
    state = {"exit_code": None, "timed_out": False}
    # No PowerShell console pipeline. The process inherits regular disk files.
    with (OUT / (label + ".stdout.log")).open("wb") as stdout, (OUT / (label + ".stderr.log")).open("wb") as stderr:
        with subprocess.Popen(list(map(str, args)), cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                              creationflags=subprocess.CREATE_NO_WINDOW) as process:
            try:
                state["exit_code"] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                state["timed_out"] = True
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=stdout, stderr=stderr, timeout=30, check=False)
                state["exit_code"] = process.wait(timeout=30)
    state["elapsed_seconds"] = round(time.time() - started, 3)
    save(label + "-status.json", state)
    return state


def checked(args, label, timeout=180):
    state = command(args, label, timeout)
    if state["exit_code"] != 0 or state["timed_out"]:
        raise RuntimeError(f"{label} failed; inspect its status and logs")
    return (OUT / (label + ".stdout.log")).read_text(encoding="utf-8", errors="replace") + (OUT / (label + ".stderr.log")).read_text(encoding="utf-8", errors="replace")


def run():
    if os.name != "nt":
        raise RuntimeError("This diagnostic requires Windows")
    if os.environ.get("GITHUB_REF") != "refs/heads/jetty-12.1.15-validacion":
        raise RuntimeError("Unexpected branch")
    save("revision.json", {"commit": git("rev-parse", "HEAD"), "base": BASE,
                          "ref": os.environ.get("GITHUB_REF"), "runner_os": os.environ.get("RUNNER_OS"),
                          "python": sys.version, "platform": sys.platform})
    git("merge-base", "--is-ancestor", BASE, "HEAD")
    # The only permitted changes relative to upstream are CI and documentation.
    changed = git("diff", "--name-only", BASE, "HEAD").splitlines()
    disallowed = [p for p in changed if not p.startswith((".github/", "documentation/"))]
    save("changes-from-base.json", changed)
    if disallowed or git("diff", "--name-only", "HEAD"):
        raise RuntimeError(f"Modified upstream sources or POM: {disallowed}")
    missing = [p for p in git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
               if not (ROOT / p).is_file()]
    if missing:
        raise RuntimeError(f"Incomplete checkout (including sparse exclusions): {missing[:5]}")
    if list(ROOT.glob("**/target/surefire-reports/TEST-*.xml")):
        raise RuntimeError("Existing reports; a clean checkout is required")
    work = Path(os.environ["RUNNER_TEMP"]) / "jetty-eight"
    work.mkdir(parents=True, exist_ok=True)
    archive = work / f"apache-maven-{VERSION}-bin.zip"
    url = f"https://archive.apache.org/dist/maven/maven-3/{VERSION}/binaries/{archive.name}"
    download(url, archive)
    checksum = archive.with_suffix(".zip.sha512")
    download(url + ".sha512", checksum)
    expected = re.search(r"\b[0-9a-fA-F]{128}\b", checksum.read_text()).group(0).lower()
    actual = hashlib.sha512(archive.read_bytes()).hexdigest()
    save("maven-download.json", {"url": url, "expected_sha512": expected, "actual_sha512": actual})
    if actual != expected:
        raise RuntimeError("Maven SHA-512 mismatch")
    with zipfile.ZipFile(archive) as z:
        z.extractall(work)
    maven = work / f"apache-maven-{VERSION}/bin/mvn.cmd"
    jdk = Path(os.environ["JAVA_HOME"])
    java = checked([jdk / "bin/java.exe", "-version"], "java-version")
    mvn = checked([maven, "-version"], "maven-version")
    if 'version "17.0.11"' not in java or f"Apache Maven {VERSION}" not in mvn or "Java version: 17.0.11" not in mvn:
        raise RuntimeError("Unexpected Java or Maven runtime")
    # Bootstrap the extension before Maven. These are external JUnit API artifacts.
    junit_version = ET.parse(ROOT / "pom.xml").getroot().findtext(
        "{*}properties/{*}junit.version")
    deps = []
    for path in (f"org/junit/jupiter/junit-jupiter-api/{junit_version}/junit-jupiter-api-{junit_version}.jar",
                 "org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar"):
        dest = work / Path(path).name
        download("https://repo.maven.apache.org/maven2/" + path, dest)
        deps.append(dest)
    save("selector-dependencies.json", [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                      for p in deps])
    classes = work / "selector"
    classes.mkdir(exist_ok=True)
    checked([jdk / "bin/javac.exe", "--release", "17", "-cp", os.pathsep.join(map(str, deps)),
             "-d", classes, ROOT / ".github/jetty-pending/PendingCases.java"], "compile-selector")
    service = classes / "META-INF/services"
    service.mkdir(parents=True, exist_ok=True)
    (service / "org.junit.jupiter.api.extension.Extension").write_text("jettypending.PendingCases\n", encoding="ascii")
    (classes / "pending-cases.tsv").write_text("".join(f"{c}#{m}\t{i}\n" for _, c, m, i in CASES), encoding="utf-8")
    selector = work / "pending-cases.jar"
    checked([jdk / "bin/jar.exe", "--create", "--file", selector, "-C", classes, "."], "package-selector")
    repository = work / "m2"
    grouped = {}
    for _, cls, method, _ in CASES:
        grouped.setdefault(cls, []).append(method)
    selection = ",".join(cls + "#" + "+".join(methods) for cls, methods in grouped.items())
    save("selection.json", {"cases": CASES, "modules": MODULES, "test": selection,
                            "selector_sha256": hashlib.sha256(selector.read_bytes()).hexdigest()})
    args = [maven, "-B", "-ntp", "-fae", "-pl", ",".join(MODULES), "-am",
            "-l", OUT / "maven.log", f"-Dmaven.repo.local={repository}",
            "-Dmaven.build.cache.enabled=false", "-Dspotless.skip=true", "-Dcheckstyle.skip=true",
            "-Dmaven.test.failure.ignore=true", "-Dsurefire.failIfNoSpecifiedTests=false",
            "-Dfailsafe.failIfNoSpecifiedTests=false", "-Dsurefire.useModulePath=false",
            "-Dsurefire.rerunFailingTestsCount=0", "-Dsurefire.timeout=600",
            "-Djunit.jupiter.extensions.autodetection.enabled=true",
            "-Djunit.jupiter.execution.parallel.enabled=false",
            "-Djunit.jupiter.execution.timeout.aftereach.method.default=60 s",
            "-Djunit.jupiter.execution.timeout.test.method.default=120 s",
            "-Djunit.jupiter.execution.timeout.testtemplate.method.default=120 s",
            "-Djetty.surefire.argLine=-Dfile.encoding=UTF-8 -Duser.language=en -Duser.region=US -Xms64m -Xmx1792m",
            f"-Dmaven.test.additionalClasspath={selector}", f"-Dtest={selection}", f"-Dit.test={selection}", "verify"]
    state = command(args, "maven", 70 * 60)
    # Never turn Maven's nonzero exit into success while collecting all XML.
    return 0 if state["exit_code"] == 0 and not state["timed_out"] else 1


def summarize():
    records = []
    parse_errors = []
    for path in sorted(p for p in ROOT.glob("**/target/surefire-reports/TEST-*.xml") if not p.is_relative_to(OUT)):
        relative = path.relative_to(ROOT)
        dest = OUT / "reports" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        try:
            suite = ET.parse(path).getroot()
            props = {p.get("name"): p.get("value") for p in suite.findall("properties/property")}
            module = relative.as_posix().split("/target/", 1)[0]
            for node in suite.findall("testcase"):
                name = node.get("name", "")
                method = re.match(r"[\w$]+", name)
                index = re.search(r"\)\[(\d+)\]", name)
                status = next((tag for tag in ("failure", "error", "skipped") if node.find(tag) is not None), "passed")
                event = node.find(status)
                records.append({"key": (module, node.get("classname"), method.group(0) if method else name,
                                        int(index.group(1)) if index else 0),
                                "name": name, "status": status,
                                "message": (event.get("message") or event.text or "") if event is not None else "",
                                "java": props.get("java.version"), "java_home": props.get("java.home"),
                                "xml": dest.relative_to(OUT).as_posix(),
                                "class_path": props.get("surefire.test.class.path", props.get("java.class.path", "")),
                                "output": "\n".join((n.text or "") for n in node.findall("system-out") + node.findall("system-err"))})
        except (ET.ParseError, OSError) as error:
            parse_errors.append({"file": str(relative), "error": str(error)})
    expected = set(CASES)
    unexpected = [r for r in records if tuple(r["key"]) not in expected and r["status"] != "skipped"]
    results = []
    for case in CASES:
        matches = [r for r in records if tuple(r["key"]) == case]
        result = {"case": f"{case[1]}#{case[2]}" + (f"[{case[3]}]" if case[3] else ""), "module": case[0]}
        if len(matches) != 1:
            result.update(status="missing" if not matches else "duplicate", count=len(matches))
        else:
            r = matches[0]
            result.update({k: r[k] for k in ("status", "name", "message", "java", "java_home", "xml", "class_path")})
            result["runtime_verified"] = r["java"] == "17.0.11"
            if case[3]:
                signature = "[8] HTTPS, 128, 200001, 413" if case[3] == 8 else "[3] H2C"
                result["variant_verified"] = signature in (r["name"] + "\n" + r["output"])
            else:
                result["variant_verified"] = True
        results.append(result)
    status_path = OUT / "maven-status.json"
    maven = json.loads(status_path.read_text()) if status_path.exists() else {"exit_code": None, "timed_out": False}
    good = all(r["status"] == "passed" and r.get("runtime_verified") and r.get("variant_verified") for r in results)
    good = good and not unexpected and not parse_errors and maven["exit_code"] == 0 and not maven["timed_out"]
    totals = {s: sum(r["status"] == s for r in results) for s in ("passed", "failure", "error", "skipped", "missing", "duplicate")}
    data = {"cases": results, "totals": totals, "maven": maven, "passed": good,
            "unexpected_executed": unexpected, "xml_errors": parse_errors,
            "other_skips": sum(r["status"] == "skipped" and tuple(r["key"]) not in expected for r in records)}
    save("summary.json", data)
    lines = ["# Jetty Windows: eight pending cases", "",
             f"Maven exit code: {maven['exit_code']}; timed out: {maven['timed_out']}", "",
             "| Case | XML result | JVM/variant verified |", "|---|---|---|"]
    for r in results:
        lines.append(f"| {r['case']} | {r['status']} | {bool(r.get('runtime_verified') and r.get('variant_verified'))} |")
    lines += ["", "Totals: " + json.dumps(totals), "", "LargeHeaderTest is deferred.",
              "Temurin 17.0.11+9 differs from the historical Oracle JDK vendor.",
              "Maven exit code and XML outcomes are evaluated independently."]
    markdown = "\n".join(lines) + "\n"
    (OUT / "summary.md").write_text(markdown, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
            output.write(markdown)
    # Preserve dumps and text reports, including forks that never produced XML.
    for path in list(p for p in ROOT.glob("**/target/*") if not p.is_relative_to(OUT)):
        if path.is_dir() and path.name in ("surefire-reports", "failsafe-reports", "jstacks"):
            shutil.copytree(path, OUT / "reports" / path.relative_to(ROOT), dirs_exist_ok=True)
    print(json.dumps(totals))
    return 0 if good else 1


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    try:
        if sys.argv[1:] == ["run"]:
            sys.exit(run())
        elif sys.argv[1:] == ["summarize"]:
            sys.exit(summarize())
        else:
            raise ValueError("Use run.py run or run.py summarize")
    except Exception:
        (OUT / "preparation-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise

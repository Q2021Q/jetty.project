"""Check the vendored tree and the consolidated JAR against a built upstream reactor."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import argparse
import json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("upstream_build", type=Path, help="Jetty 12.1.15 reactor with its target JARs")
parser.add_argument("--jar", type=Path)
arguments = parser.parse_args()
project = Path(__file__).resolve().parent.parent
upstream = arguments.upstream_build.resolve()
jar_path = arguments.jar or project / "target/jetty-core-consolidated-12.1.15.jar"
inventory = json.loads((project / "upstream/source-inventory.json").read_text(encoding="utf-8"))

for destination, (source, expected) in inventory["files"].items():
    assert sha256((project / destination).read_bytes()).hexdigest() == expected, destination
    assert sha256((upstream / source).read_bytes()).hexdigest() == expected, source

metadata = "org/eclipse/jetty/version/build.properties"
expected_resources = {}
expected_classes = set()
expected_services = {}
with ZipFile(jar_path) as consolidated:
    entries = consolidated.namelist()
    assert len(set(entries)) == len(entries), "duplicate entries"
    assert "module-info.class" not in entries, "the consolidated JAR uses one automatic JPMS name"
    for module in inventory["modules"]:
        artifact = module.rsplit("/", 1)[-1]
        with ZipFile(upstream / module / f"target/{artifact}-12.1.15.jar") as original:
            for entry in original.namelist():
                if entry.endswith(".class") and entry != "module-info.class":
                    assert entry not in expected_classes, entry
                    expected_classes.add(entry)
                elif entry.startswith("META-INF/services/") and not entry.endswith("/"):
                    providers = expected_services.setdefault(entry, set())
                    providers.update(line.partition("#")[0].strip() for line in
                                     original.read(entry).decode().splitlines() if line.partition("#")[0].strip())
                elif not entry.startswith("META-INF/maven/") and entry not in ("META-INF/MANIFEST.MF", metadata)                         and not entry.endswith(("/","module-info.class")):
                    expected_resources[entry] = original.read(entry)
    actual_classes = {entry for entry in entries if entry.endswith(".class")}
    assert expected_classes <= actual_classes, sorted(expected_classes - actual_classes)
    extra_classes = actual_classes - expected_classes
    # javac may emit otherwise empty class metadata for unannotated package-info.java files.
    for entry in extra_classes:
        assert entry.endswith("/package-info.class"), entry
        original = project / "src/main/java" / entry.replace(".class", ".java")
        assert original.is_file() and "@" not in original.read_text(encoding="utf-8").split("*/")[-1], entry
    assert {entry for entry in entries if entry.startswith("META-INF/services/") and not entry.endswith("/")} == set(expected_services)
    for entry, providers in expected_services.items():
        lines = consolidated.read(entry).decode().splitlines()
        assert len(set(lines)) == len(lines) and set(lines) == providers, entry
    for entry, value in expected_resources.items():
        assert consolidated.read(entry) == value, entry
    for name in ("LICENSE", "NOTICE.txt"):
        assert consolidated.read(f"META-INF/{name}") == (upstream / name).read_bytes(), name
    for entry in entries:
        # Jetty excludes these development keystores in its upstream config artifacts.
        if entry.startswith("META-INF/jetty/config/"):
            assert not entry.endswith(".p12"), entry
    config = [entry for entry in entries if entry.startswith("META-INF/jetty/config/") and not entry.endswith("/")]
    files = [file for file in (project / "src/main/config").rglob("*") if file.is_file() and file.suffix != ".p12"]
    assert len(config) == len(files), config
    for file in files:
        entry = "META-INF/jetty/config/" + file.relative_to(project / "src/main/config").as_posix()
        assert consolidated.read(entry) == file.read_bytes(), entry
    info = dict(line.split("=", 1) for line in consolidated.read(metadata).decode().splitlines())
    assert info["version"] == "12.1.15" and info["buildNumber"] == inventory["commit"], info
    manifest = consolidated.read("META-INF/MANIFEST.MF").decode()
    assert "Automatic-Module-Name: com.example.jetty.core.consolidated" in manifest
    assert "Jetty-Upstream-Commit: " + inventory["commit"] in manifest

print(json.dumps({
    "jar": str(jar_path.resolve()),
    "sha256": sha256(jar_path.read_bytes()).hexdigest(),
    "commit": inventory["commit"],
    "source_and_fixture_files": len(inventory["files"]),
    "upstream_classes": len(expected_classes),
    "additional_package_metadata": len(extra_classes),
    "original_resources": len(expected_resources),
    "config_resources": len(config),
    "services": {entry: sorted(providers) for entry, providers in expected_services.items()},
    "version_metadata": info,
}, indent=2))

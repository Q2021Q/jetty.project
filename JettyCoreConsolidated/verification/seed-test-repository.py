"""Seed only upstream test auxiliaries in an isolated Maven repository."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("upstream_build", type=Path, help="Clean Jetty 12.1.15 checkout after reactor verify")
parser.add_argument("repository", type=Path, help="Isolated Maven repository")
args = parser.parse_args()
root = args.upstream_build.resolve()
repo = args.repository.resolve()
if repo.is_relative_to(root) or repo == Path.home() / ".m2/repository":
    parser.error("Use a repository outside the upstream checkout and the default Maven cache")
project = Path(__file__).resolve().parent.parent
inventory = json.loads((project / "upstream/source-inventory.json").read_text(encoding="utf-8"))
git = ["git", "-c", "safe.directory=" + root.as_posix(), "-C", str(root)]
head = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
if head != inventory["commit"]:
    parser.error(f"Upstream commit is {head}")
selected = {m.rsplit("/", 1)[-1] for m in inventory["modules"]}
tracked = subprocess.check_output(git + ["ls-tree", "-r", "-z", "--name-only", "HEAD"]).decode().split("\0")
ns = {"p": "http://maven.apache.org/POM/4.0.0"}
for artifact in selected:
    originals = list((repo / "org/eclipse/jetty").rglob(f"{artifact}-12.1.15.jar"))
    if originals:
        raise SystemExit(f"Isolated repository already contains selected originals: {originals}")

def copy_verified(source, target):
    if target.exists():
        if source.read_bytes() != target.read_bytes():
            raise SystemExit(f"Use a new isolated repository instead of replacing {target}")
        return
    shutil.copyfile(source, target)

for relative in tracked:
    if relative != "pom.xml" and not relative.endswith("/pom.xml"):
        continue
    pom = root / relative
    if not pom.is_file():
        continue
    model = ET.parse(pom).getroot()
    group = model.findtext("p:groupId", namespaces=ns) or model.findtext("p:parent/p:groupId", namespaces=ns)
    artifact = model.findtext("p:artifactId", namespaces=ns)
    if not group or not group.startswith("org.eclipse.jetty") or artifact in selected:
        continue
    packaging = model.findtext("p:packaging", namespaces=ns) or "jar"
    jar = pom.parent / "target" / f"{artifact}-12.1.15.jar"
    if packaging != "pom" and not jar.is_file():
        continue
    dest = repo / Path(*group.split(".")) / artifact / "12.1.15"
    dest.mkdir(parents=True, exist_ok=True)
    copy_verified(pom, dest / f"{artifact}-12.1.15.pom")
    if jar.is_file():
        copy_verified(jar, dest / jar.name)

print(f"Upstream test auxiliaries prepared in {repo}. Maven resolves other dependencies normally.")

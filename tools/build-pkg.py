#!/usr/bin/env python3
"""Offline build of the FreeBSD .pkg from src/ (no FreeBSD/OPNsense tree needed).

Reuses the manifest of an upstream release pkg (ABI, deps, scripts) and replaces
version, file list + hashes. Usage: build-pkg.py UPSTREAM.pkg OUT_DIR
"""
import hashlib, io, json, os, subprocess, sys, tarfile

up, out = sys.argv[1], sys.argv[2]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ver = next(l.split()[-1] for l in open(root + "/Makefile") if l.startswith("PLUGIN_VERSION"))

raw = subprocess.run(["zstd", "-dc", up], check=True, capture_output=True).stdout
man = json.loads(tarfile.open(fileobj=io.BytesIO(raw)).extractfile("+MANIFEST").read())

files = {}
for line in subprocess.run(["git", "ls-files", "-s", "src"], cwd=root, check=True,
                           capture_output=True, text=True).stdout.splitlines():
    mode, _sha, _stage, path = line.replace("\t", " ").split(" ", 3)
    files["/usr/local/" + path[len("src/"):]] = (path, int(mode, 8) & 0o777)
ver_json = json.loads(json.dumps(man["annotations"]))
ver_json["product_version"] = ver
versionfile = ("{\n" + ",\n".join('    "%s": "%s"' % kv for kv in sorted(
    {k: v for k, v in ver_json.items() if k != "FreeBSD_version"}.items())) + "\n}\n").encode()
blobs = {p: (open(os.path.join(root, s), "rb").read(), m) for p, (s, m) in files.items()}
blobs["/usr/local/opnsense/version/kea-unbound"] = (versionfile, 0o644)

man["version"] = ver
man["annotations"]["product_version"] = ver
man["flatsize"] = sum(len(b) for b, _ in blobs.values())
man["files"] = {p: "1$" + hashlib.sha256(b).hexdigest() for p, (b, _) in sorted(blobs.items())}
compact = {k: v for k, v in man.items() if k not in ("files", "scripts")}

os.makedirs(out, exist_ok=True)
tarpath = os.path.join(out, "os-kea-unbound-%s.tar" % ver)
with tarfile.open(tarpath, "w", format=tarfile.PAX_FORMAT) as t:
    def add(name, data, mode):
        ti = tarfile.TarInfo(name); ti.size = len(data); ti.mode = mode
        ti.uname = ti.gname = ""; ti.uid = ti.gid = 0; ti.mtime = 0
        t.addfile(ti, io.BytesIO(data))
    add("+COMPACT_MANIFEST", json.dumps(compact, separators=(",", ":")).encode(), 0o644)
    add("+MANIFEST", json.dumps(man, separators=(",", ":")).encode(), 0o644)
    for p, (b, m) in sorted(blobs.items()):
        add(p, b, m)
pkg = tarpath[:-4] + ".pkg"
subprocess.run(["zstd", "-q", "-19", "-f", tarpath, "-o", pkg], check=True)
os.remove(tarpath)
print(pkg, os.path.getsize(pkg), "bytes,", len(blobs), "files")

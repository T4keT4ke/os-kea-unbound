#!/usr/bin/env python3
"""Offline build of the os-kea-unbound-gss-tsig package (Kea's GSS-TSIG hook library).

The library comes from the build-gss-tsig CI workflow. The manifest is derived from an
existing os-kea-unbound pkg (ABI, arch), with its own name, file list and the krb5
dependency. Usage: build-hook-pkg.py TEMPLATE.pkg libddns_gss_tsig.so KEA_VERSION OUT_DIR
"""
import hashlib, io, json, os, subprocess, sys, tarfile

tmpl, so, kea_ver, out = sys.argv[1:5]
raw = subprocess.run(["zstd", "-dc", tmpl], check=True, capture_output=True).stdout
man = json.loads(tarfile.open(fileobj=io.BytesIO(raw)).extractfile("+MANIFEST").read())

path = "/usr/local/lib/kea/hooks/libddns_gss_tsig.so"
blob = open(so, "rb").read()
man.update({
    "name": "os-kea-unbound-gss-tsig", "origin": "opnsense/os-kea-unbound-gss-tsig",
    "version": kea_ver,
    "comment": "GSS-TSIG hook library for Kea DHCP-DDNS (Kerberos-signed DNS updates)",
    "desc": "libddns_gss_tsig.so built from the Kea %s sources with Kerberos support, "
            "for os-kea-unbound's GSS-TSIG option. Must match the installed kea package "
            "version exactly; os-kea-unbound checks this before using it." % kea_ver,
    "flatsize": len(blob), "files": {path: "1$" + hashlib.sha256(blob).hexdigest()},
    "deps": {"krb5": {"origin": "security/krb5", "version": "1.22.2"}},
})
man["annotations"] = {k: v for k, v in man["annotations"].items() if not k.startswith("product_")}
man.pop("scripts", None)
compact = {k: v for k, v in man.items() if k != "files"}

os.makedirs(out, exist_ok=True)
tarpath = os.path.join(out, "os-kea-unbound-gss-tsig-%s.tar" % kea_ver)
with tarfile.open(tarpath, "w", format=tarfile.PAX_FORMAT) as t:
    def add(name, data, mode):
        ti = tarfile.TarInfo(name); ti.size = len(data); ti.mode = mode
        ti.uname = ti.gname = ""; ti.uid = ti.gid = 0; ti.mtime = 0
        t.addfile(ti, io.BytesIO(data))
    add("+COMPACT_MANIFEST", json.dumps(compact, separators=(",", ":")).encode(), 0o644)
    add("+MANIFEST", json.dumps(man, separators=(",", ":")).encode(), 0o644)
    add(path, blob, 0o755)
pkg = tarpath[:-4] + ".pkg"
subprocess.run(["zstd", "-q", "-19", "-f", tarpath, "-o", pkg], check=True)
os.remove(tarpath)
print(pkg, os.path.getsize(pkg), "bytes")

#!/usr/local/bin/python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 James (JameZUK)
"""
Keytab handling for the GSS-TSIG option, run as root by configd.

  keytab.py status            -> JSON: does the keytab exist, when, which principals
  keytab.py install <tmpfile> -> validate an uploaded keytab and install it (mode 600)

The web UI (not root) writes the upload to /tmp/keaunbound-keytab-XXXXXX; this script
checks it is a plain keytab file, moves it to the configured path and never prints
key material. The keytab is deliberately NOT stored in config.xml (backups).
"""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

CONFIG = "/conf/config.xml"
DEFAULT = "/usr/local/etc/kea/dhcp.keytab"
KLIST = "/usr/local/bin/klist"
UPLOAD_RE = re.compile(r"^/tmp/keaunbound-keytab-[A-Za-z0-9]+$")
MAX_SIZE = 65536


def destination(config=CONFIG):
    """Configured keytab path; falls back to the default if unset or not under /usr/local/etc/."""
    try:
        node = ET.parse(config).getroot().find("./OPNsense/KeaUnbound/general/gss_keytab")
        path = os.path.normpath((node.text or "").strip()) if node is not None else ""
    except (OSError, ET.ParseError):
        path = ""
    return path if path.startswith("/usr/local/etc/") and path != "/usr/local/etc/" else DEFAULT


def is_keytab(data):
    """MIT/Heimdal keytab files start with 0x05 and format version 0x01 or 0x02."""
    return 0 < len(data) <= MAX_SIZE and data[0] == 5 and data[1:2] in (b"\x01", b"\x02")


def parse_klist(text):
    """[{'kvno': int, 'principal': str}, ...] from `klist -k` output (deduplicated)."""
    out, seen = [], set()
    for line in text.splitlines():
        m = re.match(r"^\s*(\d+)\s+(\S+@\S+)\s*$", line)
        if m and (m.group(1), m.group(2)) not in seen:
            seen.add((m.group(1), m.group(2)))
            out.append({"kvno": int(m.group(1)), "principal": m.group(2)})
    return out


def status():
    path = destination()
    if not os.path.isfile(path):
        return {"exists": False, "path": path, "principals": []}
    st = os.stat(path)
    principals = []
    if os.path.exists(KLIST):
        r = subprocess.run([KLIST, "-k", path], capture_output=True, text=True)
        principals = parse_klist(r.stdout)
    return {"exists": True, "path": path, "size": st.st_size, "modified": int(st.st_mtime),
            "principals": principals}


def install(src):
    if not UPLOAD_RE.match(src):
        return {"status": "error", "message": "unexpected upload path"}
    try:
        st = os.lstat(src)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_SIZE:
            return {"status": "error", "message": "upload is not a regular file or too large"}
        with open(src, "rb") as f:
            data = f.read()
    except OSError as exc:
        return {"status": "error", "message": "cannot read upload: %s" % exc.strerror}
    finally:
        try:
            os.remove(src)
        except OSError:
            pass
    if not is_keytab(data):
        return {"status": "error", "message": "this does not look like a Kerberos keytab file"}
    path = destination()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return {"status": "error", "message": "cannot install keytab: %s" % exc.strerror}
    return {"status": "ok", "path": path}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "status":
        print(json.dumps(status()))
    elif cmd == "install" and len(sys.argv) > 2:
        print(json.dumps(install(sys.argv[2])))
    else:
        print(json.dumps({"status": "error", "message": "usage: keytab.py status|install <file>"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

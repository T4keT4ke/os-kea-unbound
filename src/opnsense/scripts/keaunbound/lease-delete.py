#!/usr/local/bin/python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 James (JameZUK)
"""
Delete Kea leases AND ask Kea to remove their DNS records (update-ddns). Used by the
"All Leases" pages. OPNsense's own delete only sends the address, so Kea leaves the
DNS records behind. Prints JSON {"removed": [...], "failed": [...]}.

    lease-delete.py 192.0.2.5,2001:db8::7
"""

import ipaddress
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import kea_ctrl  # noqa: E402


def parse_ips(arg):
    """Valid addresses from a comma-separated list; None if anything is not an IP."""
    out = []
    for part in (arg or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(str(ipaddress.ip_address(part)))
        except ValueError:
            return None
    return out or None


def delete_leases(ips, send):
    """send(command, service, arguments) -> reply dict or None (kea_ctrl.send_command)."""
    removed, failed = [], []
    v6_types = {}
    if any(":" in ip for ip in ips):
        resp = send("lease6-get-all", "dhcp6", None)
        for lease in ((resp or {}).get("arguments") or {}).get("leases") or []:
            v6_types.setdefault(lease.get("ip-address"), set()).add(lease.get("type"))
    for ip in ips:
        v6 = ":" in ip
        # an address can be both IA_NA and IA_PD base address: delete every type held
        for ltype in (v6_types.get(ip) or {None}) if v6 else {None}:
            args = {"ip-address": ip, "update-ddns": True}
            if ltype:
                args["type"] = ltype
            resp = send("lease6-del" if v6 else "lease4-del", "dhcp6" if v6 else "dhcp4", args)
            if isinstance(resp, dict) and resp.get("result") == 0:
                removed.append(ip)
            else:
                failed.append("%s: %s" % (ip, (resp or {}).get("text", "no reply from Kea")))
    return {"removed": removed, "failed": failed}


def main():
    ips = parse_ips(sys.argv[1] if len(sys.argv) > 1 else "")
    if ips is None:
        print(json.dumps({"removed": [], "failed": ["invalid address list"]}))
        return 1
    send = lambda cmd, svc, args: kea_ctrl.send_command(cmd, service=svc, arguments=args)
    print(json.dumps(delete_leases(ips, send)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/local/bin/python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 James (JameZUK)
"""
Emit every address of one family (argv[1]: 4|6) Kea has handed out or reserved as a JSON array for the
"All Leases" pages: active leases plus static reservations (including those whose
device currently holds no lease), so "which IPs are taken" is one list.

Row: address, type (static|dynamic), status (active|reserved), hostname, hwaddr,
subnet, expires (epoch, 0 = none). Read-only; never touches Kea or Unbound.
"""

import ipaddress
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import kea_source, kea_ctrl  # noqa: E402
from lib import records as R          # noqa: E402
from lib import suffix as suffixmod   # noqa: E402


def reservation_rows(cfg, family):
    """[(ip, hostname, hwaddr, subnet_id)] from a generated Kea dhcp4/6 config dict."""
    root = (cfg or {}).get("Dhcp4" if family == "4" else "Dhcp6") or {}
    subnet_key = "subnet4" if family == "4" else "subnet6"
    groups = [(root.get("reservations") or [], "")]
    for sn in suffixmod.iter_subnets(root, subnet_key):
        groups.append((sn.get("reservations") or [], str(sn.get("id", "") or "")))
    out = []
    for resv, sid in groups:
        for r in resv:
            ips = list(r.get("ip-addresses") or [])
            if r.get("ip-address"):
                ips.append(r["ip-address"])
            hw = r.get("hw-address") or r.get("duid") or r.get("client-id") or ""
            for ip in ips:
                out.append((ip, r.get("hostname") or "", hw, sid))
    return out


def build_rows(reservations, leases):
    """Merge reservations and active leases keyed by normalised IP. A lease at a
    reserved IP makes that row 'active' (live hwaddr/expiry win); a reservation with
    no lease stays 'reserved'; a lease with no reservation is 'dynamic'."""
    rows = {}
    for ip, host, hw, sid in reservations:
        n = R._norm_ip(ip)
        if n:
            rows[n] = {"address": n, "type": "static", "status": "reserved",
                       "hostname": host, "hwaddr": hw, "subnet": sid, "expires": 0}
    for ip, host, hw, sid, expires in leases:
        n = R._norm_ip(ip)
        if not n:
            continue
        row = rows.get(n)
        if row:
            row["status"] = "active"
            row["hwaddr"] = hw or row["hwaddr"]
            row["hostname"] = row["hostname"] or host
            row["expires"] = expires
        else:
            rows[n] = {"address": n, "type": "dynamic", "status": "active",
                       "hostname": host, "hwaddr": hw, "subnet": sid, "expires": expires}
    ordered = sorted(rows.values(), key=lambda r: (ipaddress.ip_address(r["address"]).version,
                                                   int(ipaddress.ip_address(r["address"]))))
    for i, r in enumerate(ordered):
        r["id"] = i
    return ordered


def _leases(family):
    cmd = "lease4-get-all" if family == "4" else "lease6-get-all"
    resp = kea_ctrl.send_command(cmd, service="dhcp4" if family == "4" else "dhcp6")
    if not (isinstance(resp, dict) and resp.get("result") == 0):
        return []
    out = []
    for lease in (resp.get("arguments") or {}).get("leases") or []:
        try:
            if int(lease.get("state", 0) or 0) != 0:
                continue
            if family == "6" and lease.get("type") not in (None, "IA_NA"):
                continue
            exp = int(lease.get("cltt", 0) or 0) + int(lease.get("valid-lft", 0) or 0)
        except (ValueError, TypeError):
            continue
        if lease.get("ip-address"):
            out.append((lease["ip-address"], lease.get("hostname", "") or "",
                        lease.get("hw-address") or lease.get("duid") or "",
                        str(lease.get("subnet-id", "") or ""), exp))
    return out


def main():
    fam = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("4", "6") else "4"
    path = kea_source.KEA4 if fam == "4" else kea_source.KEA6
    resv = reservation_rows(kea_source._load_json(path), fam)
    leases = _leases(fam)
    print(json.dumps(build_rows(resv, leases)))


if __name__ == "__main__":
    main()

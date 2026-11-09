#!/usr/local/bin/python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 James (JameZUK)
"""
Emit every address of one family (argv[1]: 4|6) as JSON {"records": [...]} for the
"All Leases" pages: active Kea leases plus static reservations, including those whose
device currently holds no lease, so "which IPs are taken" is one list. The record
fields follow OPNsense's own Kea lease listing (get_kea_leases.py) so the page can
look and behave like it. Reservation-only rows carry state -1.

Read-only; never touches Kea or Unbound.
"""

import ipaddress
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import kea_source, kea_ctrl  # noqa: E402
from lib import records as R          # noqa: E402
from lib import suffix as suffixmod   # noqa: E402

NO_LEASE = -1  # state of a reservation nobody holds a lease for


def interface_ranges(proto):
    """{ip_network: ifname} from ifconfig, to group addresses by interface."""
    ranges, this_if = {}, None
    prefix = "\tinet6" if proto == "6" else "\tinet "
    out = subprocess.run(["/sbin/ifconfig", "-f", "inet:cidr,inet6:cidr"],
                         capture_output=True, text=True).stdout
    for line in out.split("\n"):
        if not line.startswith("\t") and ":" in line:
            this_if = line.strip().split(":")[0]
        elif this_if and line.startswith(prefix) and "-->" not in line:
            try:
                ranges[ipaddress.ip_network(line.split()[1], strict=False)] = this_if
            except ValueError:
                pass
    return ranges


def reservations(cfg, family):
    """Reservation dicts {ip, hostname, hwaddr, client_id, duid, subnet} from a
    generated Kea dhcp4/6 config dict (global, per-subnet and shared-network)."""
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
            for ip in ips:
                out.append({"ip": ip, "hostname": r.get("hostname") or "",
                            "hwaddr": r.get("hw-address") or "",
                            "client_id": (r.get("client-id") or "").replace(":", ""),
                            "duid": r.get("duid") or "", "subnet": sid})
    return out


def _kinds(resv, family):
    """Which identifiers a reservation matches on (core's is_reserved)."""
    kinds = []
    if resv["hwaddr"]:
        kinds.append("hwaddr")
    if family == "4" and resv["client_id"]:
        kinds.append("client_id")
    if family == "6" and resv["duid"]:
        kinds.append("duid")
    return kinds


def _interface(address, ranges):
    try:
        net = ipaddress.ip_network(address)
    except ValueError:
        return None
    return next((name for rng, name in ranges.items() if rng.overlaps(net)), None)


def build_records(family, resvs, leases, ranges):
    """Merge reservations and active leases keyed by normalised IP. A lease at a
    reserved IP is shown as that lease flagged static (live data wins); a
    reservation without a lease stays as a state -1 row; the rest are dynamic."""
    by_ip = {}
    for r in resvs:
        n = R._norm_ip(r["ip"])
        if n:
            by_ip[n] = r
    rows, seen = [], set()
    for lease in leases:
        addr = lease.get("ip-address")
        n = R._norm_ip(addr) if addr else None
        resv = by_ip.get(n)
        seen.add(n)
        rows.append({
            "address": addr, "prefix_len": lease.get("prefix-len", 128),
            "type": lease.get("type", ""), "hwaddr": lease.get("hw-address", ""),
            "duid": lease.get("duid", ""), "client_id": lease.get("client-id", ""),
            "iaid": lease.get("iaid", ""), "valid_lifetime": lease.get("valid-lft", 0),
            "expire": lease.get("cltt", 0) + lease.get("valid-lft", 0),
            "hostname": lease.get("hostname", ""), "state": lease.get("state", 0),
            "if": _interface(addr, ranges) if addr else None,
            "is_reserved": _kinds(resv, family) if resv else [],
        })
    for n, r in by_ip.items():
        if n in seen:
            continue
        rows.append({
            "address": n, "prefix_len": 128 if family == "6" else 32,
            "type": "IA_NA" if family == "6" else "", "hwaddr": r["hwaddr"],
            "duid": r["duid"], "client_id": r["client_id"], "iaid": "",
            "valid_lifetime": 0, "expire": 0, "hostname": r["hostname"],
            "state": NO_LEASE, "if": _interface(n, ranges),
            "is_reserved": _kinds(r, family) or ["hwaddr"],
        })
    return rows


def main():
    fam = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("4", "6") else "4"
    path = kea_source.KEA4 if fam == "4" else kea_source.KEA6
    resp = kea_ctrl.send_command("lease4-get-all" if fam == "4" else "lease6-get-all",
                                 service="dhcp4" if fam == "4" else "dhcp6")
    leases = []
    if isinstance(resp, dict) and resp.get("result") == 0:
        leases = (resp.get("arguments") or {}).get("leases") or []
    rows = build_records(fam, reservations(kea_source._load_json(path), fam),
                         leases, interface_ranges(fam))
    print(json.dumps({"records": rows}))


if __name__ == "__main__":
    main()

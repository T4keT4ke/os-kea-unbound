# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 James (JameZUK)
"""
Reverse-zone -> DNS-server mapping (setting `reverse_zones`).

Kea's D2 can send PTR updates straight to an external DNS server (e.g. an Active
Directory DC) instead of our loopback listener. One line per zone:

    124.10.in-addr.arpa = 10.124.1.14, 10.124.0.8     # first server, then fallback
    124.10.in-addr.arpa = 10.124.1.14, 10.124.0.8 gss # sign with GSS-TSIG (Kerberos)

Pure helpers (no I/O) shared by the config injector and the tests.
"""

import ipaddress

_SUFFIXES = (".in-addr.arpa", ".ip6.arpa")


def parse_reverse_zones(text):
    """([(zone_with_trailing_dot, [ip, ...], gss), ...], [bad_line, ...]).

    `gss` is True when the line ends with the keyword `gss`.

    Blank lines and `#` comments are ignored. A line is rejected (and reported) when
    the zone isn't under in-addr.arpa/ip6.arpa or it has no valid server address, so
    a typo never reaches Kea's config. A zone repeated on several lines keeps the
    first definition."""
    zones, bad, seen = [], [], set()
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        zone, sep, rest = line.partition("=")
        zone = zone.strip().strip(".").lower()
        ips, gss = [], False
        for part in rest.replace(";", ",").replace(" ", ",").split(","):
            part = part.strip()
            if not part:
                continue
            if part.lower() == "gss":
                gss = True
                continue
            try:
                ips.append(str(ipaddress.ip_address(part)))
            except ValueError:
                ips = []
                break
        if not sep or not ips or not zone.endswith(_SUFFIXES) or zone in _SUFFIXES:
            bad.append(raw.strip())
            continue
        if zone not in seen:
            seen.add(zone)
            zones.append((zone + ".", ips, gss))
    return zones, bad


def parse_gss_servers(text):
    """({ip: dns_server_fqdn}, [bad_line, ...]) from lines `10.0.0.1 = dc01.example.com`.

    The FQDN becomes the Kerberos service principal DNS/<fqdn>@REALM of that server."""
    out, bad = {}, []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        ip, sep, fqdn = line.partition("=")
        fqdn = fqdn.strip().strip(".").lower()
        try:
            ip = str(ipaddress.ip_address(ip.strip()))
        except ValueError:
            ip = ""
        if not sep or not ip or not fqdn or any(c in fqdn for c in " /@,;"):
            bad.append(raw.strip())
            continue
        out.setdefault(ip, fqdn)
    return out, bad

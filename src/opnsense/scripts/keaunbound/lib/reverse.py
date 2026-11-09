# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 James (JameZUK)
"""
Reverse-zone -> DNS-server mapping (setting `reverse_zones`).

Kea's D2 can send PTR updates straight to an external DNS server (e.g. an Active
Directory DC) instead of our loopback listener. One line per zone:

    124.10.in-addr.arpa = 10.124.1.14, 10.124.0.8     # first server, then fallback

Pure helpers (no I/O) shared by the config injector and the tests.
"""

import ipaddress

_SUFFIXES = (".in-addr.arpa", ".ip6.arpa")


def parse_reverse_zones(text):
    """([(zone_with_trailing_dot, [ip, ...]), ...], [bad_line, ...]).

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
        ips = []
        for part in rest.replace(";", ",").replace(" ", ",").split(","):
            part = part.strip()
            if not part:
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
            zones.append((zone + ".", ips))
    return zones, bad

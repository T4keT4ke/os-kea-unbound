# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 James (JameZUK)
"""
Minimal Kerberos client config for the GSS-TSIG hook, generated from plugin settings.
Pure helpers (no I/O) so the injector and the tests share them.
"""

import re

MARKER = "# managed by os-kea-unbound (GSS-TSIG) - edits are overwritten"
_HOST = re.compile(r"^[0-9A-Za-z._:-]+$")


def parse_kdcs(text):
    """KDC host names / addresses from a comma-, semicolon- or whitespace-separated
    list; entries with odd characters are dropped (they end up in the config file)."""
    out = []
    for tok in re.split(r"[,;\s]+", text or ""):
        if tok and _HOST.match(tok) and tok not in out:
            out.append(tok)
    return out


def render_krb5_conf(realm, kdcs, domain=""):
    """krb5.conf text. rdns = false: Active Directory service principals are built from
    the name we were given, a reverse lookup would only break them."""
    lines = [MARKER, "[libdefaults]",
             "    default_realm = %s" % realm,
             "    rdns = false",
             "    dns_lookup_kdc = %s" % ("false" if kdcs else "true"),
             "    dns_lookup_realm = false",
             "", "[realms]", "    %s = {" % realm]
    lines += ["        kdc = %s" % k for k in kdcs]
    lines += ["    }"]
    domain = (domain or "").strip().strip(".").lower()
    if domain and _HOST.match(domain):
        lines += ["", "[domain_realm]", "    .%s = %s" % (domain, realm),
                  "    %s = %s" % (domain, realm)]
    return "\n".join(lines) + "\n"

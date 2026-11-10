#!/usr/local/bin/python3
# SPDX-License-Identifier: BSD-2-Clause
"""
Safety net for the optional GSS-TSIG hook after OPNsense updates.

Kea only loads libddns_gss_tsig.so if it was built for the installed Kea (and its
libraries). After an update that changes Kea, the config on disk may still name the
now-incompatible hook, and kea-dhcp-ddns (D2) would refuse to start: no DNS updates
at all. DHCP itself is not affected.

This re-runs the injector (kea-config-sync.py), which asks `kea-dhcp-ddns -t` whether
the hook still loads and drops it when it does not (the GSS zones then fall back to
unsigned updates, the log says why). It also puts the hook back once a matching
package is installed. If the Kea configs changed, Kea is restarted so the running
daemons match the files. Run after updates, at plugin start and daily (periodic).
A no-op when the plugin is disabled or nothing needs to change.
"""

import importlib.util
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIGCTL = "/usr/local/sbin/configctl"


def load_injector():
    spec = importlib.util.spec_from_file_location("kea_config_sync",
                                                  os.path.join(HERE, "kea-config-sync.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def log(m, msg):
    try:
        os.makedirs(os.path.dirname(m.LOG), exist_ok=True)
        with open(m.LOG, "a") as f:
            f.write("%s [INFO] hook-guard: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def guard(m=None, restart=None):
    """Returns a one-line result. `restart` is injectable for tests."""
    m = m or load_injector()
    s, changed = m.run()
    if s is None:
        return "plugin disabled, nothing to check"
    kea = [c for c in changed if c in ("dhcp4", "dhcp6", "ddns")]
    if not kea:
        return "ok, no change"
    msg = "Kea config corrected (%s); restarting Kea" % ", ".join(kea)
    log(m, msg)
    if restart is None:
        restart = lambda: subprocess.run([CONFIGCTL, "kea", "restart"],
                                         capture_output=True, timeout=120)
    try:
        restart()
    except (OSError, subprocess.SubprocessError) as e:
        msg += "; restart failed: %s" % e
        log(m, "restart failed: %s" % e)
    return msg


if __name__ == "__main__":
    print("keaunbound hook-guard: " + guard())
    sys.exit(0)

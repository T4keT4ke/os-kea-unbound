# os-kea-unbound (DDNS edition)

**OPNsense plugin: automatically register dynamic Kea DHCP leases in Unbound DNS — forward and reverse, with no core-file patching.**

> **Fork.** This is a fork of [JameZUK/os-kea-unbound](https://github.com/JameZUK/os-kea-unbound)
> (based on its 0.14.2) with a few additions: *All Leases* pages that also list static
> reservations, PTR registration in an external DNS server (e.g. Active Directory), and an
> *authoritative* DHCPv4 switch. See *[Additions in this fork](#additions-in-this-fork)*.

When a device picks up a DHCP lease, its hostname starts resolving in Unbound within
moments (A/AAAA **and** PTR) and keeps resolving across Unbound restarts and reboots,
for as long as the lease is valid.

<p align="center">
  <img src="docs/img/menu.png" alt="Find it under Services → Kea Unbound DDNS" width="210"><br>
  <sub><i>Services → Kea Unbound DDNS</i></sub>
</p>
<p align="center">
  <img src="docs/img/status.png" alt="Status page — enabled, listener running, records registered" width="760"><br>
  <sub><i>Status page — up and running</i></sub>
</p>

> This is the rewritten `0.x` line. It replaces the old **v3.x** plugin — which
> patched OPNsense's Kea files at install time — with a clean plugin built on Kea's
> *native* Dynamic DNS. Nothing in core is touched, so OPNsense upgrades can't break
> it and uninstall is trivially clean. See **[How it works](docs/HOW-IT-WORKS.md)**.

## Features

- **Automatic** — dynamic leases are registered on grant/renew and removed on
  release/expiry, forward (A/AAAA) and reverse (PTR).
- **Global by default, per-VLAN when you want it** — zero per-subnet setup out of the
  box; optionally give each subnet its own domain so leases resolve under their VLAN's
  zone (see *[Per-VLAN domains](#per-vlan-domains)*).
- **Leaves your static DNS alone** — DHCP reservations and Host Overrides stay
  OPNsense's; the plugin never adds, deletes, or prunes them. To have reserved clients
  resolve by name too, tick **Services → Unbound DNS → General → Register DHCP Static
  Mappings**: OPNsense then registers every Kea reservation that has a hostname, forward
  and reverse. (Core does this for Kea on 26.7; the checkbox is still labelled for ISC.)
- **Survives restarts** — records persist across Unbound restarts and reboots, no
  repopulation wait.
- **Secure by default** — TSIG-authenticated; the listener rejects unsigned,
  wrong-key, and wrong-algorithm updates.
- **Clean uninstall** — nothing in core is patched, so there is nothing to undo.

## Additions in this fork

- **All Leases IPv4 / IPv6** (Services → Kea DHCP): OPNsense's *Leases DHCPv4/v6* view,
  extended with the static reservations whose device holds no lease right now (state
  *reserved (no lease)*). Grouped by interface, with MAC vendor, state, static/dynamic and
  the same add/find reservation and delete actions. One list shows which addresses are
  taken — static and dynamic.
- **Reverse zones (PTR)** *(experimental, not yet field-tested)*: register PTR records for
  listed reverse zones straight at an external DNS server through Kea's DDNS daemon
  (D2), replacing hand-made `nsupdate` hook scripts. Needs zones that allow
  non-secure dynamic updates, or sign them with **GSS-TSIG** (Kerberos) for secure-only
  zones. See *Configure* and *[GSS-TSIG](#gss-tsig-kerberos-signed-updates)*.
- **Authoritative DHCPv4** *(experimental, not yet field-tested)*: Kea answers requests for
  unknown addresses with a NAK right away instead of ignoring them.

## Requirements

- OPNsense 26.1+ (Kea is the DHCP server)
- Kea DHCPv4 and/or DHCPv6 enabled, with Unbound as the resolver
- `py313-dnspython` (installed automatically by `pkg`)

## Install

**OPNsense 26.7+ (FreeBSD 15, amd64) — this fork:**

```sh
pkg add https://github.com/T4keT4ke/os-kea-unbound/releases/download/v0.16.2/os-kea-unbound-0.16.2.pkg
```

Packages are architecture-stamped (`FreeBSD:15:amd64`), so this one won't install on
FreeBSD 14. This fork publishes FreeBSD 15 packages only. On **OPNsense 26.1
(FreeBSD 14)** use the [upstream plugin](https://github.com/JameZUK/os-kea-unbound/releases)
(0.14.0) or [build from source](docs/HOW-IT-WORKS.md#build-from-source), which always
matches your running system.

If the fork's package is already installed, add `-f` to `pkg add` to reinstall over it.
Disable the plugin first when switching from the upstream package.

### The "misconfigured" / "unknown-repository" label

After installing from the `.pkg`, **System → Firmware → Packages** marks the plugin
`misconfigured` and `unknown-repository`. **This is cosmetic — the plugin is fully
installed and runs normally.** It happens because you installed from a downloaded file
rather than from a pkg repository OPNsense tracks, so OPNsense never added the plugin to
its managed-plugin list (installing *from a file* never does). To clear both labels, have
OPNsense register the installed plugin into that list:

```sh
configctl firmware resync
```

This is safe and reinstalls nothing. OPNsense still won't auto-update the plugin (it isn't
served from a repository), so you update it by installing the next release file yourself.

## Migrating from the old v3.x plugin

The old v3.x plugin and this one share the package name `os-kea-unbound`, but they're
different plugins — v3.x patched core Kea files; this one uses Kea's native DDNS. **Don't
upgrade in place; remove the old one cleanly first, then install this.**

1. **Detach the old plugin:** Services → Kea DHCP → **Kea DHCPv4** *and* **Kea DHCPv6**
   → Settings → untick **Register Leases in Unbound (via os-kea-unbound)** → **Save**.
   (This removes its hooks from Kea's config.)
2. **Remove it:** `pkg delete os-kea-unbound` — this undoes the old plugin's core-file
   patches and scrubs its Kea hook entry.
3. **Restart Kea** (Services → Kea DHCP → restart DHCPv4/DHCPv6) so Kea runs cleanly.
4. **Install this version** (see *Install* above), then **enable** it at its new home:
   Services → **Kea Unbound DDNS** → Settings.

> The version number goes *down* (3.8.x → 0.x), so a normal package "upgrade" won't
> offer it — the delete-then-install above is the supported path. Your DHCP reservations
> and Host Overrides are untouched throughout; dynamic records repopulate automatically
> once you enable this plugin.

## Configure

**Services → Kea Unbound DDNS → Settings**, tick **Enable**, click **Save**. That's
it — the plugin wires up Kea's DDNS, generates a TSIG key, and seeds existing leases.

![Settings](docs/img/settings.png)

| Setting | Default | Notes |
|---|---|---|
| Enable | off | Master switch. |
| Qualifying suffix | *(firewall domain)* | The forward zone; blank uses the system domain. |
| Authoritative DHCPv4 | off | Kea answers requests for unknown addresses with a NAK at once. |
| Reverse zones (PTR) † | *(empty)* | Experimental. Register PTRs for listed reverse zones straight at an external DNS server (e.g. Active Directory), one line per zone: `124.10.in-addr.arpa = 10.124.1.14, 10.124.0.8` (first server, then fallback). Sent via Kea's DDNS daemon **unsigned**, so the zone must allow non-secure dynamic updates. Listed zones are not written to Unbound. Applies after the next Kea config regeneration (Save/Apply in Kea). |
| GSS-TSIG (Kerberos) † | off | Experimental. Sign PTR updates for reverse zones that end in `gss`. Needs the `os-kea-unbound-gss-tsig` package, realm, client principal, keytab and the DNS servers' host names (see below). |
| Aggressive cleanup | on | Drop a host's old address when it moves to a new one. |
| Update on renew † | on | Refresh DNS on renewals, not just first grant. |
| TSIG authentication | on | Sign updates with an auto-generated key (unsigned/wrong-key are rejected). |
| TSIG algorithm † | hmac-sha256 | `hmac-sha256`, `-sha512`, or `-sha1`. |
| Listener port † | 53535 | Loopback only. |

† Shown only under **advanced mode** (toggle at the top of the form). The defaults are fine for almost everyone.

### Per-VLAN domains

By default every dynamic lease is qualified with a single suffix (the **Qualifying
suffix** above, or the firewall's system domain). If you run multiple VLANs and want
each to register under its **own** domain, just set a per-subnet **Domain name** — the
plugin picks it up automatically:

**Services → Kea DHCP → KEA DHCPv4 (or DHCPv6) → Subnets → (edit a subnet)**

1. Untick **Automatically collect option data** — otherwise OPNsense overwrites the
   domain with the firewall's system domain, so every VLAN looks the same.
2. Set **Domain name** to that VLAN's domain, e.g. `iot.lan`.
3. **Save**, then apply.

Leases on that subnet now resolve under its own domain (e.g. `camera.iot.lan`), forward
and reverse. Subnets you don't touch keep using the global suffix, so this is fully
opt-in. Behind the scenes the plugin gives each subnet its own Kea
`ddns-qualifying-suffix` and registers a DDNS forward zone per distinct domain, so every
suffix is routed to the listener correctly.

### GSS-TSIG (Kerberos-signed updates)

*Experimental: the Kea hook loads on OPNsense 26.7, but signed updates against Active
Directory have not been field-tested yet.*

OPNsense's Kea package ships **without** the GSS-TSIG hook (`libddns_gss_tsig.so`), although
the code is part of the open-source Kea since 3.0. This fork builds it in CI
(`.github/workflows/build-gss-tsig.yml`) against OPNsense's own libraries and ships it as
a separate package, which must match the installed `kea` version exactly:

```sh
pkg add https://github.com/T4keT4ke/os-kea-unbound/releases/download/v0.17.0/os-kea-unbound-gss-tsig-3.0.4.pkg
```

Without it the plugin works as before; zones marked `gss` then fall back to unsigned
updates and the plugin log says why. Before using the hook, the plugin checks it with
`kea-dhcp-ddns -t`, so a hook that doesn't fit the installed Kea (e.g. after an OPNsense
update that changed Kea) is left out instead of stopping the DDNS daemon. Rebuild the
hook for the new Kea version (run the workflow with that version) when that happens.

Setup with Active Directory (see the Kea manual, *GSS-TSIG*):

1. **AD:** create a user for the firewall, set its SPN and export a keytab on a DC:
   `setspn -S DHCP/fw.ad.example.com kea` and
   `ktpass -princ DHCP/fw.ad.example.com@AD.EXAMPLE.COM -mapuser kea +rndpass -mapop set -ptype KRB5_NT_PRINCIPAL -out dhcp.keytab`
2. **Firewall:** upload the keytab in the plugin settings (*GSS-TSIG keytab*; it is stored
   as `/usr/local/etc/kea/dhcp.keytab`, mode 600, never in `config.xml`), and
   `pkg install krb5`. Use one account and keytab per firewall if you can: you can then
   revoke a site on its own, and running `ktpass` again for a shared principal
   invalidates every copy. Time must be in sync with the DC. `krb5.conf` can come
   from the plugin: enter the KDCs (and optionally the DNS domain) in the settings and
   it writes `/usr/local/etc/krb5.conf` (the file is marked as managed; a `krb5.conf`
   you made yourself is never overwritten). Leave the KDC field empty to manage it by hand.
3. **Plugin settings:** tick *GSS-TSIG*, enter realm, KDCs and client principal, add the DNS
   servers' host names under *GSS DNS servers* (`10.0.0.10 = dc01.ad.example.com`) and
   end the zone's line in *Reverse zones* with `gss`:
   `10.in-addr.arpa = 10.0.0.10, 10.0.0.11 gss`. Switch the zone to *Secure only* in
   Windows once it works.
4. The reverse zone must exist in Windows DNS; a missing one gives the cryptic
   *"Packet was replayed in wrong direction"* error.

## Status & Records

**Status** shows listener health, the registered record count, TSIG state, the
effective qualifying suffix, a **Sync now** button, a **Remove stale records** button,
and a live activity log.

**Remove stale records** prunes any records Unbound still holds that Kea no longer knows
about (an expired or released lease, or a host that moved to another VLAN). It applies
the removals to the running Unbound straight away, so there's no need to stop the plugin
or restart Unbound. It's safe in an HA setup: if it can't confirm a current lease list
from Kea it does nothing rather than risk removing good records, and it refuses to bulk
remove an unusually large number at once.

**All Leases IPv4 / IPv6** (under *Services → Kea DHCP*) lists leases and static
reservations together, see *[Additions in this fork](#additions-in-this-fork)*.

**Records** lists every registered record, enriched with the matching Kea lease detail
(hostname, MAC/DUID, subnet, source, expiry, TTL) — searchable and sortable.

![Records](docs/img/records.png)

### CLI

```sh
configctl keaunbound status      # listener state
configctl keaunbound sync        # re-seed existing leases
configctl keaunbound clean       # prune records Kea no longer knows about
configctl keaunbound records     # list registered records (JSON)
configctl keaunbound log 500     # tail the activity log
```

### Verify it's working

1. **Services → Kea Unbound DDNS → Status** — the listener should show **running**, with a
   record count and the qualifying suffix you expect.
2. **Records** (same menu) — your current DHCP clients should be listed, each with its
   matching lease detail.
3. **Resolve a name.** Pick a client from the Records page, then query the firewall's own
   resolver, forward and reverse:

   ```sh
   drill myclient.mydomain @127.0.0.1    # forward → returns the lease address
   drill -x 192.0.2.50 @127.0.0.1        # reverse → returns the name
   ```

   The same lookups work from any machine on the network — point them at the firewall's
   address instead of `127.0.0.1`.

The [CLI](#cli) commands above do the same from a shell: `status` for listener state,
`records` to list what's registered, and `log` to watch a lease register or drop in real
time.

## Uninstall

Untick **Enable → Save** (reverts everything cleanly), or `pkg delete os-kea-unbound`.
Because nothing in core was patched, there is nothing else to undo.

## Documentation

- **[Upstream project](https://github.com/JameZUK/os-kea-unbound)** — the original
  plugin by JameZUK; all credit for the DDNS design goes there.
- **[How it works](docs/HOW-IT-WORKS.md)** — architecture, what it manages and leaves
  alone, why it replaces v3.x, the Unbound "manual overwrites" notice, and building
  from source.
- **[Testing](docs/TESTING.md)** — the unit and live integration suites, and the
  production test pass.
- **[PLAN.md](PLAN.md)** — full design notes and history.

## License

BSD-2-Clause.

from lib import reverse


def test_parse_reverse_zones():
    zones, bad = reverse.parse_reverse_zones(
        "# comment\n"
        "124.10.IN-ADDR.ARPA = 10.124.1.14, 10.124.0.8   # DCs\n"
        "\n"
        "8.b.d.0.1.0.0.2.ip6.arpa. = 2001:db8::53\n"
        "124.10.in-addr.arpa = 192.0.2.1\n"      # duplicate zone: first wins
    )
    assert zones == [("124.10.in-addr.arpa.", ["10.124.1.14", "10.124.0.8"], False),
                     ("8.b.d.0.1.0.0.2.ip6.arpa.", ["2001:db8::53"], False)]
    assert bad == []


def test_parse_reverse_zones_rejects_bad_lines():
    zones, bad = reverse.parse_reverse_zones(
        "example.com = 10.0.0.1\n"               # not a reverse zone
        "in-addr.arpa = 10.0.0.1\n"              # bare root of the tree: too broad
        "10.in-addr.arpa = not-an-ip\n"          # no valid server
        "10.in-addr.arpa\n"                       # no '='
        "10.in-addr.arpa = 10.0.0.1, bad\n"      # one bad address spoils the line
    )
    assert zones == []
    assert len(bad) == 5
    assert reverse.parse_reverse_zones(None) == ([], [])


def test_parse_reverse_zones_gss_flag():
    zones, bad = reverse.parse_reverse_zones("10.in-addr.arpa = 10.0.0.1, 10.0.0.2 gss\n"
                                              "11.in-addr.arpa = 10.0.0.3\n")
    assert zones == [("10.in-addr.arpa.", ["10.0.0.1", "10.0.0.2"], True),
                     ("11.in-addr.arpa.", ["10.0.0.3"], False)] and bad == []
    assert reverse.parse_reverse_zones("10.in-addr.arpa = gss")[1] == ["10.in-addr.arpa = gss"]


def test_parse_gss_servers():
    out, bad = reverse.parse_gss_servers(
        "# DCs\n10.0.0.1 = DC01.Example.COM.\n10.0.0.2=dc02.example.com  # second\n"
        "bad = x.example.com\n10.0.0.3 = nodots/x\n10.0.0.4\n")
    assert out == {"10.0.0.1": "dc01.example.com", "10.0.0.2": "dc02.example.com"}
    assert len(bad) == 3

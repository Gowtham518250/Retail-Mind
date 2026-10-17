from host_validation import build_allowed_hosts, build_allowed_origins


def test_current_render_hostname_is_allowed_when_configured_hosts_are_stale():
    hosts = build_allowed_hosts({
        "ALLOWED_HOSTS": "localhost,127.0.0.1,retail-mind-vkbp.onrender.com",
        "RENDER_EXTERNAL_HOSTNAME": "retail-mind-hpx3.onrender.com",
    })

    assert "retail-mind-hpx3.onrender.com" in hosts
    assert "retail-mind-vkbp.onrender.com" in hosts
    assert "evil.example" not in hosts


def test_render_url_fallback_extracts_only_its_hostname():
    hosts = build_allowed_hosts({
        "ALLOWED_HOSTS": "localhost",
        "RENDER_EXTERNAL_URL": "https://retail-mind-hpx3.onrender.com/",
    })

    assert "retail-mind-hpx3.onrender.com" in hosts
    assert "https://retail-mind-hpx3.onrender.com/" not in hosts


def test_render_hostname_is_also_in_exact_cors_origins():
    hosts = build_allowed_hosts({
        "ALLOWED_HOSTS": "localhost",
        "RENDER_EXTERNAL_HOSTNAME": "retail-mind-hpx3.onrender.com",
    })
    origins = build_allowed_origins(hosts, "https://retail-mind-web.onrender.com")

    assert "https://retail-mind-hpx3.onrender.com" in origins
    assert "https://retail-mind-web.onrender.com" in origins
    assert origins.count("https://retail-mind-hpx3.onrender.com") == 1


def test_local_origins_and_explicit_origins_are_preserved():
    hosts = build_allowed_hosts({"ALLOWED_HOSTS": "localhost,127.0.0.1"})
    origins = build_allowed_origins(hosts, "https://custom-frontend.example, ")

    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:8000" in origins
    assert "https://custom-frontend.example" in origins


def test_public_origins_only_allow_https():
    hosts = build_allowed_hosts({"ALLOWED_HOSTS": "api.example.com"})
    origins = build_allowed_origins(hosts)

    assert "https://api.example.com" in origins
    assert "http://api.example.com" not in origins


def test_explicit_origins_reject_wildcards_paths_and_cleartext_public_http():
    hosts = build_allowed_hosts({"ALLOWED_HOSTS": "localhost"})
    origins = build_allowed_origins(
        hosts,
        "*, https://good.example.com, https://bad.example.com/path, "
        "http://insecure.example.com, https://user:pass@creds.example.com, "
        "https://query.example.com/?x=1, http://localhost:5173",
    )

    assert "https://good.example.com" in origins
    assert "http://localhost:5173" in origins
    assert "*" not in origins
    assert "https://bad.example.com" not in origins
    assert "http://insecure.example.com" not in origins
    assert "https://creds.example.com" not in origins
    assert "https://query.example.com" not in origins

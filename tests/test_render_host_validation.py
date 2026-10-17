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

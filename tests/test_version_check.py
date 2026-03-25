import os

from polyapi import version_check


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_get_instance_tag_from_base_url():
    assert version_check.get_instance_tag_from_base_url("https://dev.polyapi.io") == "develop"
    assert version_check.get_instance_tag_from_base_url("https://develop.polyapi.io") == "develop"
    assert version_check.get_instance_tag_from_base_url("https://staging.polyapi.io") == "staging"
    assert version_check.get_instance_tag_from_base_url("https://test.polyapi.io") == "test"
    assert version_check.get_instance_tag_from_base_url("https://na2.polyapi.io") == "na2"
    assert version_check.get_instance_tag_from_base_url("https://eu1.polyapi.io") == "eu1"
    assert version_check.get_instance_tag_from_base_url("https://na1.polyapi.io") == "na1"
    assert version_check.get_instance_tag_from_base_url("not-a-url") is None


def test_check_version_non_interactive_warns(monkeypatch, capsys):
    monkeypatch.delenv("POLY_VERSION_REEXEC_GUARD", raising=False)
    monkeypatch.setenv("POLY_API_KEY", "k")
    monkeypatch.setenv("POLY_API_BASE_URL", "https://eu1.polyapi.io")

    monkeypatch.setattr(version_check, "get_api_key_and_url", lambda: ("k", "https://eu1.polyapi.io"))
    monkeypatch.setattr(version_check, "_get_client_version", lambda: "1.0.0")
    monkeypatch.setattr(
        version_check,
        "http_get",
        lambda *args, **kwargs: _FakeResponse({"python": "1.2.0", "typescript": "1.20"}),
    )

    version_check.check_for_client_version_update()
    out = capsys.readouterr().out
    assert 'Instance "eu1" uses a later version of the Poly client. Current: 1.0.0, Instance: 1.2.0.' in out
    assert "Please update to avoid any issues." in out


def test_check_version_interactive_decline(monkeypatch, capsys):
    monkeypatch.delenv("POLY_VERSION_REEXEC_GUARD", raising=False)
    monkeypatch.delenv("POLY_API_KEY", raising=False)
    monkeypatch.delenv("POLY_API_BASE_URL", raising=False)

    monkeypatch.setattr(version_check, "get_api_key_and_url", lambda: ("k", "https://eu1.polyapi.io"))
    monkeypatch.setattr(version_check, "_get_client_version", lambda: "1.0.0")
    monkeypatch.setattr(
        version_check,
        "http_get",
        lambda *args, **kwargs: _FakeResponse({"python": "1.2.0", "typescript": "1.20.0"}),
    )
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "n")

    version_check.check_for_client_version_update()
    out = capsys.readouterr().out
    assert "Continuing with older Poly client version 1.0.0. Please update to avoid any issues." in out


def test_check_version_interactive_accept_updates_and_reexec(monkeypatch):
    monkeypatch.delenv("POLY_VERSION_REEXEC_GUARD", raising=False)
    monkeypatch.delenv("POLY_API_KEY", raising=False)
    monkeypatch.delenv("POLY_API_BASE_URL", raising=False)

    monkeypatch.setattr(version_check, "get_api_key_and_url", lambda: ("k", "https://eu1.polyapi.io"))
    monkeypatch.setattr(version_check, "_get_client_version", lambda: "1.0.0")
    monkeypatch.setattr(
        version_check,
        "http_get",
        lambda *args, **kwargs: _FakeResponse({"python": "1.2.0", "typescript": "1.20.0"}),
    )
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "y")

    state = {"updated": False, "reexec": False}

    def _fake_run_update(_v):
        state["updated"] = True
        return True

    def _fake_reexec(*args, **kwargs):
        state["reexec"] = True

    monkeypatch.setattr(version_check, "_run_update", _fake_run_update)
    monkeypatch.setattr(version_check, "_reexec_process", _fake_reexec)

    version_check.check_for_client_version_update()

    assert state["updated"] is True
    assert state["reexec"] is True


def test_check_skips_when_python_version_missing(monkeypatch, capsys):
    monkeypatch.delenv("POLY_VERSION_REEXEC_GUARD", raising=False)
    monkeypatch.setenv("POLY_API_KEY", "k")
    monkeypatch.setenv("POLY_API_BASE_URL", "https://na2.polyapi.io")

    monkeypatch.setattr(version_check, "get_api_key_and_url", lambda: ("k", "https://na2.polyapi.io"))
    monkeypatch.setattr(version_check, "_get_client_version", lambda: "1.0.0")
    monkeypatch.setattr(
        version_check,
        "http_get",
        lambda *args, **kwargs: _FakeResponse({"typescript": "1.20"}),
    )

    version_check.check_for_client_version_update()
    out = capsys.readouterr().out
    assert out == ""


def test_reexec_guard_prevents_flow(monkeypatch):
    monkeypatch.setenv("POLY_VERSION_REEXEC_GUARD", "1")
    called = {"get_api": False}

    def _fake_get_api_key_and_url():
        called["get_api"] = True
        return ("k", "https://eu1.polyapi.io")

    monkeypatch.setattr(version_check, "get_api_key_and_url", _fake_get_api_key_and_url)
    version_check.check_for_client_version_update()
    assert called["get_api"] is False

    monkeypatch.delenv("POLY_VERSION_REEXEC_GUARD", raising=False)
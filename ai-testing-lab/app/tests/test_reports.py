"""Tests de reportes y path jail."""

from __future__ import annotations

from pathlib import Path


def _make_report(lab_root: Path, date: str = "2026-07-12", time: str = "130000") -> str:
    run = lab_root / "reports" / date / time
    run.mkdir(parents=True, exist_ok=True)
    (run / "summary.md").write_text("# ok\napi_key=secret-should-redact\n", encoding="utf-8")
    (run / "promptfoo").mkdir()
    (run / "promptfoo" / "output.log").write_text("passed (1)\n", encoding="utf-8")
    return f"{date}_{time}"


def test_list_and_latest(client, tmp_path, monkeypatch):
    # client fixture ya setea LAB_ROOT=tmp_path
    rid = _make_report(tmp_path)
    listed = client.get("/reports")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1

    latest = client.get("/reports/latest")
    assert latest.status_code == 200
    assert latest.json()["report"]["report_id"] == rid
    assert "Lexicográf" in latest.json()["criterion"] or "lexicográf" in latest.json()["criterion"].lower() or "Lexicographic" in latest.json()["criterion"] or "lexicográfico" in latest.json()["criterion"].lower()


def test_get_report(client, tmp_path):
    rid = _make_report(tmp_path)
    resp = client.get(f"/reports/{rid}")
    assert resp.status_code == 200
    assert resp.json()["has_summary"] is True


def test_report_not_found(client):
    resp = client.get("/reports/2099-01-01_000000")
    assert resp.status_code == 404


def test_path_traversal_report_id(client):
    resp = client.get("/reports/../etc_passwd")
    assert resp.status_code in (400, 404, 422)


def test_absolute_path_rejected(client):
    resp = client.get("/reports/C:_Windows_system32")
    assert resp.status_code in (400, 404, 422)


def test_file_read_and_redaction(client, tmp_path):
    rid = _make_report(tmp_path)
    resp = client.get(f"/reports/{rid}/files/summary.md")
    assert resp.status_code == 200
    body = resp.json()
    assert "REDACTED" in body["content"] or "secret" not in body["content"].lower() or "api_key=***REDACTED***" in body["content"]


def test_file_traversal(client, tmp_path):
    rid = _make_report(tmp_path)
    resp = client.get(f"/reports/{rid}/files/../../etc/passwd")
    # 400 (jail) o 404 (Starlette normaliza/rompe la ruta) — ambos son denegación segura.
    assert resp.status_code in (400, 404)


def test_disallowed_extension(client, tmp_path):
    rid = _make_report(tmp_path)
    run = tmp_path / "reports" / "2026-07-12" / "130000"
    (run / "evil.exe").write_bytes(b"MZ")
    resp = client.get(f"/reports/{rid}/files/evil.exe")
    assert resp.status_code == 400

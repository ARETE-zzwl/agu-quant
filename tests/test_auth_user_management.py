import hashlib

import pytest

from tradingagents.auth import license as license_mod
from tradingagents.auth import machine_id
from tradingagents.auth import access
from tradingagents.auth import user_db


@pytest.fixture()
def isolated_user_db(tmp_path, monkeypatch):
    monkeypatch.setattr(user_db, "DB_PATH", tmp_path / "users.db")
    yield


def test_add_license_normalizes_user_and_blocks_duplicate_names(isolated_user_db):
    key_hash_1 = hashlib.sha256(b"license-1").hexdigest()
    key_hash_2 = hashlib.sha256(b"license-2").hexdigest()

    assert user_db.add_license("  Alice@Example.COM  ", key_hash_1, "202712", 2)
    assert not user_db.add_license("alice@example.com", key_hash_2, "202712", 2)

    users = user_db.list_users()
    assert len(users) == 1
    assert users[0]["user_name"] == "alice@example.com"
    assert users[0]["device_count"] == 0
    assert users[0]["max_devices"] == 2
    assert users[0]["plan"] == "pro"


def test_supporter_license_does_not_grant_pro_access(tmp_path, monkeypatch):
    from tradingagents.auth.plans import plan_allows

    monkeypatch.setattr(license_mod, "STATE_FILE", tmp_path / "activation.json")
    monkeypatch.setattr(machine_id, "get_machine_fingerprint", lambda: "machine-a")

    key = license_mod.generate_license_key("alice", "202712", plan="supporter")
    result = license_mod.activate_license(key, "alice")

    assert result["success"]
    assert result["plan"] == "supporter"
    assert plan_allows(result["plan"], "supporter")
    assert not plan_allows(result["plan"], "pro")


def test_legacy_license_without_plan_keeps_pro_access(tmp_path, monkeypatch):
    import hmac

    monkeypatch.setattr(license_mod, "STATE_FILE", tmp_path / "activation.json")
    monkeypatch.setattr(machine_id, "get_machine_fingerprint", lambda: "machine-a")
    rand = "abcd"
    payload = f"alice:202712:{rand}".encode()
    signature = hmac.new(license_mod._SECRET, payload, hashlib.sha256).hexdigest()[:4]
    legacy_key = f"Agu-202712-{rand}-{signature}"

    result = license_mod.activate_license(legacy_key, "alice")

    assert result["success"]
    assert result["plan"] == "pro"


def test_web_access_enforces_required_plan(monkeypatch):
    from tradingagents import auth
    from web import auth_session
    from web.components import common

    monkeypatch.setattr(auth_session, "is_admin", lambda: False)
    monkeypatch.setattr(
        auth,
        "get_license_status",
        lambda: {"valid": True, "plan": "supporter"},
    )

    assert common.has_premium_access("supporter")
    assert not common.has_premium_access("pro")


def test_add_license_validates_expire_month(isolated_user_db):
    with pytest.raises(ValueError, match="到期年月"):
        user_db.add_license("alice", hashlib.sha256(b"license").hexdigest(), "2027-12", 1)


def test_bind_machine_allows_first_device_then_enforces_limit(isolated_user_db):
    key_hash = hashlib.sha256(b"license").hexdigest()
    assert user_db.add_license("alice", key_hash, "202712", 1)

    assert user_db.bind_machine(key_hash, "machine-a")
    assert user_db.check_license_db(key_hash, "machine-a")["valid"]
    assert not user_db.bind_machine(key_hash, "machine-b")

    users = user_db.list_users()
    assert users[0]["device_count"] == 1


def test_get_license_key_hash_for_user_uses_normalized_name(isolated_user_db):
    key_hash = hashlib.sha256(b"license").hexdigest()
    assert user_db.add_license("Alice", key_hash, "999912", 1)

    assert user_db.get_license_key_hash_for_user(" alice ") == key_hash


def test_activate_license_rejects_key_for_wrong_user(tmp_path, monkeypatch):
    monkeypatch.setattr(license_mod, "STATE_FILE", tmp_path / "activation.json")
    monkeypatch.setattr(machine_id, "get_machine_fingerprint", lambda: "machine-a")

    key = license_mod.generate_license_key("alice", "202712")

    result = license_mod.activate_license(key, "bob")

    assert not result["success"]
    assert "用户名" in result["message"]
    assert not license_mod.STATE_FILE.exists()


def test_activate_license_saves_trial_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(license_mod, "STATE_FILE", tmp_path / "activation.json")
    monkeypatch.setattr(machine_id, "get_machine_fingerprint", lambda: "machine-a")

    key = license_mod.generate_license_key("alice", "202712")

    result = license_mod.activate_license(key, "alice", trial_days=7)

    assert result["success"]
    state = license_mod._load_state()
    assert state["user"] == "alice"
    assert "trial_expires_at" in state


def test_authenticate_admin_rejects_when_credentials_are_not_configured(monkeypatch):
    monkeypatch.delenv("TA_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("TA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    result = access.authenticate_admin(" zzwl ", "123456")

    assert not result["success"]


def test_authenticate_admin_allows_only_configured_env_credentials(monkeypatch):
    monkeypatch.setenv("TA_ADMIN_USERNAME", "owner")
    monkeypatch.setenv("TA_ADMIN_PASSWORD", "safe-password")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    assert access.authenticate_admin("owner", "safe-password")["success"]
    assert not access.authenticate_admin("zzwl", "123456")["success"]


def test_legacy_admin_password_uses_admin_as_username(monkeypatch):
    monkeypatch.delenv("TA_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("TA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "legacy-safe-password")

    result = access.authenticate_admin("admin", "legacy-safe-password")

    assert result["success"]
    assert result["role"] == "admin"


def test_development_auth_bypass_requires_explicit_true_value(monkeypatch):
    monkeypatch.delenv("TA_DEV_MODE", raising=False)
    assert not access.development_auth_enabled()

    monkeypatch.setenv("TA_DEV_MODE", "true")
    assert access.development_auth_enabled()

    monkeypatch.setenv("TA_DEV_MODE", "false")
    assert not access.development_auth_enabled()


def test_authenticate_license_user_activates_and_binds_device(tmp_path, monkeypatch, isolated_user_db):
    monkeypatch.setattr(license_mod, "STATE_FILE", tmp_path / "activation.json")
    monkeypatch.setattr(machine_id, "get_machine_fingerprint", lambda: "machine-a")

    key = license_mod.generate_license_key("alice", "202712")
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    assert user_db.add_license("alice", key_hash, "202712", 1)

    result = access.authenticate_license_user("Alice", key)

    assert result["success"]
    assert result["role"] == "user"
    assert result["user_name"] == "alice"
    assert user_db.check_license_db(key_hash, "machine-a")["valid"]

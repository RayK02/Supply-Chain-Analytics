from app.services import save_order
from app.auth import AuthError


def add_order(app):
    db=app.extensions["db"]; loc=db.one("SELECT id FROM locations WHERE code='CH'")
    return save_order(db,{"tracking_id":"WEB-1","warehouse_order_no":"PO-WEB","at_sales_order_no":"SO-WEB","external_document_no":"EXT-WEB","location_id":loc["id"],"order_at":"2026-07-01T08:00:00+00:00","created_at_at":"2026-07-01T08:00:00+00:00","ready_at":"2026-07-04T08:00:00+00:00","picked_up_at":"2026-07-05T08:00:00+00:00","received_at":"2026-07-08T08:00:00+00:00","priority":"normal","data_source":"Test"})


def test_all_main_pages(app,client):
    oid=add_order(app)
    for url in ["/","/orders","/orders/open","/comparison","/quality","/import","/reports","/master","/settings","/system",f"/orders/{oid}",f"/orders/{oid}/edit"]:
        response=client.get(url); assert response.status_code == 200, url


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "database": "sqlite"}


def test_exports(app,client):
    add_order(app)
    csv_resp=client.get("/export/orders.csv"); assert csv_resp.status_code==200 and b"Tracking-ID" in csv_resp.data
    xlsx_resp=client.get("/export/orders.xlsx"); assert xlsx_resp.status_code==200 and xlsx_resp.data[:2]==b"PK"


def test_manual_validation_and_create(app,client):
    loc=app.extensions["db"].one("SELECT id FROM locations WHERE code='CH'")["id"]
    response=client.post("/orders/new",data={"tracking_id":"FORM-1","at_sales_order_no":"SO-FORM","location_id":loc,"order_at":"2026-07-01T08:00","priority":"normal","data_source":"Manuell"})
    assert response.status_code==302


def test_language_setting_switches_global_ui(app, client):
    response = client.post("/settings", data={
        "warning_no_pick_days": "2", "warning_pick_idle_days": "2",
        "warning_ready_pickup_days": "2", "display_unit": "workdays",
        "language": "en", "system_type": "Datei",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'<html lang="en">' in response.data
    assert b"Settings" in response.data
    assert b"Language" in response.data
    assert b"English" in response.data
    assert b'value="Datei"' in response.data
    assert b">File<" in response.data
    assert app.extensions["db"].scalar("SELECT value FROM settings WHERE key='language'") == "en"

    dashboard = client.get("/")
    assert b"Open orders" in dashboard.data
    assert b"Import data" in dashboard.data


class FakeAuth:
    configured = True

    def sign_in(self, email, password):
        if password != "correct-password":
            raise AuthError("E-Mail-Adresse oder Passwort ist falsch.")
        return {
            "access_token": "access-token", "refresh_token": "refresh-token", "expires_in": 3600,
            "user": {"id": "user-1", "email": email},
        }

    def refresh(self, refresh_token):
        assert refresh_token == "refresh-token"
        return self.sign_in("user@example.com", "correct-password")


def test_supabase_login_protects_pages_and_logout(app):
    app.config["AUTH_REQUIRED"] = True
    app.extensions["auth"] = FakeAuth()
    client = app.test_client()

    protected = client.get("/")
    assert protected.status_code == 302
    assert "/login?next=/" in protected.headers["Location"]
    assert client.get("/health").status_code == 200

    failed = client.post("/login", data={"email": "user@example.com", "password": "wrong"})
    assert failed.status_code == 401
    assert "E-Mail-Adresse oder Passwort ist falsch".encode() in failed.data

    logged_in = client.post("/login", data={
        "email": "User@Example.com", "password": "correct-password", "next": "/settings",
    })
    assert logged_in.status_code == 302
    assert logged_in.headers["Location"].endswith("/settings")
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert b"user@example.com" in dashboard.data
    logged_out = client.post("/logout")
    assert logged_out.status_code == 302
    assert logged_out.headers["Location"].endswith("/login")


def test_login_rejects_external_next_url(app):
    app.config["AUTH_REQUIRED"] = True
    app.extensions["auth"] = FakeAuth()
    client = app.test_client()
    response = client.post("/login", data={
        "email": "user@example.com", "password": "correct-password", "next": "https://evil.example/",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

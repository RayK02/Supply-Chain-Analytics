from app.services import save_order


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

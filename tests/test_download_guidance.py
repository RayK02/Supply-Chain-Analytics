from webapp import app


def test_results_download_guidance_requires_reselecting_files():
    client = app.test_client()

    script_response = client.get('/static/app.js')
    script = script_response.get_data(as_text=True)

    assert script_response.status_code == 200
    assert 'Für XLSX: Dateien oben erneut auswählen' in script
    assert 'Browser stellen Dateiauswahlen nach dem Seitenwechsel nicht wieder her' in script
    assert 'Direkt als XLSX – ohne Webansicht' in script

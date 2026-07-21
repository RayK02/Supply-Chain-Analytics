from __future__ import annotations


TRANSLATIONS = {
    "Aussenlager Tracker": "External Warehouse Tracker",
    "Aussenlager": "External warehouse",
    "Durchlaufzeit": "Lead time",
    "Bestellungen": "Orders",
    "Offene Bestellungen": "Open orders",
    "Standortvergleich": "Location comparison",
    "Datenqualität": "Data quality",
    "Stammdaten": "Master data",
    "Einstellungen": "Settings",
    "Systeminformationen": "System information",
    "Bestellung": "Order",
    "Bestellung erfassen": "Create order",
    "Bestellung bearbeiten": "Edit order",
    "Daten importieren": "Import data",
    "Lokaler Einzelplatzbetrieb · Daten bleiben auf diesem Computer": "Single-user operation · Data remains in the configured database",
    "Tracking-ID oder Auftrag …": "Tracking ID or order …",
    "Alle Standorte": "All locations",
    "Alle Status": "All statuses",
    "Arbeitstage": "Working days",
    "Kalendertage": "Calendar days",
    "Stunden": "Hours",
    "Filtern": "Filter",
    "Zurücksetzen": "Reset",
    "WARNUNGEN": "WARNINGS",
    "Schwellenwerte": "Thresholds",
    "Ohne Pick nach Arbeitstagen": "No pick after working days",
    "Pick inaktiv nach Arbeitstagen": "Pick inactive after working days",
    "Abholbereit ohne Abholung": "Ready for pickup without collection",
    "Standard-Einheit": "Default unit",
    "Sprache": "Language",
    "Deutsch": "German",
    "Englisch": "English",
    "Feiertagskalender können später standortspezifisch ergänzt werden; Version 1 verwendet Montag bis Freitag.": "Location-specific holiday calendars can be added later; version 1 uses Monday through Friday.",
    "Systemtyp": "System type",
    "Datei": "File",
    "Client Secret und Passwörter werden hier nicht gespeichert. Die produktive Anbindung soll Windows Credential Manager/Keyring verwenden.": "Client secrets and passwords are not stored here. The production connection should use Windows Credential Manager or a keyring.",
    "Einstellungen speichern": "Save settings",
    "Konfiguration prüfen": "Validate configuration",
    "Einstellungen gespeichert. Zugangsdaten werden bewusst nicht gespeichert.": "Settings saved. Credentials are deliberately not stored.",
}


def translate(text: str, language: str) -> str:
    return TRANSLATIONS.get(text, text) if language == "en" else text

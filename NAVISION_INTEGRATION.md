# Navision-/Business-Central-Integration

## Wahrscheinliche Quellen

Je nach Version und kundenspezifischer Lösung: Sales Header, Sales Shipment Header, Purchase Header, Purch. Rcpt. Header, Warehouse Activity Header/Line, Registered Whse. Activity Header, Warehouse Shipment Header, Posted Warehouse Shipment und Change Log Entry. Relevant sind u. a. Dokument-/externe Nummern, Location Code, Status, Posting/Shipment/Receipt Date, Assignment Date/Time sowie `SystemCreatedAt`/`SystemModifiedAt` in neueren BC-Versionen.

Diese Namen sind Kandidaten, keine fest verdrahtete Voraussetzung. Die tatsächlich verfügbare Zeitauflösung muss pro Installation geprüft werden; reine Datumsfelder reichen für Stunden-KPIs nur eingeschränkt.

## Verknüpfung

Die stabile fachliche Kette sollte externe Aussenlager-PO → AT Sales Order → Warehouse Activity/Pick → Warehouse Shipment/posted Shipment → Receipt verwenden. Dokumentnummer plus Mandant/Firma allein kann bei Nummernserienkollisionen unzureichend sein; System-ID oder explizite Referenzfelder sind vorzuziehen. Change Log oder kundenspezifische Statushistorie kann Zeitpunkte liefern, die im aktuellen Beleg nicht erhalten bleiben.

## Business Central API

Für BC Online/aktuelle On-Prem-Versionen sollten freigegebene Standard- oder Custom API Pages mit OAuth 2.0 genutzt werden. Konfigurationswerte: Base URL, Tenant, Environment, Company, API-Version, Client ID und Scope. Das Client Secret gehört in Windows Credential Manager/OS-Keyring, nicht in Quellcode oder SQLite. Delta-/Änderungsabfragen sollten `SystemModifiedAt` oder OData-Delta unterstützen und idempotent importieren.

## Älteres NAV / OData

NAV benötigt veröffentlichte Pages/Queries oder OData-Webservices. Authentifizierung kann Windows, NavUserPassword oder installationsspezifisch sein. Feldnamen, UTC-Verhalten, Page-Filter und Paging unterscheiden sich deutlich. Direkter SQL-Zugriff wird wegen Geschäftslogik, Sicherheit und Upgrade-Risiko nicht als Standard empfohlen.

## Benötigte Informationen des Navision-Teams

- exakte NAV-/BC-Version, Deployment (Online/On-Prem) und Firmen-/Mandanten-IDs
- veröffentlichte APIs/OData-Services und Authentifizierungsverfahren
- Nummernkreise und belastbare Join-Schlüssel
- Definition des fachlichen Bestellbeginns und Abschlusses
- Herkunft jedes Pick-, Pack-, Dokument-, Pickup- und Receipt-Zeitpunkts
- Zeitzonen, Datumsgenauigkeit und Feiertagskalender
- Custom Fields/Extensions sowie Change-Log-Konfiguration
- Datenvolumen, Aktualisierungsfrequenz und Berechtigungskonzept

## Mapping-Schicht

Connectoren liefern normalisierte Dictionaries an den bestehenden Importservice. Entity- und Feldmappings werden je Quelle konfiguriert. Dadurch bleiben Datenmodell, KPI-Logik, Duplikaterkennung und Auditierung unabhängig von der NAV-/BC-Ausprägung.


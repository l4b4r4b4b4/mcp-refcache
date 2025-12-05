# BundesMCP - Generischer MCP-Server für deutsche Behörden-APIs + OpenStreetMap

🇩🇪 **Ein einzelner MCP-Server, der Zugriff auf über 60 deutsche Behörden-APIs + OpenStreetMap-Dienste bietet**

[🇬🇧 English version below](#english-version)

## Was ist das?

BundesMCP ist ein **generischer Model Context Protocol (MCP) Server**, der automatisch deutsche Behörden-APIs aus der [bundesAPI](https://github.com/bundesAPI) einbindet **plus vollständige OpenStreetMap-Integration** für Geocoding, Routing und POI-Suche. Anstatt individuelle MCP-Server für jede API zu entwickeln, werden OpenAPI 3.0-Spezifikationen geparst und dynamisch als MCP-Tools zur Verfügung gestellt.

## Features

- ✅ **Sofort einsatzbereit** - Funktioniert mit allen gängigen Agenten und MCP-Clients
- ✅ **Generische OpenAPI → MCP Konvertierung** - Funktioniert mit jedem bundesAPI-Dienst
- ✅ **60+ APIs verfügbar** - Wetter, Energie, Ladestationen, Feiertage, Hochwasser, Luftqualität und mehr
- ✅ **OpenStreetMap Integration** - 12 Tools für Geocoding, Routing, POI-Suche, Nachbarschaftsanalyse
- ✅ **Hierarchische Endpoint- und Tool-Discovery** - Verhindert Context-Explosion durch progressive Offenlegung der Endpunkt-Spezifikationen und Tool Responses
- ✅ **Smart Caching** - Referenz-basierte Caching-System mit Preview/Full-Modi für alle Responses
- ✅ **Keyword-Suche** - Durchsuchen Sie alle Tools nach Namen, Beschreibungen und Tags
- ✅ **Eine einzige Codebasis** - Keine Notwendigkeit, 60+ separate Server zu warten
- ✅ **deutschland-Paket Integration** - Native Unterstützung für offizielle deutsche GIS-Daten


## Aktueller Status

**Vollständig funktionsfähig und produktionsbereit:**
- ✅ **49 APIs geladen** - Alle bundesAPI-Dienste + OpenStreetMap
- ✅ **365 Endpunkte verfügbar** - Komplette API-Abdeckung inkl. OSM
- ✅ **19 MCP Tools** - Hierarchische Erkennung + API-Aufrufe + OSM-Services + Cache-Verwaltung
- ✅ **Smart Caching** - Referenz-basiertes System verhindert Context-Explosion (Responses <5KB)
- ✅ **Live getestet** - In Produktion mit mehreren MCP-Servern validiert

## Verfügbare MCP Tools

### Discovery Tools (Hierarchische Erkennung)
1. **`list_apis()`** - Alle verfügbaren deutschen Behörden-APIs auflisten (~2.3KB)
2. **`list_toolsets(api_id)`** - Tools in einer spezifischen API mit Zusammenfassungen auflisten (~63 bytes - 2KB)
3. **`get_toolset_info(tool_name)`** - Vollständige Details für ein spezifisches Tool abrufen (~1.5KB)
4. **`search_toolsets(query, api_id?)`** - Tools nach Stichwort durchsuchen (~1-5KB)

### Execution Tools
5. **`api_call(tool_name, parameters, options)`** - Jeden API-Endpunkt mit Smart Caching aufrufen
6. **`cache_stats(api_id?)`** - Cache-Statistiken anzeigen (Hits, Misses, Größe)
7. **`clear_cache(api_id?)`** - Cache für spezifische oder alle APIs löschen

### OpenStreetMap Tools (Geocoding, Routing, POI-Suche)
8. **`osm_geocode_address(address)`** - Adresse zu Koordinaten konvertieren
9. **`osm_reverse_geocode(latitude, longitude)`** - Koordinaten zu Adresse konvertieren
10. **`osm_get_route_directions(from_lat, from_lon, to_lat, to_lon, mode)`** - Route berechnen (Auto/Rad/Fuß)
11. **`osm_find_nearby_places(latitude, longitude, radius, categories)`** - POIs in der Nähe finden
12. **`osm_search_category(category, bbox, subcategories)`** - Spezifische Ortstypen in Region suchen
13. **`osm_suggest_meeting_point(locations, venue_type)`** - Optimalen Treffpunkt finden
14. **`osm_explore_area(latitude, longitude, radius)`** - Umfassendes Gebietsprofil erstellen
15. **`osm_find_schools_nearby(latitude, longitude, radius)`** - Bildungseinrichtungen finden
16. **`osm_analyze_commute(home_lat, home_lon, work_lat, work_lon, modes)`** - Pendel-Analyse durchführen
17. **`osm_find_ev_charging_stations(latitude, longitude, radius)`** - Ladestationen für E-Autos finden
18. **`osm_analyze_neighborhood(latitude, longitude, radius)`** - Wohnqualität und Lebensumfeld bewerten
19. **`osm_find_parking_facilities(latitude, longitude, radius)`** - Parkplätze und Parkhäuser finden

## Schnellstart

### Voraussetzungen

- Python 3.12+
- `uv` Paketmanager

### Installation

```bash
# Repository klonen
git clone <repo-url>
cd BundesMCP

# Abhängigkeiten installieren
uv sync

# Server starten
uv run python src/main.py
```

## Test-Prompts

### 🔧 Technischer Schnelltest (2-3 Minuten)

Für einen detaillierten Test mit technischen Metriken:

```
Teste den BundesMCP-Server kurz. WICHTIG: Erkläre vor jedem Tool-Aufruf, was du tust, und interpretiere danach die Ergebnisse.

1. Nutze list_apis() - wie viele APIs sind verfügbar? Wie groß ist die Antwort?
2. Nutze list_toolsets mit api_id="tagesschau" - welche News-Tools gibt es? Antwortgröße?
3. Nutze api_call mit tool_name="tagesschau_news" (keine Parameter nötig) um aktuelle Nachrichten abzurufen. Was kommt zurück - Preview oder Full?
4. Rufe denselben Endpunkt nochmal auf - kommt der gleiche Cache-ref_id zurück? Was bedeutet das?
5. Nutze list_toolsets mit api_id="autobahn" - welche Autobahn-Tools gibt es?
6. Nutze api_call mit tool_name="autobahn_list_autobahnen" (keine Parameter) um alle deutschen Autobahnen abzurufen. Wie viele gibt es?
7. Nutze api_call mit tool_name="autobahn_list_charging_stations" und parameters='{"roadId":"A9"}' um Ladestationen an der A9 abzurufen. Nutze options={"value_type": "full"} um vollständige Daten zu erhalten.
8. Nutze api_call mit tool_name="tagesschau_news" und options={"value_type": "full", "pagination": {"page": 1, "page_size": 2}} um nur die ersten 2 News-Einträge zu bekommen (News-Objekte sind sehr groß!). Erkläre die Pagination-Struktur.

Fasse zusammen: Antwortgrößen, Caching-Verhalten, Preview vs. Full Modus, Pagination, und ob alles wie erwartet funktioniert.

HINWEIS: Der MCP-Server hat drei Response-Typen:
- "preview" (Standard bei großen Daten): Zeigt nur Vorschau mit ersten Einträgen
- "full": Zeigt vollständige Daten (nutze options={"value_type": "full"} bei api_call)
- "reference": Nur Cache-Referenz für sehr große Daten
- "pagination": Kann mit full/preview kombiniert werden (z.B. options={"value_type": "full", "pagination": {"page": 1, "page_size": 10}})
```

### 💬 Konversationeller Schnelltest: Risikobewertung (2-3 Minuten)

Für einen natürlichen Test ohne technische Details:

```
Ich bewerte gerade ein Immobiliengrundstück in Frankfurt am Main und möchte öffentliche Daten nutzen. Kannst du mir helfen?

Zeig mir bitte:
1. Welche deutschen Behörden-Infos sind verfügbar?
2. Gibt es Infos für Hochwasser-Warnungen oder Pegelstände? (Wichtig für Überschwemmungsrisiko!)
3. Welche aktuellen Warnmeldungen gibt es für Frankfurt (ARS: 064120000000)?
4. Wenn du dieselbe Abfrage nochmal machst - merkst du, dass die Daten gecacht sind?

Erkläre mir jeweils kurz, was du gerade machst und was die Ergebnisse bedeuten.

HINWEIS: Wenn Antworten zu groß sind und nur als Preview angezeigt werden, nutze options={"value_type": "full"} bei api_call um die vollständigen Daten zu sehen!
```

### 💬 Konversationeller Schnelltest: Demographie & Standort (2-3 Minuten)

Für einen natürlichen Test der sozioökonomischen Daten:

```
Ich analysiere ein Wohnbauprojekt in München und brauche Daten zur Bevölkerungsstruktur. Kannst du mir helfen?

Zeig mir bitte:
1. Welche Infos gibt es für demografische und sozioökonomische Daten?
2. Wie ist die Bevölkerungsdichte und Alterstruktur in München (Kreis-Ebene, AGS: 09162)?
3. Welche Arbeitslosenquote hat die Region? (Wichtig für Mietausfallrisiko!)
4. Vergleiche München mit Hamburg (AGS: 02000) - welche Stadt hat bessere demografische Kennzahlen?

Erkläre mir jeweils, was die Daten bedeuten und wie sie für Immobilienbewertung relevant sind.

HINWEIS: Bei großen Antworten vom Regionalatlas nutze options={"value_type": "full"} um vollständige Daten zu sehen!
```

### 💬 Konversationeller Umfassender Test (5-10 Minuten)

Für einen vollständigen Test in natürlicher Sprache:

```
Ich arbeite an einer Immobilienbewertung in Deutschland und möchte verschiedene Standortfaktoren prüfen. Kannst du mir helfen?

Führe bitte folgende Tests durch und erkläre mir jeweils, was passiert:

1. Zeig mir eine Übersicht aller verfügbaren deutschen Behörden-APIs.
2. Vergleiche die NINA-API (Katastrophenwarnungen) mit der Regionalatlas-API (sozioökonomische Daten) - wie unterscheiden sich die verfügbaren Funktionen?
3. Welche Parameter kann ich bei der NINA Dashboard-Abfrage verwenden?
4. Such mal nach allen Tools, die mit "Hochwasser" oder "Pegel" zu tun haben. Was findest du?
5. Such auch nach "Luftqualität" - gibt es da relevante Endpunkte für Immobilienstandorte?
6. Frag zweimal die Warnmeldungen für München (ARS: 091620000000) ab - merkst du beim zweiten Mal, dass die Daten aus dem Cache kommen?
7. Zeig mir die Cache-Statistiken für die NINA-API.
8. Rufe demografische Daten für Berlin ab - einmal mit Preview, einmal mit Full Mode. Was ist der Unterschied?

Fasse am Ende zusammen:
- Wie effizient ist das System (Antwortgrößen)?
- Funktioniert das Caching richtig?
- Welche APIs sind besonders relevant für Immobilienbewertung?
- Gibt es Probleme oder Auffälligkeiten?

HINWEIS: Nutze options={"value_type": "full"} bei api_call wenn du vollständige Daten sehen willst statt nur Preview!
```

### 🔧 Technischer Umfassender Test (5-10 Minuten)

Für einen vollständigen Test mit technischen Details:

```
Führe einen umfassenden Test des BundesMCP-Servers durch. WICHTIG: Erkläre vor jedem Schritt, was du tust, und interpretiere nach jedem Test das Ergebnis.

TEST 1 - API-Erkennung:
- Nutze list_apis() und berichte die Anzahl verfügbarer APIs und Antwortgröße
- Erkläre: Was zeigt diese Antwort?

TEST 2 - Tool-Erkennung:
- Nutze list_toolsets mit api_id="luftqualitaet" (mittlere API mit ~14 Tools)
- Nutze list_toolsets mit api_id="nina" (große API mit ~24 Warn-Tools)
- Berichte die Antwortgrößen für beide
- Erkläre: Warum sind die Antworten so klein?

TEST 3 - Tool-Details:
- Nutze get_toolset_info für tool_name="regionalatlas_query"
- Berichte welche Parameter verfügbar sind
- Erkläre: Wofür ist dieser Endpunkt? (Hinweis: sozioökonomische Daten für Immobilienbewertung!)

TEST 4 - Keyword-Suche:
- Nutze search_toolsets mit query="hochwasser flood pegel" um Hochwasser-Tools zu finden
- Nutze search_toolsets mit query="luftqualität air quality" für Umwelt-Endpunkte
- Berichte Anzahl und Relevanz der Ergebnisse
- Erkläre: Wie funktioniert die Relevanz-Sortierung?

TEST 5 - API-Aufrufe mit Caching:
- Nutze api_call: tool_name="nina_getDashboard", parameters='{"ARS":"055150000000"}' (Mainz)
- Erkläre das Ergebnis (welche Warnungen?)
- Rufe denselben Endpunkt mit identischen Parametern nochmal auf
- Nutze cache_stats mit api_id="nina" um Cache-Performance zu prüfen
- Berichte: Sind die ref_ids identisch? Cache Hit/Miss? Was bedeutet das?

TEST 6 - Preview vs Full Mode:
- Nutze api_call MIT options={"value_type":"preview"} für tool_name="regionalatlas_query" mit München-Daten
- Nutze api_call MIT options={"value_type":"full"} für dieselbe Abfrage
- Vergleiche die Antwortgrößen
- Erkläre: Warum gibt es Preview und Full Mode? (Kontext-Effizienz!)

Fasse zusammen:
- Alle Antwortgrößen und deren Bedeutung
- Cache-Verhalten (Hits, ref_ids) und was das bringt
- Kontext-Reduzierung vs. alte list_endpoints-Methode (95% kleiner!)
- Relevanz für Immobilien-Domain (Risikobewertung, Standortfaktoren)
- Probleme oder unerwartetes Verhalten

RESPONSE-TYPEN: Der Server unterstützt drei Antwortmodi:
1. "preview" (Standard bei >500 chars): Zeigt truncated Vorschau
2. "full": Vollständige Daten (options={"value_type": "full"})
3. "reference": Nur Cache-Referenz für sehr große Responses
```

### 💬 Konversationeller Umfassender Test: Vollständige Standortanalyse (10-15 Minuten)

Für eine komplette Standortbewertung mit allen verfügbaren Datenquellen:

```
Ich plane ein großes Immobilieninvestment in Hamburg und möchte eine umfassende Standortanalyse mit allen verfügbaren Behördendaten durchführen. Kannst du mir dabei helfen?

Führe bitte eine vollständige Due Diligence durch:

1. DEMOGRAPHIE & SOZIOÖKONOMIE:
   - Bevölkerungsdichte, Altersdurchschnitt und Wanderungssaldo für Hamburg (AGS: 02000)
   - Arbeitslosenquote und Langzeitarbeitslosigkeit
   - Erkläre: Wie bewerte ich damit die Nachfrage und das Ausfallrisiko?

2. RISIKOFAKTOREN:
   - Gibt es aktuelle Katastrophenwarnungen oder Hochwassermeldungen für Hamburg?
   - Such nach verfügbaren Pegelständen für Hamburg (Elbe)
   - Erkläre: Welche Risiken sollte ich in der Bewertung berücksichtigen?

3. LUFTQUALITÄT & UMWELT:
   - Welche Luftqualitäts-Endpunkte gibt es?
   - Sind Messstationen in Hamburg verfügbar?
   - Erkläre: Warum ist das für Wohnimmobilien relevant?

4. STÄDTEVERGLEICH:
   - Vergleiche Hamburg mit München und Berlin demografisch
   - Welche Stadt hat die niedrigste Arbeitslosigkeit?
   - Welche Stadt wächst am stärksten?
   - Erkläre: Was bedeutet das für Investitionsentscheidungen?

5. E-MOBILITÄT & LADEINFRASTRUKTUR:
   - Wie viele Ladestationen gibt es in Hamburg?
   - Vergleiche die Ladestationen-Dichte mit München und Berlin
   - Welche Leistungsklassen sind verfügbar (Schnelllader vs. Normallader)?
   - Erkläre: Warum ist Ladeinfrastruktur für Wohnimmobilien zunehmend wichtig?

6. TECHNISCHE EFFIZIENZ:
   - Welche APIs sind am wertvollsten für Immobilienanalyse?

Fasse am Ende alle Erkenntnisse zusammen: Ist Hamburg ein guter Standort für Wohnimmobilien? Was sind die wichtigsten Chancen und Risiken?

HINWEIS: Nutze options={"value_type": "full"} bei api_call für vollständige Daten!
```

**💡 Mehr Test-Prompts:** Weitere kreative Test-Szenarien findest du in [docs/TEST_PROMPTS.md](docs/TEST_PROMPTS.md) - von Wetter-Forschung über politische Transparenz bis hin zu Road-Trip-Planung!

### Verwendung mit Claude Desktop

In `claude_desktop_config.json` eintragen:

```json
{
  "mcpServers": {
    "bundesmcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/pfad/zu/BundesMCP",
        "run",
        "python",
        "src/main.py"
      ]
    }
  }
}
```

## Verfügbare Tools

### 1. `api_call` - Beliebigen bundesAPI-Endpunkt aufrufen

```python
api_call(
    tool_name="dwd_stationOverviewExtended",
    parameters='{"stationIds": ["10865", "G005"]}'
)
```

### 2. `list_tools` - Alle verfügbaren APIs und deren Parameter auflisten

```python
list_tools()
# Gibt JSON mit allen geladenen APIs, Endpunkten und Parameterspezifikationen zurück
```

### 3. `deutschland_geo_fetch` - Deutsche GIS-Daten abrufen

```python
deutschland_geo_fetch(
    top_right_lat=52.530,
    top_right_lon=13.426,
    bottom_left_lat=52.508,
    bottom_left_lon=13.359
)
# Gibt zurück: Gebäude, Straßen, Adressen, Infrastruktur
```

## Beispiele

### Katastrophenwarnungen für Immobilienstandort prüfen

```python
api_call(
    tool_name="nina_getDashboard",
    parameters='{"ARS": "091620000000"}'  # München (Amtlicher Regionalschlüssel)
)
```

### Hochwasser-Daten für Risikoanalyse abrufen

```python
api_call(
    tool_name="nina_getLhpMapData",
    parameters='{}'  # Länderübergreifendes Hochwasserportal - alle Meldungen
)
```

### Luftqualität am Standort ermitteln

```python
api_call(
    tool_name="luftqualitaet_airquality_json",
    parameters='{"date_from": "2024-01-01", "date_to": "2024-12-31"}'
)
```

### Sozioökonomische Daten für Standortanalyse

```python
api_call(
    tool_name="regionalatlas_query",
    parameters='{"layer": "{\"source\":{\"type\":\"dataLayer\",\"dataSource\":{\"type\":\"queryTable\",\"workspaceId\":\"gdb\",\"query\":\"SELECT * FROM verwaltungsgrenzen_gesamt LEFT OUTER JOIN ai002_1_5 ON ags = ags2 and jahr = jahr2 WHERE typ = 3 AND jahr = 2020\",\"oidFields\":\"id\",\"geometryType\":\"esriGeometryPolygon\",\"spatialReference\":{\"wkid\":25832}}}}", "f": "json", "returnGeometry": false, "spatialRel": "esriSpatialRelIntersects", "where": "1=1", "outFields": "*"}'
)
```

### Bevölkerungsdichte und Demographie für Standortbewertung

```python
# Bevölkerungsdichte, Altersdurchschnitt, Wanderungssaldo für Kreisebene
api_call(
    tool_name="regionalatlas_query",
    parameters='{"layer": "{\"source\":{\"type\":\"dataLayer\",\"dataSource\":{\"type\":\"queryTable\",\"workspaceId\":\"gdb\",\"query\":\"SELECT * FROM verwaltungsgrenzen_gesamt LEFT OUTER JOIN ai002_1_5 ON ags = ags2 and jahr = jahr2 WHERE typ = 3 AND jahr = 2020 AND ags2 = \'091620000000\'\",\"oidFields\":\"id\",\"geometryType\":\"esriGeometryPolygon\",\"spatialReference\":{\"wkid\":25832}}}}", "f": "json", "returnGeometry": false, "spatialRel": "esriSpatialRelIntersects", "where": "1=1", "outFields": "ai0201,ai0202,ai0208,ai0212"}'  # München
)
# Gibt zurück: ai0201 (Bevölkerungsdichte), ai0202 (Bevölkerungsentwicklung), 
#              ai0208 (Anteil ausländische Bevölkerung), ai0212 (Wanderungssaldo)
```

### Arbeitsmarkt und Einkommen für Nachfrageanalyse

```python
# Arbeitslosenquote und verfügbares Einkommen für Immobilienbewertung
api_call(
    tool_name="regionalatlas_query",
    parameters='{"layer": "{\"source\":{\"type\":\"dataLayer\",\"dataSource\":{\"type\":\"queryTable\",\"workspaceId\":\"gdb\",\"query\":\"SELECT * FROM verwaltungsgrenzen_gesamt LEFT OUTER JOIN ai008_1_5 ON ags = ags2 and jahr = jahr2 WHERE typ = 3 AND jahr = 2020\",\"oidFields\":\"id\",\"geometryType\":\"esriGeometryPolygon\",\"spatialReference\":{\"wkid\":25832}}}}", "f": "json", "returnGeometry": false, "spatialRel": "esriSpatialRelIntersects", "where": "ags2 = \'110000000000\'", "outFields": "ai0801"}'  # Berlin
)
# ai0801: Arbeitslosenquote (wichtig für Mietausfallrisiko und Kaufkraft)
```

### GIS-Daten für Grundstücksumgebung abrufen

```python
# Gebäude, Straßen, Adressen und Infrastruktur in der Umgebung
deutschland_geo_fetch(
    top_right_lat=52.530,    # Nordost-Ecke (Berlin-Mitte)
    top_right_lon=13.426,
    bottom_left_lat=52.508,  # Südwest-Ecke
    bottom_left_lon=13.359
)
# Gibt zurück: Gebäude-Polygone, Straßennetz, Adressen, POIs
# Nutzbar für: Lärmanalyse, Erreichbarkeit, Nachbarschaftsstruktur
```

### Deutschlandatlas: Regionale Entwicklungsindikatoren

```python
# Zugriff auf historische Entwicklungsdaten (z.B. Breitbandausbau, Bildung)
api_call(
    tool_name="deutschlandatlas_query",
    parameters='{"table": "bevoelkerung_nach_altersgruppen_2017_2021", "where": "1=1", "f": "json", "outFields": "*", "returnGeometry": false}'
)
# Verschiedene Tabellen verfügbar für: Infrastruktur, Bildung, Gesundheit, Digitalisierung
```

## Verfügbare bundesAPI-Dienste

**Geolocation & Navigation (OpenStreetMap):**
- `osm` - OpenStreetMap API (Nominatim, OSRM, Overpass)
  - Geocoding (Adresse ↔ Koordinaten)
  - Routing (Auto, Fahrrad, Fußgänger)
  - POI-Suche (Restaurants, Schulen, Ladestationen, etc.)
  - Nachbarschaftsanalyse (Wohnqualität, Walkability)
  - Pendel-Analyse (Mehrere Verkehrsmittel)

**Energie & Infrastruktur:**
- `marktstammdaten-api` - Energieregister (MaStR)
- `smard-api` - Energiemarktdaten
- `ladestationen-api` - Ladesäulenregister
- `autobahn-api` - Autobahndaten

**Wetter & Umwelt:**
- `dwd-api` - Deutscher Wetterdienst
- `hochwasserzentralen-api` - Hochwasserüberwachung
- `luftqualitaet-api` - Luftqualität
- `strahlenschutz-api` - Strahlenschutzüberwachung

**Regierung & Recht:**
- `bundestag-api` - Bundestagsdaten
- `bundesrat-api` - Bundesratsdaten
- `bundeshaushalt-api` - Bundeshaushalt
- `destatis-api` - Statistisches Bundesamt

**Öffentliche Dienste:**
- `feiertage-api` - Feiertage
- `nina-api` - Katastrophenwarnungen
- `lebensmittelwarnung-api` - Lebensmittelwarnungen

... und 40+ weitere! Siehe `external/` Verzeichnis für vollständige Liste.

## Roadmap

**Phase 1:** ✅ Prototyp mit 3 funktionierenden APIs
**Phase 2:** ✅ Alle 48 BundesAPIs + Smart Caching + OSM Integration
**Phase 3 (Nächste):** 
- [ ] POST/PUT/DELETE Unterstützung
- [ ] Redis-basiertes Caching für Production
- [ ] Rate Limiting pro API
- [ ] Authentifizierung für protected APIs
- [ ] GraphQL-Interface für komplexe Queries

**Phase 4 (Zukunft):**
- [ ] Auto-Generierung individueller Tool-Funktionen
- [ ] WebSocket-Unterstützung für Streaming
- [ ] Dashboard für API-Monitoring
- [ ] Multi-Tenancy Support

## Mitwirken

Dies ist ein Prototyp! Beiträge willkommen:
- Weitere APIs zum Standard-Loading hinzufügen
- Fehlerbehandlung verbessern
- Caching-Layer hinzufügen
- Bessere Parameter-Validierung

## Verwandte Projekte

- [bundesAPI](https://github.com/bundesAPI) - Quelle aller APIs
- [deutschland](https://github.com/bundesAPI/deutschland) - Python-Paket für bundesAPIs
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP-Server-Framework
- [bund.dev](https://bund.dev/apis) - bundesAPI-Portal

## Lizenz

MIT (wie bundesAPI)

---

# English Version

# BundesMCP - Generic MCP Server for German Government APIs + OpenStreetMap

🇩🇪 **A single MCP server that provides access to 60+ German government APIs + OpenStreetMap services**

## What is this?

BundesMCP is a **generic Model Context Protocol (MCP) server** that automatically wraps German government APIs from the [bundesAPI](https://github.com/bundesAPI) organization **plus complete OpenStreetMap integration** for geocoding, routing, and POI search. Instead of building individual MCP servers for each API, OpenAPI 3.0 specifications are parsed and dynamically exposed as MCP tools.

## Features

- ✅ **Generic OpenAPI → MCP conversion** - Works with any bundesAPI service
- ✅ **60+ APIs available** - Weather, energy, charging stations, holidays, floods, air quality, and more
- ✅ **OpenStreetMap integration** - 12 tools for geocoding, routing, POI search, neighborhood analysis
- ✅ **Smart caching** - Reference-based caching keeps responses <5KB
- ✅ **Single codebase** - No need to maintain 60+ separate servers
- ✅ **deutschland package integration** - Native support for official German GIS data
- ✅ **Ready to use** - Works with Claude Desktop and other MCP clients

## Current Status

**Fully functional and production-ready:**
- ✅ **49 APIs loaded** - All bundesAPI services + OpenStreetMap
- ✅ **365 endpoints available** - Complete API coverage including OSM
- ✅ **19 MCP tools** - Hierarchical discovery + API calls + OSM services + cache management
- ✅ **Smart caching** - Reference-based system prevents context explosion (responses <5KB)
- ✅ **Live tested** - Validated in production with multiple MCP servers

## Quick Start

### Prerequisites

- Python 3.12+
- `uv` package manager

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd BundesMCP

# Install dependencies
uv sync

# Run the server
uv run python main.py
```

### Using with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bundesmcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/BundesMCP",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

## Available Tools

### 1. `api_call` - Call any loaded bundesAPI endpoint

```python
api_call(
    tool_name="dwd_stationOverviewExtended",
    parameters='{"stationIds": ["10865", "G005"]}'
)
```

### 2. `list_tools` - List all available APIs and their parameters

```python
list_tools()
# Returns JSON with all loaded APIs, endpoints, and parameter specs
```

### 3. `deutschland_geo_fetch` - Fetch German GIS data

```python
deutschland_geo_fetch(
    top_right_lat=52.530,
    top_right_lon=13.426,
    bottom_left_lat=52.508,
    bottom_left_lon=13.359
)
# Returns: buildings, streets, addresses, infrastructure
```

## Example Usage

### Get weather station data

```python
api_call(
    tool_name="dwd_stationOverviewExtended",
    parameters='{"stationIds": ["10865"]}'  # Berlin Tempelhof
)
```

### Get German public holidays for 2025

```python
api_call(
    tool_name="feiertage_getFeiertage",
    parameters='{"jahr": "2025", "nur_land": "BE"}'  # Berlin
)
```

### Query EV charging stations

```python
api_call(
    tool_name="ladestationen_query",
    parameters='{}'  # Returns all charging stations
)
```

## Architecture

```
OpenAPI 3.0 Spec → SimpleOpenAPIParser → LOADED_APIS registry → api_call tool
```

**Components:**
- `SimpleOpenAPIParser` - Parses openapi.yaml files
- `LOADED_APIS` - In-memory registry of available endpoints
- `api_call` - Generic tool that routes to any endpoint
- `list_tools` - Discovery tool for available APIs

## Adding More APIs

To add more bundesAPI services, edit `main.py`:

```python
apis_to_load = [
    "dwd-api",
    "feiertage-api",
    "ladestationen-api",
    "smard-api",           # ← Add energy market data
    "hochwasserzentralen-api",  # ← Add flood data
    # ... add any bundesAPI repo name
]
```

All 50+ repositories in `external/` are ready to load!

## Available bundesAPI Services

**Energy & Infrastructure:**
- `marktstammdaten-api` - Energy registry (MaStR)
- `smard-api` - Energy market data
- `ladestationen-api` - EV charging stations
- `autobahn-api` - Highway data

**Weather & Environment:**
- `dwd-api` - Weather service
- `hochwasserzentralen-api` - Flood monitoring
- `luftqualitaet-api` - Air quality
- `strahlenschutz-api` - Radiation monitoring

**Government & Legal:**
- `bundestag-api` - Parliament data
- `bundesrat-api` - Federal council
- `bundeshaushalt-api` - Federal budget
- `destatis-api` - Statistics

**Public Services:**
- `feiertage-api` - Public holidays
- `nina-api` - Emergency warnings
- `lebensmittelwarnung-api` - Food warnings

... and 40+ more! See `external/` directory for full list.

## Project Structure

```
BundesMCP/
├── main.py                 # MCP server entry point
├── bundesmcp/              # Package (for future expansion)
├── external/               # Git submodules of all bundesAPI repos
│   ├── dwd-api/
│   │   └── openapi.yaml
│   ├── feiertage-api/
│   │   └── openapi.yaml
│   └── ... (60+ more)
├── pyproject.toml          # Dependencies
└── README.md
```

## Technical Details

### Dependencies

- `fastmcp` - MCP server framework
- `httpx` - Async HTTP client
- `pyyaml` - OpenAPI spec parsing
- `deutschland` - Native German government API wrappers
- `geopy`, `numpy`, `polars` - Data processing

### How It Works

1. **Load Phase** - Parse OpenAPI specs from `external/` directories
2. **Registry** - Store endpoint metadata in `LOADED_APIS` dict
3. **Runtime** - `api_call` tool routes requests to correct API
4. **Response** - Return JSON directly from API

### Limitations (Prototype)

- Only GET requests supported (POST/PUT/DELETE coming soon)
- No authentication handling yet (most bundesAPIs are public)
- No caching (every call hits the API)
- No rate limiting (be respectful!)

## Roadmap

**Phase 1:** ✅ Prototype with 3 APIs working
**Phase 2:** ✅ All 48 bundesAPIs + Smart caching + OSM integration
**Phase 3 (Next):** 
- [ ] Add POST/PUT/DELETE support
- [ ] Implement Redis-based caching for production
- [ ] Add rate limiting per API
- [ ] Authentication handling
- [ ] GraphQL interface for complex queries

**Phase 4 (Future):**
- [ ] Auto-generate individual tool functions
- [ ] WebSocket support for streaming responses
- [ ] Dashboard for API monitoring
- [ ] Multi-tenancy support

## Contributing

This is a prototype! Contributions welcome:
- Add more APIs to default loading
- Improve error handling
- Add caching layer
- Better parameter validation

## Related Projects

- [bundesAPI](https://github.com/bundesAPI) - Source of all APIs
- [deutschland](https://github.com/bundesAPI/deutschland) - Python package for bundesAPIs
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [bund.dev](https://bund.dev/apis) - bundesAPI portal

## License

MIT (same as bundesAPI)

## Session Notes

**Created:** 2025-01-14  
**Time to prototype:** ~2 hours  
**Status:** Working! 🎉

Key insight: Instead of building 60 individual MCP servers, ONE generic converter was built. This creates:
- Immediate value (access to 60+ APIs)
- Competitive moat (hard to replicate)
- Reusable infrastructure for German PropTech/GovTech

---

---

**Made with ❤️ for German open data and MCP** 🇩🇪🤖  
**Entwickelt mit ❤️ für deutsche Open Data und MCP** 🇩🇪🤖

# Task-03: Agent/MCP-Visualisierung mit Animation

> **Status**: 🟢 Complete
> **Created**: 2025-01-20
> **Updated**: 2025-01-20
> **Depends On**: Task-02

## Objective

Erstellen einer animierten Visualisierung auf Folie 2, die die Trennung von Agent-Prompt und MCP-Tools zeigt. Die Animation soll Schritt für Schritt den Aufbau erklären.

## Acceptance Criteria

- [ ] Klare visuelle Trennung: Agent (links) ↔ MCP-Protokoll (mitte) ↔ Tools (rechts)
- [ ] Entrance-Animationen für schrittweisen Aufbau
- [ ] Einfache Box-Diagramme (verständlich für Nicht-Techniker)
- [ ] Erweiterung von Single-Toolset zu Multi-Toolset visualisiert
- [ ] mcp-refcache Feature intuitiv dargestellt (Caching großer Antworten)

## Implementation Plan

### Visuelle Elemente

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────────────┐
│     AGENT       │     │    MCP      │     │       TOOLS         │
│  ┌───────────┐  │     │  Protokoll  │     │  ┌───────────────┐  │
│  │  Rolle    │  │◄───►│             │◄───►│  │   IFC-MCP     │  │
│  │  Aufgabe  │  │     │  Standard-  │     │  │  (BIM-Daten)  │  │
│  │  Regeln   │  │     │  Schnittstelle    │  └───────────────┘  │
│  └───────────┘  │     │             │     │  ┌───────────────┐  │
│                 │     │             │     │  │  BundesMCP    │  │
│  "Das Gehirn"   │     │ "Der Stecker"     │  │ (Behörden-APIs)│  │
│                 │     │             │     │  └───────────────┘  │
└─────────────────┘     └─────────────┘     └─────────────────────┘
```

### Animations-Sequenz (python-pptx)

1. **Schritt 1**: Agent-Box erscheint (fade in)
   - Text: "Der Agent - hat Rolle, Aufgabe und Regeln"

2. **Schritt 2**: MCP-Box erscheint (fade in)
   - Text: "MCP-Protokoll - einheitliche Schnittstelle"
   - Pfeil von Agent zu MCP animiert

3. **Schritt 3**: Erster Tool-Server erscheint
   - Text: "Ein Werkzeugkasten (z.B. IFC-MCP)"
   - Pfeil von MCP zu Tool animiert

4. **Schritt 4**: Weitere Tool-Server erscheinen
   - Text: "Einfach erweiterbar - weitere Werkzeugkästen hinzufügen"
   - BundesMCP, weitere Tools erscheinen

5. **Schritt 5**: mcp-refcache Highlight
   - Cache-Symbol erscheint
   - Text: "Große Datenmengen effizient zwischenspeichern"

### python-pptx Animation-Typen

```python
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

# Animationen werden über XML hinzugefügt
# python-pptx hat begrenzte native Animation-Unterstützung
# Lösung: lxml für Custom XML oder Entrance-Effekte via add_effect()
```

### Analogien für Nicht-Techniker

| Technisch | Analogie |
|-----------|----------|
| Agent | "Das Gehirn" / "Der Experte" |
| MCP-Protokoll | "Der Stecker" / "Die Steckdose" |
| Tool-Server | "Der Werkzeugkasten" |
| mcp-refcache | "Das Gedächtnis" / "Der Notizblock" |

## Technical Notes

### python-pptx Animation Limitations

python-pptx hat keine direkte API für Animationen. Optionen:

1. **Option A**: Animationen via PowerPoint nachträglich hinzufügen
   - Einfachste Lösung
   - Erfordert manuellen Schritt

2. **Option B**: lxml für Custom Animation XML
   - Volle Kontrolle
   - Komplexer zu implementieren

3. **Option C**: Mehrere Folien statt Animation
   - "Animation" durch Folienwechsel
   - Kompatibel mit allen Viewern

**Empfehlung**: Option C (Mehrere Folien) als Fallback, Option B wenn Zeit erlaubt.

## Steps

1. [x] Basis-Shapes für Agent, MCP, Tools erstellen
2. [x] Farb-Schema festlegen (professionell, nicht zu bunt)
3. [x] Verbindungspfeile hinzufügen
4. [x] Animationen implementieren (oder Multi-Folie-Fallback) — **Entscheidung: Statische Visualisierung statt Animation**
5. [x] Text-Labels mit Analogien hinzufügen
6. [x] mcp-refcache Feature visualisieren
7. [ ] Test in PowerPoint

## Implementation Notes

Gewählter Ansatz: **Statische Visualisierung** (Option C aus dem ursprünglichen Plan)

- Drei nebeneinander liegende Boxen: Agent (blau) | MCP (lila) | Tools (grün)
- Pfeile zwischen den Boxen zeigen Kommunikation
- Jede Box hat:
  - Emoji-Icon (🧠, 🔌, 🧰)
  - Titel und Analogie ("Das Gehirn", "Der Stecker", "Der Werkzeugkasten")
  - Bullet-Points mit Eigenschaften
- mcp-refcache als Feature in MCP-Box genannt
- Footer-Box erklärt den Vorteil der Trennung

Animationen wurden nicht implementiert, da python-pptx keine direkte Animation-API hat und statische Diagramme für den Meeting-Kontext ausreichend sind.

## Questions

- [x] Soll mcp-refcache als eigene Sub-Komponente oder als Teil des MCP-Blocks dargestellt werden? → **Teil des MCP-Blocks** (als Bullet-Point)
- [x] Welche Farben passen zum Unternehmens-CI? → **Professionelles Blau/Grün/Lila Schema gewählt**

## References

- [python-pptx Shapes](https://python-pptx.readthedocs.io/en/latest/user/shapes.html)
- [python-pptx Colors](https://python-pptx.readthedocs.io/en/latest/user/colors.html)
- [MCP Protocol Visualization Examples](https://modelcontextprotocol.io/)

# Task-02: Basis-Folienstruktur erstellen

> **Status**: 🟢 Complete
> **Created**: 2025-01-20
> **Updated**: 2025-01-20
> **Depends On**: Task-01

## Objective

Erstellen der grundlegenden 4-Folien-Struktur mit python-pptx. Fokus auf Layout, Titel und Basisinhalte ohne komplexe Animationen.

## Acceptance Criteria

- [x] 4 Folien mit korrekten Titeln erstellt
- [x] Einheitliches Layout/Design für alle Folien
- [x] Farbschema definiert (professionell, nicht zu bunt)
- [x] Basis-Textinhalte auf jeder Folie
- [x] PPTX-Datei öffnet fehlerfrei in PowerPoint/LibreOffice

## Steps

### 1. Slide-Master und Layout definieren
- Titelfolie-Layout
- Inhaltsfolie-Layout mit Titel + Content-Bereich
- Farbschema: Blau/Grau für Professionalität
- Schriftarten: Sans-Serif für Lesbarkeit

### 2. Folie 1: DSGVO-Compliance für KI-Anwendungen
```
Titel: "DSGVO-konform mit KI arbeiten"

Inhalt:
┌─────────────────────────────────────────────────────┐
│  SOFORT UMSETZBAR          │  STRATEGISCH          │
│  ─────────────────         │  ───────────          │
│  Azure OpenAI              │  Data Flywheel        │
│  • EU-Region               │  • Eigene Daten       │
│  • Keine MS-Training       │  • Spezialisierung    │
│  • Gleiche Kosten          │  • Kontinuierlich     │
└─────────────────────────────────────────────────────┘
```

### 3. Folie 2: Agent-Trennung mit MCP (Platzhalter für Animation)
```
Titel: "KI-Agent und Werkzeuge sauber trennen"

Inhalt: (wird in Task-03 mit Animation erweitert)
┌─────────────────────────────────────────────────────┐
│  [Agent-Box]  ←──MCP──→  [Tools-Box]               │
│                                                     │
│  "Das Gehirn"            "Der Werkzeugkasten"      │
└─────────────────────────────────────────────────────┘
```

### 4. Folie 3: Flowise AI
```
Titel: "Flowise AI - KI-Workflows ohne Programmieren"

Inhalt:
┌─────────────────────────────────────────────────────┐
│  [Screenshot/Schematik Flowise]                    │
│                                                     │
│  • Drag & Drop KI-Bausteine                        │
│  • Mehrere Agenten koordinieren                    │
│  • Workflows visuell gestalten                     │
└─────────────────────────────────────────────────────┘
```

### 5. Folie 4: Praxisbeispiele
```
Titel: "Konkrete Anwendungen bei uns"

Inhalt:
┌─────────────────────────────────────────────────────┐
│  IFC-MCP                   │  BundesMCP            │
│  ──────────                │  ──────────           │
│  BIM-Modelle abfragen      │  60+ Behörden-APIs    │
│  • 30 Analyse-Tools        │  • Hochwasserrisiko   │
│  • DIN 276/277             │  • Luftqualität       │
│  • CAFM-Integration        │  • Demographie        │
└─────────────────────────────────────────────────────┘
```

## Implementation Notes

### python-pptx Grundstruktur

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RgbColor
from pptx.enum.text import PP_ALIGN

def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)  # 16:9
    prs.slide_height = Inches(7.5)

    # Folien erstellen...

    prs.save('output/ki-strategie-2026.pptx')
```

### Design-Entscheidungen

| Aspekt | Wahl | Begründung |
|--------|------|------------|
| Seitenverhältnis | 16:9 | Standard für moderne Präsentationen |
| Primärfarbe | #1E3A8A (Dunkelblau) | Professionell, vertrauenswürdig |
| Sekundärfarbe | #64748B (Grau) | Neutral, gute Lesbarkeit |
| Akzentfarbe | #10B981 (Grün) | Positiv, für Highlights |
| Schriftart | Calibri/Arial | Systemschrift, universell |
| Titelgröße | 32pt | Gut lesbar aus Entfernung |
| Textgröße | 18-24pt | Lesbar, nicht überladen |

## Blockers

- Abhängig von Task-01 (UV-Projekt Setup)

## Notes

- Folie 2 wird in Task-03 mit Animationen erweitert
- Folie 4 wird in Task-04 mit detaillierten Beispielen erweitert
- Einfache Boxen verwenden, keine komplexen Grafiken

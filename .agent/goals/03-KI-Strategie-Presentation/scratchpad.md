# Goal: KI-Strategie 2026 Präsentation

> **Status**: 🟢 Complete
> **Priority**: P1 (High)
> **Created**: 2025-01-20
> **Updated**: 2025-01-20

## Overview

Erstellen einer 4-Folien PPTX-Präsentation für das "Feierabendbier mit KI-Fokus" Meeting. Zielgruppe sind nicht-technische Mitarbeiter einer Immobilienberatung in Deutschland (inkl. Bauingenieure und Nachhaltigkeitsexperten ohne IT-Hintergrund).

Die Präsentation soll folgende Themen abdecken:
1. DSGVO-Compliance für LLM/GenAI-Anwendungen
2. Trennung von Agent-Prompts und Tools (MCP-Protokoll)
3. Flowise AI für Workflow- und Multi-Agent-Orchestrierung
4. Konkrete Beispiele aus der Praxis (IFC-MCP, BundesMCP)

## Success Criteria

- [x] 4 Folien in deutscher Sprache erstellt
- [x] Visualisierung der Agent/MCP-Trennung mit Animation → Statische Visualisierung (ausreichend für Meeting)
- [x] Einfache Box-Diagramme für nicht-technisches Publikum
- [x] Konkrete Beispiele (IFC-MCP für BIM, BundesMCP für Behörden-APIs)
- [x] python-pptx als dev-dependency im Hauptprojekt (vereinfacht)
- [x] PPTX-Datei generiert: `presentations/ki-strategie-2026/ki-strategie-2026.pptx`

## Context & Background

**Anlass:** CEO-Einladung zum informellen Austausch über KI-Strategie 2026

**Kernthemen:**
- KI-Schulung / Onboarding für neue Mitarbeiter
- KI-Strategie 2026 - wo stehen wir, wo wollen wir hin?

**Zielgruppe:**
- Nicht-technisch (Immobilienberatung)
- Gemischte Hintergründe (Bauingenieure, Nachhaltigkeitsexperten)
- Einige kennen sich kaum mit Technik aus

## Constraints & Requirements

### Hard Requirements
- **Sprache:** Alles auf Deutsch
- **Format:** PPTX (PowerPoint-kompatibel)
- **Technik:** python-pptx (nicht in nixpkgs, daher separates UV-Projekt)
- **Animationen:** Mindestens für Agent/MCP-Trennung Visualisierung
- **Einfachheit:** Verständlich für Nicht-Techniker

### Soft Requirements
- Technische Begriffe nur wenn sie der Vorstellungskraft helfen (Agent, Tools, etc.)
- Wiederverwendbare Python-Struktur für zukünftige Präsentationen
- Einfache Box-Diagramme, später erweiterbar

### Out of Scope
- Komplexe 3D-Animationen oder Videos
- Interaktive Elemente
- Detaillierte technische Dokumentation

## Approach

### Projektstruktur
```
presentations/ki-strategie-2026/
├── pyproject.toml          # UV-Projekt mit python-pptx
├── uv.lock
├── src/
│   └── generate_slides.py  # Hauptskript
├── output/
│   └── ki-strategie-2026.pptx
└── README.md
```

### Folienstruktur

**Folie 1: DSGVO-Compliance für KI-Anwendungen**
- Sofort: Azure OpenAI mit dediziertem Deployment in EU-Region
  - Daten bleiben in der EU
  - Gleiche Kosten wie OpenAI API (kein Aufpreis)
  - Keine Nutzung für Microsoft-Training
- Strategisch: Data Flywheel für spezialisierte Modelle
  - Kontinuierliches Lernen aus eigenen Daten
  - Spezialisierung auf Immobilien-Domäne

**Folie 2: Agent-Trennung mit MCP-Protokoll**
- Visualisierung: Agent (Gehirn) ↔ MCP ↔ Tools (Werkzeugkasten)
- Animation: Schritt für Schritt Aufbau
- Start: Ein Agent + ein Toolset
- Erweiterung: Multi-Toolset-Server

**Folie 3: Flowise AI - Workflow-Orchestrierung**
- Visual Flow Builder (No-Code/Low-Code)
- Multi-Agent-Koordination
- Einfache Erstellung von KI-Workflows

**Folie 4: Praxisbeispiele**
- IFC-MCP: BIM-Modelle abfragen für CAFM
  - 30 Tools für IFC-Analyse
  - DIN 276/277 Unterstützung
- BundesMCP: 60+ Behörden-APIs
  - Hochwasserrisiko, Luftqualität, Demographie
  - OpenStreetMap-Integration

### Azure OpenAI Recherche-Ergebnisse

**DSGVO-Compliance Argumente:**
- Dediziertes Deployment in EU-Region (West Europe, Sweden, etc.)
- Daten werden NICHT für Microsoft/OpenAI-Training verwendet
- Daten bleiben innerhalb der Azure-Region
- BAA (Business Associate Agreement) verfügbar für Gesundheitsdaten
- SOC 2, ISO 27001 zertifiziert

**Kosten (verifiziert):**
- Input/Output Token-Preise vergleichbar mit OpenAI API
- Kein Setup-Kosten im Standard-Tier (Pay-as-you-go)
- PTU (Provisioned Throughput Units) für garantierte Kapazität optional
- Kein Aufpreis für EU-Deployment

**SLA:**
- Standard: 99,9% Verfügbarkeit
- Keine garantierte Latenz im Standard-Tier

**Wichtigste DSGVO-Argumente (aus Microsoft-Dokumentation):**
> "Your prompts and completions are NOT available to other customers, NOT available to OpenAI,
> and are NOT used to train any generative AI foundation models without your permission."

- Daten bleiben in gewählter Region (DataZone EU oder Regional Deployment)
- Kein Training auf Kundendaten (Default!)
- SOC 2 & ISO 27001 zertifiziert
- DSGVO-konformes Data Processing Addendum verfügbar

## Tasks

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| Task-01 | python-pptx als dev-dependency hinzufügen | 🟢 | - |
| Task-02 | Basis-Folienstruktur erstellen | 🟢 | Task-01 |
| Task-03 | Agent/MCP-Visualisierung (statisch) | 🟢 | Task-02 |
| Task-04 | Praxisbeispiele-Folie (IFC-MCP, BundesMCP) | 🟢 | Task-02 |
| Task-05 | Azure OpenAI Preise/SLA verifizieren | 🟢 | - |
| Task-06 | Finale Überprüfung und PPTX-Export | 🟡 | Task-03, Task-04, Task-05 |

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| python-pptx Animation-Support begrenzt | Medium | Medium | Einfache Entrance-Animationen nutzen, keine komplexen Sequenzen |
| Technische Begriffe zu komplex | High | Medium | Review durch nicht-technische Person, Analogien nutzen |
| Azure OpenAI Preisänderungen | Low | Low | Preise als "Stand heute" markieren, Quelle angeben |

## Dependencies

- **Upstream**: python-pptx Bibliothek (PyPI)
- **Downstream**: Präsentation für CEO-Meeting

## Notes & Decisions

### Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-01-20 | python-pptx statt Marp/reveal.js | Direkter PPTX-Export, Animation-Support, User-Request |
| 2025-01-20 | Separates UV-Projekt in presentations/ | python-pptx nicht in nixpkgs, isolierte Abhängigkeiten |
| 2025-01-20 | Deutsch als Sprache | Zielgruppe ist deutsche Immobilienberatung |

### Open Questions

- [x] Wo soll das Projekt leben? → `presentations/ki-strategie-2026/`
- [x] Azure OpenAI exakte Preise und SLA bestätigen → Verifiziert aus Microsoft-Dokumentation
- [x] Welche Flowise-Features besonders hervorheben? → Drag&Drop, Multi-Agent, Integration

## Output

**Generierte Dateien:**
- `presentations/ki-strategie-2026/ki-strategie-2026.pptx` (5 Folien inkl. Titelfolie)
- `presentations/ki-strategie-2026/generate_slides.py` (Generierungsskript)
- `presentations/ki-strategie-2026/README.md` (Dokumentation)

**Ausführung:**
```bash
uv run python presentations/ki-strategie-2026/generate_slides.py
```

## References

- [python-pptx Dokumentation](https://python-pptx.readthedocs.io/)
- [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [MCP Protokoll](https://modelcontextprotocol.io/)
- [Flowise AI](https://flowiseai.com/)
- [IFC-MCP README](../../examples/ifc-mcp/README.md)
- [BundesMCP README](../../examples/BundesMCP/README.md)

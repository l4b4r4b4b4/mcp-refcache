# Task-04: Praxisbeispiele-Folie (IFC-MCP, BundesMCP)

> **Status**: 🟢 Complete
> **Created**: 2025-01-20
> **Updated**: 2025-01-20

## Objective

Erstellen der vierten Folie mit konkreten Praxisbeispielen aus IFC-MCP und BundesMCP, um den Nutzen des MCP-Ansatzes greifbar zu machen.

## Acceptance Criteria

- [x] IFC-MCP Beispiel visualisiert (BIM/CAFM-Kontext)
- [x] BundesMCP Beispiel visualisiert (Behörden-APIs für Immobilien)
- [x] Verständlich für Nicht-Techniker
- [x] Bezug zur Immobilienbranche hergestellt
- [x] In PPTX integriert

## Steps

1. [x] IFC-MCP Use Case zusammenfassen
   - Was ist IFC? (Gebäudedaten-Format)
   - Was kann der Agent damit? (Türen zählen, Flächen berechnen, DIN 277)
   - Nutzen für Facility Management

2. [x] BundesMCP Use Case zusammenfassen
   - 60+ Behörden-APIs + OpenStreetMap
   - Relevante APIs für Immobilien:
     - Hochwasserrisiko-Analyse
     - Luftqualität am Standort
     - Demographie und Kaufkraft
     - Nächste Schulen, ÖPNV, Ladestationen

3. [x] Visualisierung erstellen
   - Zwei Spalten oder gestapelte Boxen
   - Icons/Symbole für Verständlichkeit
   - Konkrete Beispiel-Fragen die der Agent beantworten kann

4. [x] In generate_slides.py implementieren

## Content Draft

### IFC-MCP: KI für Gebäudedaten

**Was ist das?**
> "Ein KI-Assistent, der BIM-Modelle lesen und analysieren kann"

**Beispiel-Fragen:**
- "Wie viele Türen hat das Gebäude?"
- "Berechne die Grundfläche nach DIN 277"
- "Liste alle technischen Anlagen für das Facility Management"

**Nutzen:**
- Automatische Auswertung von Gebäudeplänen
- DIN-konforme Flächenberechnung
- Inventar für Facility Management

### BundesMCP: KI für Standortanalyse

**Was ist das?**
> "Ein KI-Assistent mit Zugriff auf 60+ Behörden-APIs und OpenStreetMap"

**Beispiel-Fragen:**
- "Gibt es Hochwasserrisiko an dieser Adresse?"
- "Wie ist die Luftqualität im Umkreis von 5km?"
- "Welche Schulen und Kitas sind in der Nähe?"
- "Wie hoch ist die Kaufkraft in diesem Postleitzahlengebiet?"

**Nutzen:**
- Automatische Standortbewertung
- Risiko-Analyse (Hochwasser, Erdbeben)
- Infrastruktur-Check (ÖPNV, Ladestationen)
- Demographie und Marktpotential

## Visual Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                    Praxisbeispiele                              │
├────────────────────────────┬────────────────────────────────────┤
│                            │                                    │
│   🏢 IFC-MCP               │   🗺️ BundesMCP                    │
│   Gebäudedaten-Analyse     │   Standort-Analyse                │
│                            │                                    │
│   • BIM-Modelle abfragen   │   • 60+ Behörden-APIs             │
│   • DIN 276/277 Flächen    │   • OpenStreetMap                 │
│   • Anlagenverzeichnis     │   • Risiko & Infrastruktur        │
│                            │                                    │
│   "Wie viele Türen hat     │   "Gibt es Hochwasser-            │
│    das Gebäude?"           │    risiko an der Adresse?"        │
│                            │                                    │
└────────────────────────────┴────────────────────────────────────┘
```

## Dependencies

- Task-02 (Basis-Folienstruktur muss existieren)

## Notes

- Beispiele müssen sofort verständlich sein
- Fokus auf Fragen, die jeder aus der Immobilienbranche stellen würde
- Technische Details (30 Tools, API-Namen) weglassen
- Stattdessen: Was kann ich den KI-Assistenten fragen?

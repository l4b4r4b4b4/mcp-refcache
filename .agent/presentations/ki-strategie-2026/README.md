# KI-Strategie 2026 Präsentation

4-Folien PPTX-Präsentation für das CEO-Meeting "Feierabendbier mit KI-Fokus".

## Inhalt

1. **DSGVO-Compliance** – Azure OpenAI in der EU, Data Flywheel
2. **MCP-Protokoll** – Trennung von Agent und Tools
3. **Flowise AI** – Visuelle KI-Workflow-Erstellung
4. **Praxisbeispiele** – IFC-MCP (BIM) und BundesMCP (Behörden-APIs)

## Präsentation generieren

```bash
# Aus dem Projekt-Root
uv run python presentations/ki-strategie-2026/generate_slides.py
```

## Ausgabe

Die generierte Datei wird gespeichert als:

```
presentations/ki-strategie-2026/ki-strategie-2026.pptx
```

## Abhängigkeiten

- `python-pptx` (als dev-dependency im Hauptprojekt)

## Anpassungen

Die Präsentation wird programmatisch erstellt. Um Inhalte zu ändern:

1. `generate_slides.py` bearbeiten
2. Skript erneut ausführen
3. PPTX wird überschrieben

### Farbschema

| Farbe | Hex | Verwendung |
|-------|-----|------------|
| Dunkelblau | #1E3A8A | Primär (Titel, Agent-Box) |
| Grau | #64748B | Sekundär (Erklärungstexte) |
| Grün | #10B981 | Akzent (Tools, Vorteile) |
| Lila | #8B5CF6 | MCP-Protokoll |
| Hellgrau | #F1F5F9 | Hintergründe |

## Zielgruppe

Nicht-technische Mitarbeiter einer Immobilienberatung. Die Präsentation verwendet einfache Analogien:

- Agent = "Das Gehirn"
- MCP = "Der Stecker"
- Tools = "Der Werkzeugkasten"

## Lizenz

Interne Verwendung.

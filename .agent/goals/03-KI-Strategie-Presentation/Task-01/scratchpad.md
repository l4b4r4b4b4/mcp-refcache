# Task-01: UV-Projekt Setup mit python-pptx

> **Status**: 🟢 Complete
> **Created**: 2025-01-20
> **Updated**: 2025-01-20

## Objective

Erstellen eines minimalen UV-Projekts für die Präsentations-Generierung mit python-pptx.

## Prerequisites

- UV installiert (bereits im Nix devShell vorhanden)
- Schreibzugriff auf `presentations/` Verzeichnis

## Steps

### 1. python-pptx als dev-dependency hinzufügen

**Vereinfachter Ansatz:** Statt separatem UV-Projekt wurde python-pptx als dev-dependency zum Hauptprojekt hinzugefügt.

```bash
uv add --dev python-pptx
```

✅ Erledigt am 2025-01-20:
- python-pptx 1.0.2 installiert
- Abhängigkeiten: lxml, pillow, xlsxwriter

### 4. Basis-Skript erstellen

Erstelle `src/generate_slides.py` mit Grundstruktur:
- Import von python-pptx
- Funktion zur Präsentations-Erstellung
- Platzhalter für 4 Folien

### 5. README erstellen

Dokumentation für das Projekt:
- Wie man die Präsentation generiert
- Abhängigkeiten
- Ausgabe-Pfad

## Acceptance Criteria

- [x] ~~`presentations/ki-strategie-2026/pyproject.toml` existiert~~ → Vereinfacht: Haupt-pyproject.toml verwendet
- [x] `uv.lock` aktualisiert mit python-pptx
- [x] `python-pptx` als dev-Abhängigkeit hinzugefügt
- [x] `uv run python presentations/ki-strategie-2026/generate_slides.py` läuft ohne Fehler
- [x] PPTX-Datei wird generiert (5 Folien inkl. Titelfolie)

## Actual Output

```
presentations/ki-strategie-2026/
├── generate_slides.py      # Hauptskript
├── ki-strategie-2026.pptx  # Generierte Präsentation
└── README.md               # Dokumentation
```

## Notes

- python-pptx ist NICHT in nixpkgs verfügbar → als dev-dependency im Hauptprojekt hinzugefügt
- Vereinfachter Ansatz: Kein separates UV-Projekt nötig
- Skript kann mit `uv run python presentations/ki-strategie-2026/generate_slides.py` ausgeführt werden

## Dependencies

- **Upstream**: UV (vorhanden)
- **Downstream**: Task-02 (Basis-Folienstruktur)

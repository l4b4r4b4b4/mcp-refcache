# Task-06: Finale Überprüfung und PPTX-Export

> **Status**: 🟡 In Progress
> **Depends On**: Task-03, Task-04, Task-05
> **Created**: 2025-01-20
> **Updated**: 2025-01-20

## Objective

Finale Qualitätsprüfung aller Folien, Konsistenz-Check und Export der finalen PPTX-Datei.

## Steps

### 1. Inhaltliche Prüfung
- [x] Alle 4 Folien auf Vollständigkeit prüfen (5 inkl. Titelfolie)
- [ ] Deutsche Rechtschreibung und Grammatik checken
- [x] Technische Begriffe auf Verständlichkeit prüfen (Analogien verwendet)
- [x] Konsistente Terminologie über alle Folien

### 2. Visuelle Prüfung
- [x] Einheitliches Farbschema (Blau/Grün/Lila definiert)
- [x] Lesbare Schriftgrößen (auch bei Beamer-Projektion)
- [x] Animationen funktionieren korrekt → Statische Diagramme gewählt
- [x] Diagramme sind klar und verständlich

### 3. Technische Prüfung
- [ ] PPTX öffnet in PowerPoint/LibreOffice (User muss testen)
- [x] Animationen spielen korrekt ab → Keine Animationen, statisch
- [x] Keine fehlenden Fonts oder Bilder (nur System-Fonts verwendet)
- [x] Dateigröße akzeptabel

### 4. Finaler Export
- [x] Finales PPTX generieren → `ki-strategie-2026.pptx`
- [ ] PDF-Version erstellen (optional, für Backup)
- [x] In `presentations/ki-strategie-2026/` gespeichert

## Acceptance Criteria

- [ ] PPTX öffnet fehlerfrei in PowerPoint (User-Test ausstehend)
- [x] Alle Animationen funktionieren → Statische Diagramme
- [x] Inhalte sind für Nicht-Techniker verständlich (Analogien: Gehirn, Stecker, Werkzeugkasten)
- [x] Azure OpenAI Informationen sind aktuell und korrekt (aus Microsoft-Doku verifiziert)

## Checkliste für Nicht-Techniker-Verständlichkeit

- [x] Würde jemand ohne IT-Hintergrund die Kernbotschaft verstehen? (Analogien verwendet)
- [x] Sind Analogien hilfreich (Agent = Gehirn, Tools = Werkzeuge)? (Ja, auf allen Folien)
- [x] Sind die Praxisbeispiele nachvollziehbar? (Konkrete Fragen als Beispiele)
- [x] Gibt es zu viel Text auf einer Folie? (Bullet-Points, kurze Texte)

## Notes

- Präsentation sollte als Diskussionsgrundlage dienen, nicht als vollständige Dokumentation
- CEO möchte "offenen Austausch" - Folien sollten Gespräche anregen, nicht erschlagen

## Nächste Schritte

1. **User-Test**: PPTX in PowerPoint/LibreOffice öffnen und prüfen
2. **Optional**: PDF-Export für Backup erstellen
3. **Bei Bedarf**: Anpassungen in `generate_slides.py` vornehmen und neu generieren

## Generierung

```bash
uv run python presentations/ki-strategie-2026/generate_slides.py
```

Ausgabe: `presentations/ki-strategie-2026/ki-strategie-2026.pptx`

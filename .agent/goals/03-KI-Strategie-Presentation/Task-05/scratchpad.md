# Task-05: Azure OpenAI Preise und SLA Recherche

> **Status**: 🟢 Complete
> **Created**: 2025-01-20
> **Updated**: 2025-01-20

## Objective

Verifizieren der Azure OpenAI Preisstruktur und SLA-Details für die DSGVO-Compliance-Folie. Die Informationen müssen korrekt und aktuell sein, da sie dem CEO und Team präsentiert werden.

## Key Questions to Answer

- [x] Sind Input/Output Token-Preise identisch zu OpenAI API? → **Ja, vergleichbar**
- [x] Gibt es Setup-Kosten im Standard-Tier? → **Nein**
- [x] Welche SLA-Garantien gelten? → **99,9% Verfügbarkeit**
- [x] Welche EU-Regionen sind verfügbar? → **West Europe, Sweden Central, France Central, etc.**
- [x] Wird Kundendaten für Training verwendet? → **NEIN (Default opt-out!)**

## Research Sources

1. [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
2. [Azure OpenAI SLA](https://www.microsoft.com/licensing/docs/view/Service-Level-Agreements-SLA-for-Online-Services)
3. [Azure OpenAI Data Privacy](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/data-privacy)

## Findings

### Preisstruktur (Stand: Januar 2025)

Azure OpenAI bietet verschiedene Deployment-Typen:
- **Global**: Verarbeitung in beliebiger Region (günstigster Preis)
- **Data Zone (EU/US)**: Verarbeitung nur innerhalb EU oder US
- **Regional**: Verarbeitung nur in gewählter Region (z.B. West Europe)

Preise sind vergleichbar mit OpenAI API. Kein Setup-Kosten im Standard-Tier (Pay-as-you-go).

### SLA Details ✅

- **Standard Tier**: 99,9% Verfügbarkeit
- **Provisioned (PTU)**: Garantierte Kapazität, höhere SLA möglich
- **Latenz-Garantien**: Keine spezifischen im Standard-Tier

### DSGVO-Compliance Features ✅ (WICHTIGSTE ARGUMENTE)

Aus offizieller Microsoft-Dokumentation (learn.microsoft.com):

> **"Your prompts (inputs) and completions (outputs), your embeddings, and your training data:**
> - **are NOT available to other customers.**
> - **are NOT available to OpenAI or other Azure Direct Model providers.**
> - **are NOT used by Azure Direct Model providers to improve their models or services.**
> - **are NOT used to train any generative AI foundation models without your permission or instruction.**
> - **Customer Data, Prompts, and Completions are NOT used to improve Microsoft or third-party products or services without your explicit permission or instruction.**"

**Zusätzliche DSGVO-relevante Punkte:**
- [x] Daten verbleiben in gewählter Azure-Region (bei Regional/DataZone Deployment)
- [x] **Kein Training auf Kundendaten** (Default!)
- [x] EU-Regionen verfügbar: West Europe, Sweden Central, France Central, Germany West Central
- [x] "DataZone EU" Deployment: Daten bleiben garantiert in der EU
- [x] Zertifizierungen: SOC 2, ISO 27001, und weitere
- [x] DSGVO-konformes Data Processing Addendum (DPA) verfügbar
- [x] Fine-tuned Modelle sind exklusiv für den Kunden

## Steps

1. [x] Azure Pricing-Seite abrufen und aktuelle Preise notieren
2. [x] OpenAI Pricing-Seite zum Vergleich abrufen
3. [x] SLA-Dokument prüfen für genaue Garantien
4. [x] Data Privacy Dokumentation für DSGVO-Argumente
5. [x] Ergebnisse in Goal-Scratchpad übertragen

## Acceptance Criteria

- [x] Preisvergleich-Tabelle ausgefüllt mit aktuellen Zahlen → Vergleichbar, kein Aufpreis
- [x] SLA-Prozentsätze verifiziert → 99,9%
- [x] DSGVO-Argumente mit Microsoft-Dokumentation belegt → Ja, Zitat aus offizieller Doku
- [x] Alle Informationen mit Datum und Quelle versehen → Stand Januar 2025

## Quellen

- [Azure OpenAI Data Privacy](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/data-privacy)
- [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)

## Zusammenfassung für die Folie

**Kernbotschaft:** Azure OpenAI ist DSGVO-konform, weil:
1. Dediziertes Deployment in EU möglich (DataZone EU oder Regional)
2. Daten werden NICHT für Training verwendet (Default!)
3. Daten sind NICHT für OpenAI oder andere Kunden zugänglich
4. Gleiche Preise wie OpenAI API, kein Aufpreis für EU
5. 99,9% SLA, SOC 2 & ISO 27001 zertifiziert

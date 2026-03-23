/**
Dit zijn de user prompts die worden gebruikt om de LLM aan te sturen.
Generieke regels (rol, brongebruik, citaties, stijl, format) staan in de system prompt (api/app/prompts/system_prompt.py).
Deze prompts bevatten alleen taakspecifieke instructies en structuur.
 */

export type PromptType = 'executiveSummary' | 'topOrganizations' | 'topCollaborators' | 'recentPublications';

export const getPrompt = (type: PromptType, entityName: string): string => {
  const prompts: Record<PromptType, (name: string) => string> = {
    executiveSummary: (name) => `
Maak een feitelijke en samenhangende samenvatting van ${name} op basis van de aangeleverde context.

STRUCTUUR

**Profiel**
Beschrijf in 3 tot 5 zinnen de kern van het onderzoeksprofiel, inclusief vakgebieden, expertise en methoden.

**Onderzoeksfocus**
Beschrijf in 2 tot 4 zinnen welke onderzoeksvragen, thema's of maatschappelijke vraagstukken centraal staan.

**Publicaties en projecten**
Beschrijf in 3 tot 5 zinnen de meest relevante publicaties, projecten of onderzoekslijnen. Noem alleen concrete voorbeelden uit de context. Voeg bronverwijzingen toe waar relevant.

**Samenwerkingen en netwerk**
Beschrijf in 2 tot 4 zinnen de belangrijkste samenwerkingen met onderzoekers en organisaties. Benoem alleen relaties die expliciet uit de context blijken. Voeg bronverwijzingen toe waar relevant.

**Impact en toepassing**
Beschrijf in 2 tot 4 zinnen de wetenschappelijke, maatschappelijke of praktische betekenis van het werk, uitsluitend voor zover onderbouwd in de context.

INHOUDSREGELS
- Vermijd overlap tussen secties.
`,

    topOrganizations: (name) => `Vind de top 5 organisaties waarmee ${name} samenwerkt. Voor elke samenwerking:

1. Organisatienaam
2. Aard van de samenwerking (onderzoeksproject, co-autorschap publicaties, institutionele affiliatie, etc.)
3. Belangrijkste gezamenlijke publicaties of projecten (indien beschikbaar)
4. Impact of betekenis van de samenwerking
5. Jaren van actieve samenwerking

Presenteer bevindingen in een duidelijk, gestructureerd formaat met elke organisatie als apart item.
`,

  topCollaborators: (name) => `
Identificeer de 5 meest onderbouwde personen waarmee ${name} samenwerkt op basis van de aangeleverde context.

RANGSCHIKKING
Gebruik deze volgorde:
1. gezamenlijke publicaties
2. gedeelde projecten of onderzoekslijnen
3. herhaalde relatievermeldingen in de context
4. recente samenwerking

STRUCTUUR

**Top samenwerkingspartners**
1. **Persoon**
   - Type relatie:
   - Onderbouwing:
   - Belangrijkste gezamenlijke publicaties of projecten:
   - Periode:
   - Relevantie van de samenwerking:

INHOUDSREGELS
- Vermijd speculatie over de aard of sterkte van de relatie.
`,

    recentPublications: (name) => `
Selecteer de meest recente publicaties van ${name} op basis van de aangeleverde context.

INSTRUCTIE
- Sorteer strikt van meest recent naar minst recent.
- Gebruik publicatiejaar als primair selectiecriterium.
- Neem geen oudere publicatie op als een recentere expliciet beschikbare publicatie ontbreekt.
- Toon maximaal 8 publicaties.

GEEF DE OUTPUT EXACT IN DIT MARKDOWN-FORMAAT

**Recente publicaties**

- **Titel:** ...
  **Jaar:** ...
  **Type:** ...
  **Beschrijving:** ...
  **Auteurs:** ...
  **Bron:** ...

- **Titel:** ...
  **Jaar:** ...
  **Type:** ...
  **Beschrijving:** ...
  **Auteurs:** ...
  **Bron:** ...

FORMATREGELS
- Elk veld moet op een aparte regel staan.
- Laat een lege regel tussen publicaties.
- Gebruik geen doorlopende tekst op één regel.
`,
  };

  return prompts[type](entityName);
};

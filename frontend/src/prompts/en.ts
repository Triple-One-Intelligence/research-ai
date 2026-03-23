/**
 * AI Prompts for English language.
 * Generic rules (role, source handling, citations, style, format) are in the system prompt (api/app/prompts/system_prompt.py).
 * These prompts contain only task-specific instructions and structure.
 */

export type PromptType = 'executiveSummary' | 'topOrganizations' | 'topCollaborators' | 'recentPublications';

export const getPrompt = (type: PromptType, entityName: string): string => {
  const prompts: Record<PromptType, (name: string) => string> = {
    executiveSummary: (name) => `
Create a factual and coherent summary of ${name} based on the provided context.

STRUCTURE

**Profile**
In 3 to 5 sentences, describe the core research profile, including main fields, expertise, and methods.

**Research Focus**
In 2 to 4 sentences, describe the main research questions, themes, or societal challenges addressed.

**Publications and Projects**
In 3 to 5 sentences, describe the most relevant publications, projects, or research lines. Include only concrete examples supported by the context. Add source references where relevant.

**Collaborations and Network**
In 2 to 4 sentences, describe the main collaborations with researchers and organizations. Include only relationships explicitly supported by the context. Add source references where relevant.

**Impact and Application**
In 2 to 4 sentences, describe the scientific, societal, or practical relevance of the work, only where supported by the context.

CONTENT RULES
- Avoid overlap between sections.
`,

    topOrganizations: (name) => `Find the top 5 organizations that ${name} collaborates with. For each collaboration, provide:

1. Organization name
2. Nature of collaboration (research project, publication co-authorship, institutional affiliation, etc.)
3. Key collaborative publications or projects (if available)
4. Impact or significance of the collaboration
5. Years of active collaboration

Present findings in a clear, structured format with each organization as a separate item.
`,

  topCollaborators: (name) => `
Identify the 5 most well-supported people with whom ${name} collaborates based on the provided context.

RANKING
Use the following order:
1. co-authored publications
2. shared projects or research lines
3. repeated mentions of the relationship in the context
4. recent collaboration

STRUCTURE

**Top Collaboration Partners**
1. **Person**
   - Type of relationship:
   - Evidence:
   - Main shared publications or projects:
   - Period:
   - Relevance of the collaboration:

CONTENT RULES
- Avoid speculation about the nature or strength of the relationship.
`,

    recentPublications: (name) => `
Show all explicitly identified publications of ${name} based on the provided context, sorted from most recent to least recent.

STRUCTURE

**Recent Publications**

- **Title:** <title>
  **Year:** <year>
  **Type:** <type>
  **Description:** <short factual description in 1–2 sentences>
  **Authors:** <authors>
  **Source:** <source reference>

RULES
- Show all identified publications, unless there are more than 8. In that case, show the 8 most recent publications.
- Sort strictly from most recent to least recent.
- Use publication year as the leading sorting criterion.
- Put each field on a new line.
- Leave one blank line between publications.
`,
  };

  return prompts[type](entityName);
};

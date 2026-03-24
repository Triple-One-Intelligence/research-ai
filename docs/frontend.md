# Frontend Guide

React + TypeScript + Vite application.

## Component Tree

```
App
├── LeftPanel
│   └── EntitySearchBar
├── MiddlePanel (AI response display)
└── RightPanel
    └── CollapsibleCard
```

## State Flow

- **App holds**: `selectedEntity`, `responseText`, `isGenerating`, `debugInfo`
- **Entity selection**: User types in EntitySearchBar -> calls `searchEntities` API -> selects entity -> `setSelectedEntity`
- **On entity select**: RightPanel fetches connections via `fetchConnections` API
- **Prompt flow**: User types prompt in LeftPanel or clicks template button -> `onAsk` callback -> `handleGenerate` in App
- `POST /generate` handles all prompt requests
- If entity selected: `/generate` uses RAG context
- If no entity selected: `/generate` acts as general chat
- **SSE streaming**: `streamSSE` utility reads response body, parses SSE events, calls `onChunk` for tokens

## SSE Streaming Implementation

- `streamSSE()` in App.tsx handles `/generate`
- Uses fetch API with ReadableStream
- Parses `data:` lines, handles `[DONE]`, `{token}`, `{debug}`, `{error}` events
- Debug info displayed in collapsible RAG debug panel (visible when `LOGLEVEL=DEBUG` on backend)

## Internationalization (i18n)

- Uses `react-i18next`
- Two languages: English (`en`) and Dutch (`nl`)
- Language toggle in app header
- Translation keys in `leftPanel`, `header` namespaces

## API Client

- `api.ts` exports axios instance with `baseURL` from `VITE_API_URL` env var
- `searchEntities()`: transforms backend Person/Organization response to `EntitySuggestion[]`
- `fetchConnections()`: fetches entity connections

## Styling

- Dark header (`#1a1a2e`), light panels
- Three-column grid layout (`320px / 1fr / 300px`), responsive breakpoints at 1024px and 768px
- CSS in `App.css` (global layout, debug panel) and component-level CSS files (`LeftPanel.css`)
- RAG debug panel uses `.rag-debug` CSS classes

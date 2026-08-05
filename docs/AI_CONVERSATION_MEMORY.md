# Threaded AI Memory

## Behaviour

Each Vividity chatbox is an independent backend conversation.

- Full messages are stored in Frappe for the chat UI.
- The language model does **not** receive the raw transcript.
- Every successful answer returns a compact structured memory update.
- That memory summary is stored on the conversation and supplied on the next turn.
- A new chat creates a new conversation ID and starts with empty memory.
- Reloading the page restores recent conversations and their messages.

## Follow-up resolution

Example:

1. `What were vehicle sales for Jaguar and NEXA in the last two months?`
2. `Give me a pie chart of that.`

The second turn reuses the remembered resource, companies, date range, metric, and aggregation, while changing only the presentation to a pie chart.

## Control boundary

OpenAI controls read-only analytical interpretation:

- resource and field selection;
- metric and aggregation;
- company and date interpretation;
- table or chart selection;
- chart type, including pie;
- follow-up reference resolution;
- conversation summary updates.

The backend remains authoritative for:

- authentication identity;
- tenant and administrator scope;
- permitted database records;
- deterministic database reads;
- widget payload construction;
- conversation ownership.

OpenAI is never given unrestricted SQL or write access.

## Endpoints

```text
POST /api/method/dms.api.ai_agent.query
POST /api/method/dms.api.ai_agent.create_conversation
GET  /api/method/dms.api.ai_agent.list_conversations
POST /api/method/dms.api.ai_agent.get_conversation
POST /api/method/dms.api.ai_agent.archive_conversation
```

## Production requirement

The current demo can identify users through frontend headers. Before public production data is used, conversation ownership and tenant scope must be derived from authenticated Frappe sessions or signed tokens rather than client-controlled demo headers.

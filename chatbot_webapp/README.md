# Chatbot Webapp

Next.js chat interface for the platform. Connects to the chat service via the gateway for conversation management and real-time LLM streaming. Built on top of `@platform/auth-ui` for authentication.

## What It Does

- Full conversation management — create, rename, search, delete
- Real-time LLM streaming via WebSocket with REST fallback
- Markdown rendering in assistant messages (code blocks, tables, lists)
- Collapsible sidebar with search
- Dark/light theme support
- Mobile responsive
- Auth handled by `@platform/auth-ui` (login, register, MFA, token refresh)

```
┌──────────────────────────────────────────────────┐
│  Sidebar            │  Chat Area                  │
│                     │                             │
│  [+ New Chat]       │  ┌─────────────────────┐   │
│                     │  │ User: Hello          │   │
│  🔍 Search...       │  └─────────────────────┘   │
│                     │  ┌─────────────────────┐   │
│  > Conversation 1   │  │ Assistant: Hi there! │   │
│    Conversation 2   │  │ How can I help?      │   │
│    Conversation 3   │  └─────────────────────┘   │
│                     │                             │
│                     │  ┌─────────────────────┐   │
│                     │  │ Type a message...  ⬆ │   │
│                     │  └─────────────────────┘   │
└──────────────────────────────────────────────────┘
```

## Stack

- Next.js 16 with App Router + React 19
- Tailwind CSS v4 (CSS variable theming)
- `@platform/auth-ui` — auth pages, BFF handler, `useApiClient`, `useWSClient`
- `react-markdown` + `remark-gfm` — assistant message rendering
- Bun for package management

## Project Structure

```
chatbot_webapp/
├── package.json
├── src/
│   ├── app/
│   │   ├── page.tsx                          # Redirects to /chat or /login
│   │   ├── api/auth/[...path]/route.ts       # BFF auth handler (httpOnly cookies)
│   │   ├── (auth)/                           # Login, register, forgot-password (from auth-ui)
│   │   └── (app)/
│   │       ├── layout.tsx                    # App shell with sidebar + topbar
│   │       ├── chat/
│   │       │   ├── layout.tsx                # Full-height chat container
│   │       │   ├── page.tsx                  # Empty state → create conversation
│   │       │   └── [id]/page.tsx             # Active conversation
│   │       ├── dashboard/page.tsx
│   │       └── settings/page.tsx
│   ├── components/
│   │   ├── chat/
│   │   │   ├── chat-layout.tsx               # Two-panel: sidebar + chat area
│   │   │   ├── conversation-sidebar.tsx      # Search + conversation list + new button
│   │   │   ├── conversation-item.tsx         # Inline rename/delete actions
│   │   │   ├── chat-area.tsx                 # Orchestrates messages + input + streaming
│   │   │   ├── message-list.tsx              # Auto-scroll to bottom
│   │   │   ├── message-bubble.tsx            # User/assistant styling + markdown
│   │   │   ├── chat-input.tsx                # Auto-resize textarea, Enter=send, Shift+Enter=newline
│   │   │   ├── streaming-indicator.tsx       # Animated dots + stop button
│   │   │   ├── empty-state.tsx               # Welcome screen CTA
│   │   │   └── markdown-renderer.tsx         # ReactMarkdown + remark-gfm + styled blocks
│   │   ├── icons.tsx                         # SVG icon components
│   │   ├── app-shell.tsx, sidebar.tsx, topbar.tsx, user-menu.tsx
│   │   └── nav-item.tsx, mobile-sidebar.tsx
│   ├── hooks/
│   │   ├── use-conversations.ts              # CRUD with optimistic updates + debounced search
│   │   └── use-chat.ts                       # Message state + WebSocket streaming
│   ├── lib/
│   │   ├── chat-api.ts                       # Typed API functions for all chat REST endpoints
│   │   └── utils.ts                          # cn() helper
│   └── config/
│       └── navigation.ts                     # Sidebar nav items
```

## API Flow

Chat REST calls go through nginx → gateway → chat-service (gRPC). Auth calls go through the BFF (httpOnly cookie → gateway → auth-service).

```
Browser                Nginx :8880         Gateway :8080        Chat Service :50052
  │                      │                    │                       │
  │── GET /chat ────────▶│── proxy ──────────▶│ (webapp:3000)         │
  │                      │                    │                       │
  │── POST /api/v1/chat/─▶│── proxy ──────────▶│── gRPC ─────────────▶│
  │   conversations      │                    │                       │
  │                      │                    │                       │
  │── WS /ws/chat ──────▶│── WS upgrade ─────▶│── WS proxy ─────────▶│
  │                      │                    │                       │
  │── POST /api/auth/ ──▶│── proxy ──────────▶│ (BFF → gateway)      │
```

## Running

Part of the deploy stack:

```bash
cd deploy
./scripts/deploy.sh up all        # starts everything
./scripts/deploy.sh logs webapp   # tail logs
```

For local dev with hot reload:

```bash
cd deploy
./scripts/deploy.sh dev up        # all with hot reload
# or just frontend:
./scripts/deploy.sh dev up frontend
```

The app is served at `http://localhost:8880` (via nginx) or `http://localhost:3000` (direct, dev mode).

## Chat REST API

All endpoints require authentication (JWT via BFF cookie). Proxied through nginx/gateway to the chat service.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat/conversations` | Create conversation |
| `GET` | `/api/v1/chat/conversations` | List conversations (paginated) |
| `GET` | `/api/v1/chat/conversations/:id` | Get conversation + messages |
| `PUT` | `/api/v1/chat/conversations/:id` | Update title / system prompt |
| `DELETE` | `/api/v1/chat/conversations/:id` | Delete conversation |
| `POST` | `/api/v1/chat/conversations/:id/messages` | Send message (sync response) |
| `POST` | `/api/v1/chat/conversations/:id/stream` | Send message (SSE streaming) |
| `GET` | `/api/v1/chat/conversations/search?q=` | Full-text search |

## WebSocket Streaming

The `use-chat` hook connects via `useWSClient()` from `@platform/auth-ui`. Falls back to REST `sendMessage` if WebSocket isn't available.

```
1. Client sends: { action: "send", conversation_id, content }
2. Server streams: { type: "token", data: "Hello" } (one per token)
3. Server finishes: { type: "done", message: { full message object } }
```

## Environment

Configured via `deploy/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBAPP_DIR` | `chatbot_webapp` | Which app directory to build (set in .env) |
| `GATEWAY_URL` | `http://gateway:8080` | Gateway URL (Docker internal) |

The app itself needs no `.env` file — all config comes from the deploy stack.

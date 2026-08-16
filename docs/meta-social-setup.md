# Connect your Instagram + Facebook (Meta) — one-time setup

This is the only thing **you** have to do to pull your real IG/FB posts into Social Studio. It's ~10
minutes, and because the app runs in Meta **Development mode** with you as a tester, **no App Review is
required** — you connect your *own* accounts directly.

Everything in the app is already built, tested, and deployed (encrypted token storage, the OAuth flow,
the FB/IG post connectors, and the "your posts ground your drafts" behaviour). It just needs your Meta
app's credentials.

## Prerequisites
- Your **Instagram** account must be **Business** or **Creator** (IG app → Settings → switch account type).
- That IG account must be **linked to a Facebook Page** (IG app → Settings → Linked accounts / or via the
  Page's Meta Business Suite).
- You are an admin of the Facebook Page.

## Steps

1. **Create a Meta app** → https://developers.facebook.com/apps → *Create App* → type **Business**.
2. **Add products** (left sidebar → *Add product*): **Facebook Login** and **Instagram Graph API**.
3. **Keep the app in *Development* mode** (top toggle stays off/"In development"). Under **App roles →
   Roles**, add **yourself** as **Administrator** or **Tester**. Dev mode + your own role = full read
   access to your accounts with **no App Review**.
4. **Facebook Login → Settings → Valid OAuth Redirect URIs** — add exactly:
   - `https://cgrigoriadis.online/api/v1/social/callback`
   - (for local testing also `http://localhost:8880/api/v1/social/callback`)
5. **Grab your credentials**: *App settings → Basic* → **App ID** and **App Secret**.
6. **Put them in `deploy/.env`** (a `META_TOKEN_KEY` is already generated for you there — keep it secret
   and stable; rotating it makes existing stored tokens undecryptable):
   ```
   META_APP_ID=<your app id>
   META_APP_SECRET=<your app secret>
   META_OAUTH_REDIRECT=https://cgrigoriadis.online/api/v1/social/callback
   ```
7. **Redeploy** the agent service so it picks up the env:
   ```
   cd deploy && ./scripts/deploy.sh up backend agent-service
   ```
8. **Connect in the app**: Studio → **Sources** → **Connect Facebook / Instagram** → authorize at Meta →
   you're redirected back ("Connected ✓"). Your Page (and its linked IG) appear as connectable accounts;
   click **Add as source** and the app pulls your latest posts in the background and refreshes daily.

That's it — once connected, the assistant grounds your drafts in your *real* posts (voice, themes,
what you've covered), exactly as the sample-post demo showed.

## Notes / security
- The app requests **read-only** scopes only (`pages_show_list`, `pages_read_engagement`, `instagram_basic`)
  — it can read your posts, never publish.
- OAuth tokens are **encrypted at rest** (AES-256-GCM, key from `META_TOKEN_KEY`, bound to the row), never
  logged, and never sent to the browser.
- The OAuth callback authenticates via a short-lived **signed state** (CSRF-safe), not a login session.
- **LinkedIn** is not supported — its post API is effectively closed to third parties. For LinkedIn, paste
  a public post URL as a normal web source, or export and ask me to ingest it.

## Troubleshooting
- *"META_APP_ID not configured"* when you click Connect → step 6/7 not done (env not set or not redeployed).
- *Connected but no posts* → the IG account isn't Business/Creator, or isn't linked to the Page, or you
  aren't a Page admin. Fix the linkage (prereqs) and click **Refresh now** on the source.
- *"Reconnect" appears later* → the long-lived token lapsed; click Connect again (re-auth is instant).

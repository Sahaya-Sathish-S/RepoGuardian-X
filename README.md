# RepoGuardian X — Project Health Lab (MVP)

A cinematic, mobile-first Flask project health scanner with ZIP/source upload, public GitHub scanning, evidence-linked heuristic findings, a risk heatmap, repair roadmap, animated video/image backgrounds, optional Gemini/OpenRouter scan explanations, optional Supabase Google OAuth + private scan history, and Stripe Checkout scaffolding.

## What's included
- **Two supplied videos**: `static/assets/hero-future.mp4` in the hero backdrop and `static/assets/guardian-world.mp4` in the intelligence feature panel.
- **All four supplied images** are used in the visual gallery and supporting section backgrounds.
- **Scanner**: ZIP/source upload and public GitHub URL; files are inspected but never executed. ZIP path traversal checks and size caps are applied.
- **AI explanation endpoint**: `/api/ai/explain`; accepts a compact finding summary, not whole source files. Set `OPENROUTER_API_KEY` or `GEMINI_API_KEY`. OpenRouter takes precedence when both exist.
- **Supabase auth/history**: optional Google OAuth via Supabase JS; authenticated scan reports save to `public.scan_reports`. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
- **Subscriptions**: illustrative Pro/Studio pricing cards and Stripe Checkout Session creation are included. Set Stripe secret + recurring Price IDs. Checkout is not a complete paid-product system until a verified Stripe webhook updates `subscriptions`, entitlement checks are enforced server-side, and customer portal/cancellation/refunds are implemented.
- **Health check**: `/healthz`; public runtime configuration: `/api/config`.
- **Render**: `render.yaml` and Gunicorn start command included.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill values; export them in your shell or use your platform's env settings
python app.py
```
Open `http://127.0.0.1:5000`. Flask reads configuration from environment variables; it does not automatically load `.env` files.

## Supabase setup
1. Create a Supabase project.
2. Run `supabase_schema.sql` in SQL Editor.
3. Set `SUPABASE_URL` and the public anon/publishable key in deployment settings.
4. In Authentication → Providers, enable Google and enter Google OAuth client credentials.
5. Add the local and deployed site URLs to Supabase Auth URL Configuration / redirect allow-list.
6. Keep RLS enabled. Never put a Supabase service-role key in browser code.

## AI setup
Set one of `OPENROUTER_API_KEY` or `GEMINI_API_KEY` as a server environment variable. Optional model overrides: `OPENROUTER_MODEL`, `GEMINI_MODEL`. The frontend displays a helpful configuration message when neither is set. Provider requests are time-limited. AI output is untrusted advice and should be verified.

## Stripe setup — important
1. Create recurring monthly products/prices in Stripe.
2. Set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO_MONTHLY`, and `STRIPE_PRICE_STUDIO_MONTHLY` in deployment settings.
3. Before accepting real payments, implement and verify a Stripe webhook (signature validation) that upserts `subscriptions`, enforce active entitlement on all paid API routes, and add a billing portal/cancellation flow. The current checkout endpoint creates a hosted Checkout Session but does **not** verify payment or grant paid entitlements.

## Deploy to Render
Push this folder to a Git repository, create a Render Blueprint from `render.yaml`, and set optional credentials in the Render environment dashboard. Git must be installed on the host for GitHub URL scanning. The uploaded video assets are included in the repository and increase deploy size.

## Android Studio later
The UI uses responsive HTML/CSS/JS and same-origin Flask API routes, making it suitable for a WebView/Capacitor wrapper. For a real Android release, add a secure OAuth redirect/deep-link flow, network error states, app icons/splash, and Android-specific upload permissions. Do not embed server-side AI or Stripe secret keys in the Android app.

## Security / limitations
- Findings are rule-based heuristic signals, not confirmed vulnerabilities; health score is a prototype metric.
- Code is not executed. This is not a replacement for Semgrep, Bandit, Ruff, ESLint, dependency CVE scanning, CI tests, or expert security review.
- Public GitHub repositories only; no private repository token flow.
- Do not upload proprietary or sensitive source unless you have permission and understand your hosting provider's storage/logging policies.
- Production hardening still recommended: rate limiting, CSRF strategy for future cookie-based endpoints, upload quotas, structured audit logs, background jobs, a verified Stripe webhook, subscription enforcement, report retention/deletion, and automated tests.

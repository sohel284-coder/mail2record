# Connecting a mailbox — step by step

**IMAP is the default and only visible path** — it works with every provider
(Gmail, Outlook, Yahoo, corporate) using an app-specific password. Gmail OAuth
exists but is hidden unless you explicitly enable it (Option B, bottom).

---

## 0. One-time prep (once per install)

1. **Encryption key** — optional but recommended. Generate one:
   ```bash
   uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Add it to `.env`:
   ```
   EMAIL_CREDENTIALS_KEY=<the key you just generated>
   ```
   If you skip this, a key is derived from `SECRET_KEY` automatically (fine for
   local dev — just don't change `SECRET_KEY` afterward or you'll have to
   reconnect the mailbox).

2. **Start the app** and sign in:
   ```bash
   uv run python manage.py migrate
   uv run python manage.py runserver
   ```
   Open **http://localhost:8000/** — use `localhost`, not `127.0.0.1`
   (matters for the Gmail redirect later). Sign in.

3. Go to **Settings** (left sidebar) → the **Mailbox** card.

---

## Option A — Connect via IMAP  (any provider)

### A1. Get an app-specific password

You cannot use your normal login password — every provider requires an
"app password" (which also means 2-factor auth must be on).

| Provider | Where to generate it | IMAP host (auto-filled) |
|---|---|---|
| **Gmail** | myaccount.google.com → Security → 2-Step Verification → **App passwords** | `imap.gmail.com` : 993 |
| **Outlook.com / Hotmail** | account.microsoft.com/security → Advanced security → **App passwords** | `outlook.office365.com` : 993 |
| **Yahoo** | login.yahoo.com → Account security → **Generate app password** | `imap.mail.yahoo.com` : 993 |
| **iCloud** | appleid.apple.com → Sign-In & Security → **App-Specific Passwords** | `imap.mail.me.com` : 993 |
| Other / corporate | ask your mail admin for IMAP host + port | enter manually |

> **Microsoft 365 work/school accounts:** many tenants disable IMAP basic auth.
> If the connection test fails with an auth error, IMAP is blocked for that
> account and you'd need Gmail-style OAuth (not built yet).

### A2. Connect in the UI

1. Settings → Mailbox card → **Connect via IMAP →**
2. Fill in:
   - **Email address** — your full address. The IMAP host hint appears next to
     the "IMAP host" label as you type a known domain.
   - **App password** — the one from A1 (paste it, spaces don't matter for most)
   - **IMAP host / Port** — leave blank to auto-detect, or type them for a
     custom server
3. Click **Test & connect**.
   - It logs into the mailbox right then. If it fails you get the exact error
     (wrong password, host unreachable, IMAP disabled) and nothing is saved.
   - On success the page reloads and the Mailbox card shows Provider / Address /
     Host / "Last sync: never".

---

## Option B — Connect Gmail via OAuth

> **Hidden by default.** IMAP already covers Gmail. Only do this if you'd rather
> not use an app password. After the setup below, add `GMAIL_OAUTH_ENABLED=True`
> to `.env` and restart the server — the "Connect Gmail with OAuth" button then
> appears on the Settings Mailbox card.

### B1. Google Cloud setup (one time)

1. Go to **console.cloud.google.com** → create or pick a project.
2. **APIs & Services → Library** → search **Gmail API** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create
   - Fill app name + your email, Save and Continue through the screens
   - **Scopes** → Add → search `gmail.readonly` → select
     `.../auth/gmail.readonly` → Update
   - **Test users** → **Add users** → add the Google account whose mail you'll
     connect (required while the app is in "Testing" mode)
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Web application**
   - **Authorized redirect URIs → Add URI**:
     ```
     http://localhost:8000/emails/oauth/gmail/callback/
     ```
   - Create → **Download JSON**
5. Save that file as **`credentials/gmail_credentials.json`** (replace the
   existing one).

> The redirect URI must match exactly, including the trailing slash. If you run
> the server on a different port, update both the URI here and
> `GMAIL_OAUTH_REDIRECT_URI` in `.env`.

### B2. Connect in the UI

1. Settings → Mailbox card → **Connect Gmail**
2. You're sent to Google's consent screen → pick the account → "Continue"
   (you'll see an "unverified app" warning while it's in Testing mode — click
   **Advanced → Go to \<app\> (unsafe)**, that's your own app)
3. Grant read-only Gmail access → Google redirects back to Settings
4. A green "Gmail connected — you@gmail.com" banner appears; the Mailbox card
   fills in.

> Testing-mode refresh tokens expire after 7 days — if sync starts failing with
> an auth error after a week, just click **Connect Gmail** again. Publishing the
> consent screen (Google review) removes that limit.

---

## 3. Fetch email and verify

```bash
uv run python manage.py fetch_emails            # syncs every connected mailbox
uv run python manage.py fetch_emails --user <username>   # just yours
```

Expected:
```
Syncing you@gmail.com (gmail)…
  12 new (3 attachment(s)), 0 duplicate(s) skipped.
```

Then in the browser:
- **Inbox** — the fetched emails appear (newest first), status **Unprocessed**
- **Settings → Mailbox** — "Last sync" updates to a timestamp, green if OK
- The **sidebar** card shows the mailbox + "Last sync X min ago"

Re-running `fetch_emails` is safe — it skips anything already stored
(dedup on `message_id`).

To run it automatically: **Windows Task Scheduler** → new task → action
`...\uv.exe run python manage.py fetch_emails` in the project folder, trigger
every 5 minutes.

## 4. Test / disconnect

On the Settings Mailbox card once connected:
- **Test connection** — re-checks the login now, updates the status line
- **Disconnect** — themed confirm → removes the connection. Emails and records
  already collected stay; syncing just stops.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| IMAP: *"authentication failed"* | Wrong app password, or you used your login password. Regenerate the app password. Gmail: also confirm 2-Step Verification is on. |
| IMAP: *"couldn't work out the IMAP server"* | Uncommon domain — type the host + port manually (ask your mail admin). |
| IMAP: connects but 0 emails | The mailbox's INBOX is empty, or (rare) IMAP access is disabled in the provider's web settings. Gmail: Settings → Forwarding and POP/IMAP → Enable IMAP. |
| Gmail: *redirect_uri_mismatch* | The URI in Google Cloud must be exactly `http://localhost:8000/emails/oauth/gmail/callback/`. Also make sure you opened the app as `http://localhost:8000`, not `127.0.0.1`. |
| Gmail: *access_blocked / app not verified* | Add your Google account under **Test users** on the OAuth consent screen. |
| Gmail: sync fails after ~7 days | Testing-mode token expired — click **Connect Gmail** again, or publish the consent screen. |
| Nothing happens on `fetch_emails` | No mailbox connected, or `--user` doesn't match. Connect one in Settings first. |

## Offline test (no real mailbox)

To exercise the rest of the app without connecting a mailbox, create an email
directly — see `MANUAL_TESTING.md` §4 ("No mailbox / offline testing").

# Free AI offer: step-by-step guide

Give every API Tool user the AI assistant for a limited time, with your own API key.
Users see a notification with a **Claim** button; one click sets up the AI, and it stops by
itself on the end date.

```
 You                               GitHub                          Users' PCs
 ───                               ──────                          ──────────
 1. new DeepSeek key
 2. ~/ai-offer.json (with key) ──▶ secret gist  ◀──────────────┐
 3. offer in notifications.json ─▶ repo (main) ──▶ 🔔 "Free AI"  │
                                                   [Claim] ──────┘ downloads the config
                                                   ✓ AI ready until <date>
```

| File | Where | What it is |
|---|---|---|
| `ai-offer.example.json` | In the project (public) | Template only. The app never reads it. Must always say `PUT-YOUR-KEY-HERE`. |
| `~/ai-offer.json` | Your home folder → secret gist | The real config with the key. The app downloads this when a user clicks Claim. |
| `notifications.json` | In the project (public) | The offer message, which points to the gist's address. Never put the key here. |

> ⚠️ **Never put a key in a file inside the project folder.** The repo is public, so anyone can read
> it, and it stays in the git history even after you delete it. If that happens, delete the key in
> the DeepSeek dashboard at once.

---

## Current offer

| | |
|---|---|
| Offer id | `free-ai-2026-10` |
| Gist | `7487e0ab8bf092cacdba718a707cc73c` (file `ai-offer.json`) |
| Config URL | `https://gist.github.com/Thoeunsitha39/7487e0ab8bf092cacdba718a707cc73c/raw/ai-offer.json` |
| Provider / model | `deepseek` · `deepseek-v4-pro` |
| Ends | 2026-10-12 23:59 (+07:00) |
| Status (2026-10-06) | 🔴 Gist still has the **old leaked key** (`…f1a6`): replace it ([Update the gist](#update-the-gist)). 🟠 Offer hidden: `expires` in `notifications.json` is `2026-10-04`; set it to `2026-10-12` once the key is replaced. |
| To do on 2026-10-12 | Delete the key in the DeepSeek dashboard. |

Update this table whenever you start, change or end an offer.

---

## Start an offer

### Step 1: Create a key for the offer

1. Open **https://platform.deepseek.com** and log in.
2. Click **API keys** → **Create new API key**.
3. Name it, e.g. `API Tool free AI 2026-10`.
4. **Copy the key** (it starts with `sk-`). DeepSeek shows it only once.

💡 Use a separate key for each offer, and keep only a small balance on the account. The balance is
the most anyone can spend if the key is copied.

### Step 2: Make the config file

```bash
cd "/home/sitha/Tool/Pagination API"
cp ai-offer.example.json ~/ai-offer.json
nano ~/ai-offer.json
```

Edit `~/ai-offer.json` (home folder), **not** `ai-offer.example.json`:

```json
{
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com/anthropic",
  "model": "deepseek-v4-pro",
  "api_key": "sk-your-new-key",
  "expires_at": "2026-10-12T23:59:59+07:00"
}
```

| Field | Meaning |
|---|---|
| `provider` | AI provider id, as listed in AI settings: `deepseek`, `anthropic`, `openai`, `anthropic_compat`, … |
| `base_url` | API address. A URL ending in `/anthropic` uses the Anthropic format. |
| `model` | The model users get. |
| `api_key` | Your key for this offer. |
| `expires_at` | When the free AI stops on users' PCs. `+07:00` is Cambodia time. |

Save and close: **Ctrl+O**, **Enter**, **Ctrl+X**.

### Step 3: Upload it as a secret gist

```bash
gh gist create ~/ai-offer.json
```

Gists are secret by default. Never add `-p` / `--public`. (Older `gh` versions also accept
`--secret`; newer ones reject it with `unknown flag: --secret`.)

It prints the gist's link. Check that it says **secret gist**:

```
✓ Created secret gist ai-offer.json
https://gist.github.com/Thoeunsitha39/7487e0ab8bf092cacdba718a707cc73c
```

The last part is the **gist ID**. The address the app needs is the link plus `/raw/ai-offer.json`.
Both of these forms work; don't add a commit hash, so later edits to the gist are picked up:

```
https://gist.github.com/Thoeunsitha39/<gist-id>/raw/ai-offer.json
https://gist.githubusercontent.com/Thoeunsitha39/<gist-id>/raw/ai-offer.json
```

**Check it** the same way the Claim button reads it. The key is masked, so the output is safe to
share:

```bash
cd "/home/sitha/Tool/Pagination API"
venv/bin/python -m api_tool.ai.claim https://gist.github.com/Thoeunsitha39/<gist-id>/raw/ai-offer.json
```

```
OK    provider: deepseek
      base_url: https://api.deepseek.com/anthropic
      model:    deepseek-v4-pro
      key:      sk-a…9c3e        ← make sure these are the last 4 characters of your NEW key
      ends:     2026-10-12 23:59 (key expires in 6d 23h)
```

`FAIL …` means users would get the same error when they click Claim; see
[Troubleshooting](#troubleshooting).

(`curl -s <address>` also works, but prints the whole key. Only run it on your own PC.)

### Step 4: Add the offer to notifications.json

Add (or update) this entry in the `messages` list:

```json
{
  "id": "free-ai-2026-10",
  "date": "2026-10-05",
  "title": "Free AI for 7 days",
  "body": "Claim to use the AI assistant (DeepSeek V4 Pro) until 2026-10-12. No API key needed.",
  "popup": true,
  "expires": "2026-10-12",
  "min_version": "2.1",
  "claim_ai": { "config_url": "https://gist.github.com/Thoeunsitha39/<gist-id>/raw/ai-offer.json" }
}
```

⚠️ `expires` must be **today or later**, or nobody sees the offer. Keep the dates in `body`,
`expires` and the gist's `expires_at` the same.

| Field | Meaning |
|---|---|
| `id` | Unique per offer. A new id makes it a new notification, so everyone sees it again. |
| `popup` | `true` opens it as a popup window once, when the app starts. |
| `expires` | After this date the offer disappears from the bell. Match it to `expires_at`. |
| `min_version` | `2.1`: older apps can't claim, so they get the update notice first. |
| `claim_ai.config_url` | The raw gist address from Step 3. |

Then publish it:

```bash
git add notifications.json
git commit -m "Free AI offer until 2026-10-12"
git push origin main
```

If `git push` says `rejected … fetch first`, someone changed the repo on GitHub (for example in the
website editor). Run `git pull`, then `git push origin main` again.

No new app release is needed.

### Step 5: Check it

1. Open API Tool and click 🔔 → **Check now**. GitHub can take up to 5 minutes to serve the change.
2. You should see **Free AI for 7 days** with a **✨ Claim** button.
3. Click **Claim**: the app says **✓ The AI assistant is ready — until …**.
4. Open the **AI** page and ask something.

---

## What users see

1. 🔔 shows a red count and a popup: **Free AI for 7 days**, with **[Claim]** and **[Later]**.
   - The app checks at startup and every 6 hours; **Check now** checks immediately.
2. They click **Claim**.
   - If they already use their own AI key, the app asks before replacing it.
3. The app downloads the config in the background and sets up the AI. A message says
   **✓ The AI assistant is ready — until 2026-10-12 23:59**, with an **Open AI** button.
4. The bell list shows **✓ Claimed — AI ready until …**, and the AI page shows
   `DeepSeek · deepseek-v4-pro · key expires in …`.
5. On the end date the key is removed from their PC and the AI page says
   **The free AI ended on … Enter your own API key to keep chatting.**

---

## End an offer

On the end date (or earlier, to stop it now):

1. **Delete the key** in the DeepSeek dashboard (**API keys** → **Delete**).
   This is what really stops it: the app's end date only affects the app, and anyone who copied
   the key could keep using it otherwise.
2. Optional: delete the gist with `gh gist delete <gist-id>`.

The offer message disappears from the bell by itself after its `expires` date.

## Update the gist

Edit your local copy, then send it to the same gist. The address stays the same, so
`notifications.json` doesn't change:

```bash
nano ~/ai-offer.json                                  # change the key, model or date
gh gist edit <gist-id> ~/ai-offer.json                # upload it to the same gist
venv/bin/python -m api_tool.ai.claim <config-url>     # check: key ends with the new 4 characters
```

If your `gh` version opens an editor instead of uploading the file, paste the new content there
and save. GitHub can take a few minutes to serve the new version.

## Change a running offer

| To… | Do this |
|---|---|
| Extend it | [Update the gist](#update-the-gist) with a later `expires_at`. Also update `expires` and the body in `notifications.json`. Users who already claimed keep the old date until they claim again. |
| Change the model | Update `model` in the gist. Users who claim after that get the new model. |
| Replace the key | Create a new key, [update the gist](#update-the-gist), check it, then delete the old key. Users who claimed before have to claim again. |
| Run a new offer | Repeat Steps 1–4 with a new key and a **new** `id`. |

---

## Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `Couldn't set up the free AI: HTTP Error 404: Not Found` | `config_url` is wrong (e.g. still the example `abc123`), or the gist was deleted. | Use your gist ID with `/raw/ai-offer.json`; test it with `python -m api_tool.ai.claim`. |
| `Couldn't set up the free AI: This free AI offer has ended` | `expires_at` in the gist is in the past. | Set a later date in the gist. |
| `The offer config has no "api_key"` (or `model`, `expires_at`) | A field is missing in the gist. | Compare with `ai-offer.example.json`. |
| `Unknown AI provider "…"` | `provider` is misspelled. | Use an id from the table in Step 2. |
| Claim works, but the AI answers with an auth error | The key was deleted or is wrong. | Put a valid key in the gist; users click **Claim** again. |
| Users don't see the offer | They're on 2.0, the offer's `expires` date is in the past, or GitHub is still serving the old file. | Ask them to update; set `expires` to the end date; wait up to 5 minutes, then **Check now**. |
| `unknown flag: --secret` | Newer `gh` versions make gists secret by default. | Run `gh gist create ~/ai-offer.json` (without `--secret`). |
| The checker shows the wrong key ending | The gist still has an old key, or GitHub hasn't served the update yet. | [Update the gist](#update-the-gist); wait a few minutes and check again. |
| A key ended up in `ai-offer.example.json` or another project file | The wrong file was edited. | Delete that key in DeepSeek **now**, make a new one, and put `PUT-YOUR-KEY-HERE` back. |

## Security notes

- Anyone who can download the config can copy the key. A secret gist is unlisted, not private,
  and its address is in the public `notifications.json`.
- The end date is enforced by the app only. Deleting the key in the DeepSeek dashboard is the real
  end.
- Keep the account balance small, use a new key for each offer, and delete it when the offer ends.

Code: `api_tool/ai/claim.py` (reads the config), `api_tool/ui/main_window/notifications.py`
(Claim button and setup), `api_tool/core/notifications.py` (the `claim_ai` field).

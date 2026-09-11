# Omni Cookie Sync Setup

Short guide for extracting fresh Gemini auth data and applying it to `omni-proxy`.

## What this extension exports

The extension reads the current signed-in Gemini session and exports:

- Google session cookies
- `SAPISID`
- `SNlM0e` (`xsrf_token`)
- `cfb2h` (`gemini_bl`)
- `auth_user`

It saves them locally as `omni-auth.json`.

## Install and export

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `cookie-sync` folder
5. Open [https://gemini.google.com/app](https://gemini.google.com/app)
6. Sign in and refresh the page
7. Open the extension and click **Inspect session**
8. Confirm the session looks ready
9. Click **Export omni-auth.json**

Expected ready state:

```text
XSRF / SNlM0e: present
gemini_bl / cfb2h: present
Session and XSRF are ready for export.
```

## Apply it in `omni-proxy`

Move the exported file into the project:

```bash
cd /path/to/omni-proxy

WIN_HOME=$(wslpath "$(powershell.exe -NoProfile -Command '[Environment]::GetFolderPath("UserProfile")' | tr -d '\r')")
cp "$WIN_HOME/Downloads/omni-auth.json" ./omni-auth.json
chmod 600 omni-auth.json
```

Update `config.json`:

```bash
cd /path/to/omni-proxy

AUTH_FILE="$(pwd)/omni-auth.json"
tmp=$(mktemp)

jq \
  --arg auth_file "$AUTH_FILE" \
  --slurpfile auth "$AUTH_FILE" \
  '
    .cookie_file = $auth_file
    | .auth_user = $auth[0].auth_user
    | .xsrf_token = $auth[0].xsrf_token
    | if (($auth[0].gemini_bl // "") | length) > 0
      then .gemini_bl = $auth[0].gemini_bl
      else .
      end
  ' config.json > "$tmp" &&
mv "$tmp" config.json

chmod 600 config.json
```

Quick check:

```bash
jq '{
  cookie_file,
  auth_user,
  xsrf_token_set: ((.xsrf_token // "") | length > 0),
  gemini_bl_set: ((.gemini_bl // "") | length > 0)
}' config.json
```

## Restart and test

```bash
systemctl --user restart omni-proxy
```

```bash
curl -sS http://127.0.0.1:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "gemini-3.1-pro",
    "messages": [
      {
        "role": "user",
        "content": "Reply exactly with: authenticated-ok"
      }
    ]
  }' | jq
```

## Keep it secret

`omni-auth.json` contains real sessions. Do not share it, print it, or commit it to Git.

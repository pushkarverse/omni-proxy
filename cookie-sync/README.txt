Omni-Proxy Cookie Sync v1.0

Purpose:
- Read cookies for the current Google/Gemini session.
- Extract the XSRF token named SNlM0e from the Gemini page.
- Extract gemini_bl from cfb2h or from page requests when available.
- Export `omni-auth.json` locally only.

Installation:
1. Open `chrome://extensions`
2. Enable Developer mode
3. Click Load unpacked
4. Select this folder
5. Open `https://gemini.google.com/app`, sign in, and refresh the page
6. Click Inspect session
7. Click Export `omni-auth.json`

Security:
The generated file represents real sessions and must be treated as secret. Do not send it, print it, or commit it to Git.

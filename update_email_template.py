"""
Fix Supabase email to send OTP code ({{ .Token }}) instead of confirmation link ({{ .ConfirmationURL }})
Uses Supabase Management API - requires SUPABASE_ACCESS_TOKEN (from https://supabase.com/dashboard/account/tokens)
and project ref (fhjdckszmaifixbhycof).

Run:
  SUPABASE_ACCESS_TOKEN=sbp_xxx python update_email_template.py
or
  python update_email_template.py --token sbp_xxx --project-ref fhjdckszmaifixbhycof

This will PATCH the auth config to use OTP for:
- confirm_signup (was link, now OTP)
- magiclink (already OTP, ensure)
- recovery, etc. kept as link but you can change.

See https://supabase.com/docs/guides/auth/auth-email-templates
"""
import os, sys, json, httpx
from pathlib import Path

PROJECT_REF = os.getenv("PROJECT_REF", "fhjdckszmaifixbhycof")
TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN") or os.getenv("SB_TOKEN")

# Allow CLI args
for i, a in enumerate(sys.argv):
    if a == "--token" and i+1 < len(sys.argv):
        TOKEN = sys.argv[i+1]
    if a == "--project-ref" and i+1 < len(sys.argv):
        PROJECT_REF = sys.argv[i+1]
    if a.startswith("sbp_"):
        TOKEN = a

if not TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN not set")
    print("Get it from https://supabase.com/dashboard/account/tokens -> Create new token (read/write for project)")
    print("Then run: SUPABASE_ACCESS_TOKEN=sbp_xxx python update_email_template.py")
    sys.exit(1)

# New OTP-based templates
# For confirm_signup, use {{ .Token }} instead of {{ .ConfirmationURL }}
otp_confirm_content = """<h2>Confirm your signup</h2><p>Your OTP code is:</p><p style="font-size:24px; letter-spacing:0.3em; font-weight:700; background:#111214; border:1px solid #242629; border-radius:12px; padding:12px 16px; text-align:center; color:#F5F5F5;">{{ .Token }}</p><p>Enter this code in the skilly app to verify your email. Expires in 10 minutes.</p><p style="color:#6F7377; font-size:11px;">If you didn't request this, ignore.</p>"""

magic_link_content = """<h2>Your OTP code</h2><p>Your code is:</p><p style="font-size:24px; letter-spacing:0.3em; font-weight:700; background:#111214; border:1px solid #242629; border-radius:12px; padding:12px 16px; text-align:center; color:#F5F5F5;">{{ .Token }}</p><p>Enter this code to sign in. Expires shortly. If you didn't request, ignore.</p>"""

payload = {
    "mailer_subjects_confirmation": "Your skilly OTP code is {{ .Token }}",
    "mailer_templates_confirmation_content": otp_confirm_content,
    "mailer_subjects_magic_link": "Your skilly OTP code is {{ .Token }}",
    "mailer_templates_magic_link_content": magic_link_content,
    # Keep recovery as link (user expects link for password reset) but you can also make it OTP:
    # "mailer_subjects_recovery": "Reset your password - {{ .Token }}",
    # "mailer_templates_recovery_content": "<h2>Reset code</h2><p>{{ .Token }}</p>",
}

url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth"
print(f"PATCH {url}")
print("Payload keys:", list(payload.keys()))
try:
    r = httpx.patch(url, headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}, json=payload, timeout=30)
    print("Status:", r.status_code)
    print(r.text[:2000])
    if r.status_code == 200:
        print("\n✅ Email templates updated to OTP! New signups will now receive 6-digit code, not link.")
        print("Test: sign up with a new email and check inbox for OTP code.")
    else:
        print("\n❌ Failed. Check token has write access and project ref is correct.")
        print("Project ref from SUPABASE_URL: fhjdckszmaifixbhycof")
except Exception as e:
    print("Error:", e)
    sys.exit(1)

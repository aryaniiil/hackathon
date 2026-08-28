import httpx, json, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(r"D:\Hackathon\backend\.env"))
url = os.getenv("SUPABASE_URL")
anon = os.getenv("SUPABASE_ANON_KEY")
print("url", url)
print("anon", anon[:20])
import random, string
email = f"sbtest{random.randint(1000,9999)}@example.com"
password = "test1234"
print("email", email)
# try Supabase signUp via REST
headers = {"apikey": anon, "Authorization": f"Bearer {anon}", "Content-Type": "application/json"}
data = {"email": email, "password": password, "data": {"full_name": "SB Test"}}
r = httpx.post(f"{url}/auth/v1/signup", headers=headers, json=data, timeout=10)
print("signup", r.status_code, r.text[:500])
if r.status_code == 200:
    j = r.json()
    print("user id", j.get("user", {}).get("id"))
    # try verifyOtp - but we need actual OTP from email, which we don't have; for demo we can try to use the OTP from backend? But supabase OTP is separate.
    # Try signInWithOtp to get OTP
    r2 = httpx.post(f"{url}/auth/v1/otp", headers=headers, json={"email": email, "create_user": False}, timeout=10)
    print("otp", r2.status_code, r2.text[:300])

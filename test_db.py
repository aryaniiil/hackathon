import pathlib, sys
sys.path.insert(0, r"D:\Hackathon\backend")
from app.db import init_db
init_db()
print('init done')
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv(Path(r"D:\Hackathon\backend\.env"))
url = os.getenv("DATABASE_URL")
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute("SELECT to_regclass('public.test_history')")
print(cur.fetchone())
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", ('test_history',))
print(cur.fetchall())
cur.close(); conn.close()

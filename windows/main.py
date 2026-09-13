import csv, json, os, queue, sqlite3, threading, time, shutil
from datetime import datetime
from urllib import request
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

APP = "GSMS SMS v1.0"
SCHOOL = "Govt. Higher Secondary School Utror Swat"
# Use plain strings here instead of pathlib.Path objects. This keeps the
# application compatible with older Python/Windows combinations, including
# Windows 7, and avoids the WindowsPath TypeError seen in the previous build.
APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
DB = os.path.join(APPDATA, "GSMS_SMS_v1", "gsms.db")
if not os.path.isdir(os.path.dirname(DB)):
    os.makedirs(os.path.dirname(DB))
DEFAULT_PASSWORD = "1234"
MAX_15, MAX_HOUR, MAX_DAY = 150, 250, 750

class DBStore:
    def __init__(self):
        self.db = sqlite3.connect(DB, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT,group_name TEXT,kind TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT,designation TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS sent_log(id INTEGER PRIMARY KEY AUTOINCREMENT,phone TEXT,message TEXT,created_at TEXT,status TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS templates(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,message TEXT)")
        self._migrate_contacts()
        self.db.commit()
        if self.get("password") is None: self.set("password", DEFAULT_PASSWORD)
        if self.get("android_url") is None: self.set("android_url", "http://192.168.1.100:8765")
        if self.get("token") is None: self.set("token", "")

    def _migrate_contacts(self):
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(contacts)").fetchall()}
        for col in ("roll_no", "father_name", "class_name", "section"):
            if col not in cols:
                self.db.execute("ALTER TABLE contacts ADD COLUMN %s TEXT" % col)

    def get(self, k):
        row = self.db.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
        return row[0] if row else None
    def set(self, k, v):
        with self.lock:
            # INSERT OR REPLACE is intentionally used instead of SQLite UPSERT.
            # Older SQLite versions bundled with Windows 7-compatible Python
            # do not understand "ON CONFLICT ... DO UPDATE" and fail with
            # "near ON: syntax error".
            self.db.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (k, v))
            self.db.commit()
    def contacts(self):
        return self.db.execute("SELECT id,roll_no,name,father_name,class_name,section,phone,group_name,kind FROM contacts ORDER BY id").fetchall()
    def add_contact(self, roll, name, father, cls, section, phone):
        with self.lock:
            self.db.execute("INSERT INTO contacts(roll_no,name,father_name,class_name,section,phone,group_name,kind) VALUES(?,?,?,?,?,?,?,?)", (roll,name,father,cls,section,phone,cls,"Student/Parent"))
            self.db.commit()
    def update_contact(self, row_id, roll, name, father, cls, section, phone):
        with self.lock:
            self.db.execute("UPDATE contacts SET roll_no=?,name=?,father_name=?,class_name=?,section=?,phone=?,group_name=? WHERE id=?", (roll,name,father,cls,section,phone,cls,row_id))
            self.db.commit()
    def delete_contacts(self, ids):
        with self.lock:
            self.db.executemany("DELETE FROM contacts WHERE id=?", [(i,) for i in ids])
            self.db.commit()
    def logs(self): return self.db.execute("SELECT id,phone,message,created_at,status FROM sent_log ORDER BY id DESC").fetchall()
    def log(self,p,m,s):
        with self.lock:
            self.db.execute("INSERT INTO sent_log(phone,message,created_at,status) VALUES(?,?,?,?)", (p,m,datetime.now().isoformat(timespec="seconds"),s)); self.db.commit()
    def backup(self,target):
        with self.lock:
            self.db.commit(); shutil.copy2(DB,target)
    def restore(self,source):
        with self.lock:
            self.db.close(); shutil.copy2(source,DB); self.db=sqlite3.connect(DB,check_same_thread=False); self._migrate_contacts(); self.db.commit()

class RateLimiter:
    def __init__(self): self.times=[]; self.lock=threading.Lock()
    def can_send(self):
        now=time.time()
        with self.lock:
            self.times=[t for t in self.times if now-t<86400]
            return sum(now-t<900 for t in self.times)<MAX_15 and sum(now-t<3600 for t in self.times)<MAX_HOUR and len(self.times)<MAX_DAY
    def wait_seconds(self):
        now=time.time()
        with self.lock:
            self.times=[t for t in self.times if now-t<86400]; waits=[]
            recent15=[t for t in self.times if now-t<900]
            recent60=[t for t in self.times if now-t<3600]
            if len(recent15)>=MAX_15: waits.append(900-(now-min(recent15)))
            if len(recent60)>=MAX_HOUR: waits.append(3600-(now-min(recent60)))
            if len(self.times)>=MAX_DAY: waits.append(86400-(now-min(self.times)))
            return max(waits) if waits else 0
    def mark(self):
        with self.lock: self.times.append(time.time())

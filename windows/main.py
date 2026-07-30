import csv, json, os, queue, sqlite3, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from urllib import request, error
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from openpyxl import load_workbook

APP = "GSMS SMS v1.0"
DB = Path(os.getenv("APPDATA", Path.home())) / "GSMS_SMS_v1" / "gsms.db"
DB.parent.mkdir(parents=True, exist_ok=True)
DEFAULT_PASSWORD = "1234"
MAX_15 = 150
MAX_HOUR = 250
MAX_DAY = 750

class DBStore:
    def __init__(self):
        self.db = sqlite3.connect(DB, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT,group_name TEXT,kind TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS sent_log(id INTEGER PRIMARY KEY AUTOINCREMENT,phone TEXT,message TEXT,created_at TEXT,status TEXT)")
        self.db.commit()
        if self.get("password") is None: self.set("password", DEFAULT_PASSWORD)
        if self.get("android_url") is None: self.set("android_url", "http://192.168.1.100:8765")
        if self.get("token") is None: self.set("token", "")
    def get(self,k):
        row=self.db.execute("SELECT v FROM settings WHERE k=?",(k,)).fetchone(); return row[0] if row else None
    def set(self,k,v):
        with self.lock:
            self.db.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(k,v)); self.db.commit()
    def add_contact(self,name,phone,group_name,kind):
        with self.lock:
            self.db.execute("INSERT INTO contacts(name,phone,group_name,kind) VALUES(?,?,?,?)",(name,phone,group_name,kind)); self.db.commit()
    def contacts(self): return self.db.execute("SELECT id,name,phone,group_name,kind FROM contacts ORDER BY name").fetchall()
    def log(self,phone,message,status):
        with self.lock:
            self.db.execute("INSERT INTO sent_log(phone,message,created_at,status) VALUES(?,?,?,?)",(phone,message,datetime.now().isoformat(timespec='seconds'),status)); self.db.commit()

class RateLimiter:
    def __init__(self): self.times=[]; self.lock=threading.Lock()
    def can_send(self):
        now=time.time()
        with self.lock:
            self.times=[t for t in self.times if now-t < 86400]
            c15=sum(now-t<900 for t in self.times); ch=sum(now-t<3600 for t in self.times); cd=len(self.times)
            return c15<MAX_15 and ch<MAX_HOUR and cd<MAX_DAY
    def wait_seconds(self):
        now=time.time()
        with self.lock:
            self.times=[t for t in self.times if now-t < 86400]
            waits=[]
            if sum(now-t<900 for t in self.times)>=MAX_15:
                waits.append(900-(now-min(t for t in self.times if now-t<900)))
            if sum(now-t<3600 for t in self.times)>=MAX_HOUR:
                waits.append(3600-(now-min(t for t in self.times if now-t<3600)))
            if len(self.times)>=MAX_DAY: waits.append(86400-(now-min(self.times)))
            return max(waits) if waits else 0
    def mark(self):
        with self.lock: self.times.append(time.time())

class App:
    def __init__(self,root):
        self.root=root; self.store=DBStore(); self.limiter=RateLimiter(); self.stop_event=threading.Event(); self.pause_event=threading.Event(); self.pause_event.set(); self.q=queue.Queue(); self.logged=False
        self.root.title(APP); self.root.geometry("980x680"); self.build_login()
    def build_login(self):
        for w in self.root.winfo_children(): w.destroy()
        f=ttk.Frame(self.root,padding=30); f.pack(expand=True)
        ttk.Label(f,text="GSMS SMS v1.0",font=("Segoe UI",24,"bold")).pack(pady=8)
        ttk.Label(f,text="GHSS Utror Swat",font=("Segoe UI",14)).pack(pady=4)
        ttk.Label(f,text="Principal login").pack(pady=(20,5)); pw=ttk.Entry(f,show="*"); pw.pack(); pw.focus()
        ttk.Button(f,text="Login",command=lambda:self.login(pw.get())).pack(pady=15)
        ttk.Label(f,text="First login default: 1234 — change it from Settings.",foreground="#555").pack()
    def login(self,pw):
        if pw==self.store.get("password"): self.logged=True; self.build_main()
        else: messagebox.showerror(APP,"Incorrect password.")
    def build_main(self):
        for w in self.root.winfo_children(): w.destroy()
        top=ttk.Frame(self.root,padding=10); top.pack(fill="x")
        ttk.Label(top,text=APP,font=("Segoe UI",18,"bold")).pack(side="left")
        ttk.Button(top,text="Settings",command=self.settings).pack(side="right")
        ttk.Button(top,text="Import Excel/CSV",command=self.import_contacts).pack(side="right",padx=5)
        ttk.Button(top,text="Change Password",command=self.change_password).pack(side="right",padx=5)
        body=ttk.Panedwindow(self.root,orient="horizontal"); body.pack(fill="both",expand=True,padx=10,pady=5)
        left=ttk.Frame(body,padding=5); right=ttk.Frame(body,padding=5); body.add(left,weight=1); body.add(right,weight=1)
        ttk.Label(left,text="Contacts",font=("Segoe UI",12,"bold")).pack(anchor="w")
        self.tree=ttk.Treeview(left,columns=("id","name","phone","group","kind"),show="headings",selectmode="extended")
        for c,t,w in [("id","ID",45),("name","Name",150),("phone","Phone",130),("group","Group",100),("kind","Type",80)]: self.tree.heading(c,text=t); self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True,pady=5); self.refresh_contacts()
        ttk.Button(left,text="Select All",command=self.select_all).pack(side="left")
        ttk.Button(left,text="Queue Selected",command=self.queue_selected).pack(side="right")
        ttk.Label(right,text="SMS Message",font=("Segoe UI",12,"bold")).pack(anchor="w")
        self.msg=tk.Text(right,height=10,wrap="word"); self.msg.pack(fill="x",pady=5)
        ctl=ttk.Frame(right); ctl.pack(fill="x",pady=5)
        ttk.Button(ctl,text="Pause",command=lambda:self.pause_event.clear()).pack(side="left")
        ttk.Button(ctl,text="Resume",command=lambda:self.pause_event.set()).pack(side="left",padx=5)
        ttk.Button(ctl,text="Clear Queue",command=self.clear_queue).pack(side="left")
        self.status=tk.StringVar(value="Ready")
        ttk.Label(right,textvariable=self.status,wraplength=420).pack(anchor="w",pady=10)
        self.queue_view=tk.Listbox(right,height=14); self.queue_view.pack(fill="both",expand=True)
        ttk.Label(right,text="Safety limits: 150/15 min • 250/hour • 750/24 hours",foreground="#7a1f1f").pack(anchor="w",pady=5)
        threading.Thread(target=self.worker,daemon=True).start()
    def refresh_contacts(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        for row in self.store.contacts(): self.tree.insert("","end",values=row)
    def select_all(self): self.tree.selection_set(self.tree.get_children())
    def queue_selected(self):
        msg=self.msg.get("1.0","end").strip()
        if not msg: return messagebox.showwarning(APP,"Enter the SMS message first.")
        rows=[self.tree.item(i,"values") for i in self.tree.selection()]
        if not rows: return messagebox.showwarning(APP,"Select at least one contact.")
        for row in rows: self.q.put((row[2],msg,row[1])); self.queue_view.insert("end",f"Queued: {row[1]} — {row[2]}")
        self.status.set(f"Queued {len(rows)} SMS(s). Sending is controlled by safety limits.")
    def clear_queue(self):
        while not self.q.empty():
            try:self.q.get_nowait(); self.q.task_done()
            except queue.Empty:break
        self.queue_view.delete(0,"end"); self.status.set("Queue cleared.")
    def worker(self):
        while True:
            phone,msg,name=self.q.get()
            try:
                self.pause_event.wait()
                while not self.limiter.can_send():
                    wait=self.limiter.wait_seconds(); self.status_set(f"Safety limit reached. Waiting about {int(wait//60)+1} minute(s).")
                    time.sleep(min(max(wait,1),60)); self.pause_event.wait()
                ok,detail=self.send_android(phone,msg)
                self.store.log(phone,msg,"accepted" if ok else "failed")
                if ok: self.limiter.mark(); self.status_set(f"Accepted for sending: {name} ({phone})")
                else: self.status_set(f"Failed: {name} ({phone}) — {detail}")
            finally:
                try:self.q.task_done()
                except:pass
    def status_set(self,text): self.root.after(0,lambda:self.status.set(text))
    def send_android(self,phone,msg):
        base=self.store.get("android_url").rstrip("/"); token=self.store.get("token") or ""
        data=json.dumps({"phone":phone,"message":msg}).encode()
        req=request.Request(base+"/send",data=data,method="POST",headers={"Content-Type":"application/json","X-GSMS-Token":token})
        try:
            with request.urlopen(req,timeout=12) as r: return r.status==200,r.read().decode(errors="replace")
        except Exception as e:return False,str(e)
    def settings(self):
        win=tk.Toplevel(self.root); win.title("GSMS Settings"); win.geometry("560x240"); f=ttk.Frame(win,padding=20); f.pack(fill="both",expand=True)
        ttk.Label(f,text="Android phone IP / URL (same Wi-Fi)").grid(row=0,column=0,sticky="w",pady=5); url=ttk.Entry(f,width=48); url.grid(row=0,column=1,pady=5); url.insert(0,self.store.get("android_url"))
        ttk.Label(f,text="Pairing token").grid(row=1,column=0,sticky="w",pady=5); tok=ttk.Entry(f,width=48); tok.grid(row=1,column=1,pady=5); tok.insert(0,self.store.get("token"))
        def save(): self.store.set("android_url",url.get().strip()); self.store.set("token",tok.get().strip()); win.destroy(); messagebox.showinfo(APP,"Settings saved.")
        ttk.Button(f,text="Save",command=save).grid(row=2,column=1,sticky="e",pady=15)
    def change_password(self):
        old=simpledialog.askstring(APP,"Current password",show="*");
        if old!=self.store.get("password"): return messagebox.showerror(APP,"Current password is incorrect.")
        new=simpledialog.askstring(APP,"New password",show="*");
        if new and len(new)>=4: self.store.set("password",new); messagebox.showinfo(APP,"Password changed.")
        else: messagebox.showwarning(APP,"Password must contain at least 4 characters.")
    def import_contacts(self):
        path=filedialog.askopenfilename(filetypes=[("Excel/CSV","*.xlsx *.xlsm *.csv"),("All files","*.*")])
        if not path:return
        try:
            rows=[]
            if path.lower().endswith(".csv"):
                with open(path,newline="",encoding="utf-8-sig") as f: rows=list(csv.reader(f))
            else:
                ws=load_workbook(path,read_only=True,data_only=True).active; rows=[list(r) for r in ws.iter_rows(values_only=True)]
            if not rows: raise ValueError("No rows found")
            header=[str(x or "").strip().lower() for x in rows[0]]
            def idx(names,default):
                for n in names:
                    if n in header:return header.index(n)
                return default
            ni=idx(["name","student name","student","parent name"],0); pi=idx(["phone","mobile","mobile no","phone number","parent phone"],1); gi=idx(["group","class","section"],2 if len(header)>2 else 0); ki=idx(["type","kind","category"],3 if len(header)>3 else 0)
            count=0
            for r in rows[1:]:
                if len(r)<=max(ni,pi):continue
                name=str(r[ni] or "").strip(); phone=str(r[pi] or "").strip()
                if not phone:continue
                group=str(r[gi] or "") if gi<len(r) else ""; kind=str(r[ki] or "Student/Parent") if ki<len(r) else "Student/Parent"
                self.store.add_contact(name,phone,group,kind); count+=1
            self.refresh_contacts(); messagebox.showinfo(APP,f"Imported {count} contact(s).")
        except Exception as e: messagebox.showerror(APP,f"Import failed: {e}")

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()

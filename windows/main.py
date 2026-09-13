import csv, json, os, queue, sqlite3, threading, time, shutil
from datetime import datetime
from urllib import request
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

APP = "GSMS SMS v1.0"
SCHOOL = "Govt. Higher Secondary School Utror Swat"
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
            # Keep compatibility with the older SQLite version bundled with Python 3.6.
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

class App:
    def __init__(self, root):
        self.root=root
        self.store=DBStore()
        self.limiter=RateLimiter()
        self.pause=threading.Event(); self.pause.set()
        self.q=queue.Queue()
        self.checked=set()
        root.title(APP + " - " + SCHOOL)
        root.geometry("1120x720")
        root.minsize(900,600)
        self.build_login()

    def clear(self):
        for w in self.root.winfo_children(): w.destroy()

    def build_login(self):
        self.clear()
        f=tk.Frame(self.root,padx=50,pady=40); f.pack(expand=True)
        tk.Label(f,text=SCHOOL,font=("Segoe UI",20,"bold")).pack(pady=8)
        tk.Label(f,text="GSMS SMS Software",font=("Segoe UI",18,"bold")).pack(pady=4)
        tk.Label(f,text="Version 1.0",font=("Segoe UI",11,"italic")).pack(pady=4)
        tk.Label(f,text="Principal Login",font=("Segoe UI",12)).pack(pady=(28,6))
        pw=tk.Entry(f,show="*",width=28); pw.pack(); pw.focus()
        tk.Button(f,text="Login",width=16,command=lambda:self.login(pw.get())).pack(pady=14)
        tk.Label(f,text="Default first-login password: 1234",fg="#7a1f1f").pack()
        pw.bind("<Return>",lambda e:self.login(pw.get()))

    def login(self,p):
        if p==self.store.get("password"): self.build_main()
        else: messagebox.showerror(APP,"Incorrect password.")

    def build_main(self):
        self.clear()
        self.checked=set()
        self.root.geometry("1120x720")
        tk.Label(self.root,text=SCHOOL,bg="#dce9c4",font=("Segoe UI",16,"bold"),pady=5).pack(fill="x")
        tk.Label(self.root,text="GSMS SMS SOFTWARE",bg="#f9c08f",font=("Segoe UI",17,"bold"),pady=5).pack(fill="x")
        tk.Label(self.root,text="Version 1.0",font=("Segoe UI",10,"italic")).pack(anchor="e",padx=14,pady=(2,4))
        toolbar=tk.Frame(self.root); toolbar.pack(fill="x",padx=10,pady=2)
        tk.Button(toolbar,text="Import Students",command=self.import_students).pack(side="left")
        tk.Button(toolbar,text="Select All",command=self.select_all).pack(side="left",padx=4)
        tk.Button(toolbar,text="Clear Checks",command=self.clear_checks).pack(side="left")
        tk.Button(toolbar,text="Settings",command=self.settings).pack(side="right",padx=3)
        tk.Button(toolbar,text="Backup",command=self.backup).pack(side="right",padx=3)
        tk.Button(toolbar,text="Change Password",command=self.change_password).pack(side="right",padx=3)
        table_frame=tk.Frame(self.root,bd=1,relief="solid"); table_frame.pack(fill="both",expand=True,padx=10,pady=5)
        cols=("check","roll","name","father","class","section")
        self.tree=ttk.Treeview(table_frame,columns=cols,show="headings",selectmode="browse")
        headings={"check":"","roll":"Roll No","name":"Name","father":"Father Name","class":"Class","section":"Section"}
        widths={"check":45,"roll":95,"name":220,"father":220,"class":100,"section":100}
        for c in cols:
            self.tree.heading(c,text=headings[c]); self.tree.column(c,width=widths[c],anchor="w")
        self.tree.column("check",anchor="center")
        y=ttk.Scrollbar(table_frame,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side="left",fill="both",expand=True); y.pack(side="right",fill="y")
        self.tree.bind("<Button-1>",self.toggle_check)
        self.tree.bind("<Double-1>",self.edit_student)
        self.refresh_students()
        tk.Label(self.root,text="Message",font=("Segoe UI",10,"bold"),anchor="w").pack(fill="x",padx=12,pady=(4,0))
        self.message=tk.Text(self.root,height=7,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken")
        self.message.pack(fill="x",padx=10,pady=(2,5))
        bottom=tk.Frame(self.root); bottom.pack(fill="x",padx=10,pady=(0,10))
        self.status=tk.StringVar(value="Ready — check the students who should receive the SMS.")
        tk.Label(bottom,textvariable=self.status,anchor="w").pack(side="left",fill="x",expand=True)
        tk.Button(bottom,text="SEND SMS",font=("Segoe UI",11,"bold"),width=16,command=self.send_checked).pack(side="right")
        threading.Thread(target=self.worker,daemon=True).start()

    def refresh_students(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        self.checked=set()
        for r in self.store.contacts():
            rid,roll,name,father,cls,section,phone,group_name,kind=r
            self.tree.insert("","end",iid=str(rid),values=("☐",roll or "",name or "",father or "",cls or "",section or ""))

    def toggle_check(self,event):
        item=self.tree.identify_row(event.y); col=self.tree.identify_column(event.x)
        if not item or col!="#1": return
        rid=int(item)
        if rid in self.checked:
            self.checked.remove(rid); mark="☐"
        else:
            self.checked.add(rid); mark="☑"
        vals=list(self.tree.item(item,"values")); vals[0]=mark; self.tree.item(item,values=vals)

    def select_all(self):
        for item in self.tree.get_children():
            rid=int(item); self.checked.add(rid); vals=list(self.tree.item(item,"values")); vals[0]="☑"; self.tree.item(item,values=vals)
        self.status.set("All visible students checked.")
    def clear_checks(self):
        self.checked.clear()
        for item in self.tree.get_children():
            vals=list(self.tree.item(item,"values")); vals[0]="☐"; self.tree.item(item,values=vals)
        self.status.set("Checks cleared.")

    def student_data(self,rid):
        for r in self.store.contacts():
            if r[0]==rid:return r
        return None

    def edit_student(self,event=None):
        item=self.tree.focus()
        if not item:return
        row=self.student_data(int(item))
        if not row:return
        w=tk.Toplevel(self.root);w.title("Edit Student");f=tk.Frame(w,padx=15,pady=15);f.pack()
        vals=[row[1],row[2],row[3],row[4],row[5],row[6]]
        labels=["Roll No","Name","Father Name","Class","Section","Mobile No"]
        es=[]
        for i,(lab,val) in enumerate(zip(labels,vals)):
            tk.Label(f,text=lab,width=16,anchor="w").grid(row=i,column=0,pady=4)
            e=tk.Entry(f,width=40);e.grid(row=i,column=1,pady=4);e.insert(0,str(val or ""));es.append(e)
        def save():
            self.store.update_contact(row[0],*[e.get().strip() for e in es]);w.destroy();self.refresh_students()
        tk.Button(f,text="Save",command=save).grid(row=6,column=1,sticky="e",pady=8)

    def import_students(self):
        p=filedialog.askopenfilename(filetypes=[("Excel/CSV","*.xlsx *.xlsm *.csv"),("All files","*.*")])
        if not p:return
        try:
            if p.lower().endswith(".csv"):
                with open(p,newline="",encoding="utf-8-sig") as f: rows=list(csv.reader(f))
            else:
                from openpyxl import load_workbook
                rows=[list(r) for r in load_workbook(p,read_only=True,data_only=True).active.iter_rows(values_only=True)]
            if not rows: raise ValueError("No rows found")
            h=[str(x or "").strip().lower() for x in rows[0]]
            def idx(names,default):
                for n in names:
                    if n in h:return h.index(n)
                return default
            ri=idx(["roll no","roll number","admission no","admission number","s.no","sr no"],0)
            ni=idx(["name","student name"],1)
            fi=idx(["father name","father","guardian name"],2)
            ci=idx(["class","class name"],3)
            si=idx(["section","sec"],4)
            pi=idx(["mobile","mobile no","phone","phone number","parent phone"],5)
            count=0
            for r in rows[1:]:
                if len(r)<=max(ri,ni,pi):continue
                vals=[str(r[i] or "").strip() if i<len(r) else "" for i in (ri,ni,fi,ci,si,pi)]
                if vals[1] and vals[5]: self.store.add_contact(*vals);count+=1
            self.refresh_students();messagebox.showinfo(APP,"Imported %d student(s)."%count)
        except Exception as e: messagebox.showerror(APP,"Import failed: %s"%e)

    def send_checked(self):
        text=self.message.get("1.0","end").strip()
        if not text:return messagebox.showwarning(APP,"Please enter the SMS message first.")
        if not self.checked:return messagebox.showwarning(APP,"Please check at least one student.")
        rows=[]; missing=[]
        for rid in list(self.checked):
            r=self.student_data(rid)
            if r:
                if r[6]: rows.append(r)
                else: missing.append(r[2] or str(rid))
        if not rows:return messagebox.showerror(APP,"None of the checked students has a mobile number.")
        if missing and not messagebox.askyesno(APP,"%d checked student(s) have no mobile number and will be skipped. Continue?"%len(missing)):return
        if not messagebox.askyesno(APP,"Send this SMS to %d checked student(s)?"%len(rows)):return
        for r in rows:self.q.put((r[6],text,r[2] or "Student"))
        self.status.set("Queued %d SMS(s) for sending."%len(rows))

    def worker(self):
        while True:
            phone,msg,name=self.q.get()
            try:
                self.pause.wait()
                while not self.limiter.can_send():
                    wait=self.limiter.wait_seconds();self.status_set("Safety limit reached; waiting about %d minute(s)."%(int(wait//60)+1));time.sleep(min(max(wait,1),60));self.pause.wait()
                ok,detail=self.send_android(phone,msg)
                self.store.log(phone,msg,"accepted" if ok else "failed")
                if ok:self.limiter.mark(); self.status_set("Accepted: %s (%s)"%(name,phone))
                else:self.status_set("Failed: %s — %s"%(name,detail))
            finally:self.q.task_done()

    def status_set(self,t): self.root.after(0,lambda:self.status.set(t))
    def send_android(self,phone,msg):
        base=(self.store.get("android_url") or "").rstrip("/"); token=self.store.get("token") or ""
        data=json.dumps({"phone":phone,"message":msg}).encode()
        req=request.Request(base+"/send",data=data,method="POST",headers={"Content-Type":"application/json","X-GSMS-Token":token})
        try:
            with request.urlopen(req,timeout=12) as r:return r.status==200,r.read().decode(errors="replace")
        except Exception as e:return False,str(e)

    def settings(self):
        w=tk.Toplevel(self.root);w.title("Gateway Settings");f=tk.Frame(w,padx=20,pady=20);f.pack()
        tk.Label(f,text="Android URL").grid(row=0,column=0,sticky="w",pady=5);u=tk.Entry(f,width=48);u.grid(row=0,column=1);u.insert(0,self.store.get("android_url") or "")
        tk.Label(f,text="Pairing token").grid(row=1,column=0,sticky="w",pady=5);t=tk.Entry(f,width=48);t.grid(row=1,column=1);t.insert(0,self.store.get("token") or "")
        tk.Button(f,text="Save",command=lambda:(self.store.set("android_url",u.get().strip()),self.store.set("token",t.get().strip()),w.destroy())).grid(row=2,column=1,sticky="e",pady=10)

    def change_password(self):
        old=simpledialog.askstring(APP,"Current password",show="*")
        if old!=self.store.get("password"):return messagebox.showerror(APP,"Current password is incorrect.")
        new=simpledialog.askstring(APP,"New password",show="*")
        if new and len(new)>=4:self.store.set("password",new);messagebox.showinfo(APP,"Password changed.")

    def backup(self):
        p=filedialog.asksaveasfilename(defaultextension=".db",filetypes=[("GSMS backup","*.db")])
        if p:self.store.backup(p);messagebox.showinfo(APP,"Backup created successfully.")

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()

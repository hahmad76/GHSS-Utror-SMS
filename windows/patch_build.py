from pathlib import Path
p=Path('main.py')
s=p.read_text(encoding='utf-8')
s=s.replace('SCHOOL = "Govt. Higher Secondary School Utror Swat"\n', '''SCHOOL = "Govt. Higher Secondary School Utror Swat"\nCLASS_OPTIONS = ["6th", "7th", "8th", "9th", "10th", "11th", "12th", "Teaching Staff", "Non-Teaching Staff"]\n\ndef _persistent_data_dir():\n    candidates=[]\n    if os.path.isdir("D:\\\\"):\n        candidates.append(os.path.join("D:\\\\", "GSMS_SMS_Data"))\n    program_data=os.getenv("PROGRAMDATA")\n    if program_data:\n        candidates.append(os.path.join(program_data, "GSMS_SMS_v1"))\n    candidates.append(os.path.join(APPDATA, "GSMS_SMS_v1"))\n    for path in candidates:\n        try:\n            os.makedirs(path, exist_ok=True)\n            test=os.path.join(path, ".write_test")\n            with open(test, "w") as f: f.write("ok")\n            os.remove(test)\n            return path\n        except Exception:\n            pass\n    return os.path.join(APPDATA, "GSMS_SMS_v1")\n\n''')
s=s.replace('DB = os.path.join(APPDATA, "GSMS_SMS_v1", "gsms.db")\nif not os.path.isdir(os.path.dirname(DB)):\n    os.makedirs(os.path.dirname(DB))\n', '''DATA_DIR = _persistent_data_dir()\nDB = os.path.join(DATA_DIR, "gsms.db")\nAUTO_BACKUP = os.path.join(DATA_DIR, "gsms_auto_backup.db")\nLEGACY_DB = os.path.join(APPDATA, "GSMS_SMS_v1", "gsms.db")\nif not os.path.isdir(DATA_DIR): os.makedirs(DATA_DIR)\n''')
s=s.replace('    def __init__(self):\n        self.db = sqlite3.connect(DB, check_same_thread=False)', '''    def __init__(self):\n        self._recover_database()\n        self.db = sqlite3.connect(DB, check_same_thread=False)''')
needle='    def _migrate_contacts(self):\n'
s=s.replace(needle, '''    def _recover_database(self):\n        if os.path.exists(DB): return\n        for source in (LEGACY_DB, AUTO_BACKUP):\n            if source and os.path.exists(source) and os.path.abspath(source) != os.path.abspath(DB):\n                try:\n                    shutil.copy2(source, DB); return\n                except Exception: pass\n\n    def _auto_backup(self):\n        try:\n            if os.path.exists(DB) and os.path.abspath(AUTO_BACKUP) != os.path.abspath(DB):\n                shutil.copy2(DB, AUTO_BACKUP)\n        except Exception: pass\n\n'''+needle)
if 'def delete_contact(self, row_id)' not in s:
    s=s.replace('    def delete_contacts(self, ids):', '''    def delete_contact(self, row_id):\n        with self.lock:\n            self.db.execute("DELETE FROM contacts WHERE id=?", (row_id,))\n            self.db.commit()\n            self._auto_backup()\n\n    def delete_contacts(self, ids):''')
start=s.index('    def build_main(self):')
end=s.index('    def refresh_students(self):', start)
new=r'''    def build_main(self):
        self.clear()
        self.checked=set()
        self.filters={c:"" for c in ("check","roll","name","father","class","section","mobile")}
        self.root.geometry("1280x820")
        tk.Label(self.root,text=SCHOOL,bg="#dce9c4",font=("Segoe UI",16,"bold"),pady=5).pack(fill="x")
        tk.Label(self.root,text="GSMS SMS SOFTWARE",bg="#f9c08f",font=("Segoe UI",17,"bold"),pady=5).pack(fill="x")
        tk.Label(self.root,text="Version 1.0",font=("Segoe UI",10,"italic")).pack(anchor="e",padx=14,pady=(2,2))
        toolbar=tk.Frame(self.root); toolbar.pack(fill="x",padx=10,pady=2)
        tk.Button(toolbar,text="Import Students",command=self.import_students).pack(side="left")
        tk.Button(toolbar,text="Add New Person",command=self.focus_add_box).pack(side="left",padx=4)
        tk.Button(toolbar,text="Delete Selected",command=self.delete_selected).pack(side="left")
        tk.Button(toolbar,text="Select All",command=self.select_all).pack(side="left",padx=4)
        tk.Button(toolbar,text="Clear Checks",command=self.clear_checks).pack(side="left")
        tk.Button(toolbar,text="Clear Filters",command=self.clear_filters).pack(side="left",padx=4)
        tk.Button(toolbar,text="Settings",command=self.settings).pack(side="right",padx=3)
        tk.Button(toolbar,text="Backup",command=self.backup).pack(side="right",padx=3)
        tk.Button(toolbar,text="Change Password",command=self.change_password).pack(side="right",padx=3)
        add=tk.LabelFrame(self.root,text="Add New Person Manually",padx=6,pady=4); add.pack(fill="x",padx=10,pady=(2,4))
        fields=[("Roll No","roll"),("Name","name"),("Father Name","father"),("Class","class"),("Section","section"),("Mobile Number","mobile")]
        self.add_vars={}; self.add_widgets={}
        for i,(label,key) in enumerate(fields):
            tk.Label(add,text=label).grid(row=0,column=i,padx=3,sticky="w")
            if key=="class":
                var=tk.StringVar(value="6th"); self.add_vars[key]=var
                widget=ttk.Combobox(add,textvariable=var,values=CLASS_OPTIONS,state="readonly",width=15)
            else:
                var=tk.StringVar(); self.add_vars[key]=var
                widget=tk.Entry(add,textvariable=var,width=(14 if key in ("roll","section") else 24))
            widget.grid(row=1,column=i,padx=3,pady=2,sticky="ew"); self.add_widgets[key]=widget
        tk.Button(add,text="ADD",font=("Segoe UI",9,"bold"),command=self.add_person).grid(row=1,column=6,padx=6,pady=2,sticky="ew")
        table_frame=tk.Frame(self.root,bd=1,relief="solid"); table_frame.pack(fill="both",expand=True,padx=10,pady=5)
        cols=("check","roll","name","father","class","section","mobile")
        self.tree=ttk.Treeview(table_frame,columns=cols,show="headings",selectmode="browse")
        headings={"check":"✓ ▼","roll":"Roll No ▼","name":"Name ▼","father":"Father Name ▼","class":"Class ▼","section":"Section ▼","mobile":"Phone Number ▼"}
        widths={"check":55,"roll":95,"name":205,"father":205,"class":120,"section":90,"mobile":150}
        for c in cols:
            self.tree.heading(c,text=headings[c],command=lambda cc=c:self.open_filter(cc))
            self.tree.column(c,width=widths[c],anchor="w")
        self.tree.column("check",anchor="center")
        y=ttk.Scrollbar(table_frame,orient="vertical",command=self.tree.yview); x=ttk.Scrollbar(table_frame,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        self.tree.pack(side="top",fill="both",expand=True); x.pack(side="bottom",fill="x"); y.pack(side="right",fill="y")
        self.tree.bind("<Button-1>",self.toggle_check); self.tree.bind("<Double-1>",self.edit_student); self.tree.bind("<Button-3>",self.context_menu)
        self.refresh_students()
        tk.Label(self.root,text="Message",font=("Segoe UI",10,"bold"),anchor="w").pack(fill="x",padx=12,pady=(4,0))
        self.message=tk.Text(self.root,height=6,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken"); self.message.pack(fill="x",padx=10,pady=(2,5))
        bottom=tk.Frame(self.root); bottom.pack(fill="x",padx=10,pady=(0,10))
        self.status=tk.StringVar(value="Ready — check the people who should receive the SMS.")
        tk.Label(bottom,textvariable=self.status,anchor="w").pack(side="left",fill="x",expand=True)
        tk.Button(bottom,text="SEND SMS",font=("Segoe UI",11,"bold"),width=16,command=self.send_checked).pack(side="right")
        if not getattr(self,"worker_started",False):
            self.worker_started=True; threading.Thread(target=self.worker,daemon=True).start()

    def focus_add_box(self):
        self.add_widgets["name"].focus_set()

    def add_person(self):
        vals={k:self.add_vars[k].get().strip() for k in self.add_vars}
        if not vals["name"]: return messagebox.showwarning(APP,"Please enter the Name.")
        if not vals["mobile"]: return messagebox.showwarning(APP,"Please enter the Mobile Number.")
        self.store.add_contact(vals["roll"],vals["name"],vals["father"],vals["class"],vals["section"],vals["mobile"])
        for key in ("roll","name","father","section","mobile"): self.add_vars[key].set("")
        self.add_widgets["class"].set("6th"); self.refresh_students()
        self.status.set("New person added successfully and saved permanently.")

    def _row_matches(self,r):
        vals={"check":"Checked" if r[0] in self.checked else "Unchecked","roll":r[1] or "","name":r[2] or "","father":r[3] or "","class":r[4] or "","section":r[5] or "","mobile":r[6] or ""}
        return all(not f or f==vals[c] for c,f in self.filters.items())

    def open_filter(self,col):
        menu=tk.Menu(self.root,tearoff=0); values=[]; current=self.filters.get(col,"")
        if col=="class":
            values=CLASS_OPTIONS[:]
            values += [r[4] for r in self.store.contacts() if r[4] and r[4] not in values]
        elif col=="check": values=["Checked","Unchecked"]
        else:
            index={"roll":1,"name":2,"father":3,"section":5,"mobile":6}.get(col)
            if index is not None:
                values=sorted(set(str(r[index] or "") for r in self.store.contacts() if str(r[index] or "")),key=lambda x:x.lower())
        menu.add_command(label="All",command=lambda:self.set_filter(col,"")); menu.add_separator()
        for value in values[:200]: menu.add_command(label=("✓ " if current==value else "")+value,command=lambda v=value:self.set_filter(col,v))
        menu.add_separator(); menu.add_command(label="Clear All Filters",command=self.clear_filters)
        try: menu.tk_popup(self.root.winfo_pointerx(),self.root.winfo_pointery())
        finally: menu.grab_release()

    def set_filter(self,col,value):
        self.filters[col]=value; self.refresh_students(); self.status.set(col.title()+" filter: "+(value or "All"))

    def clear_filters(self):
        for c in self.filters: self.filters[c]=""
        self.refresh_students(); self.status.set("All filters cleared.")

    def context_menu(self,event):
        item=self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item); menu=tk.Menu(self.root,tearoff=0)
            menu.add_command(label="Edit",command=self.edit_student); menu.add_command(label="Delete Selected",command=self.delete_selected)
            menu.tk_popup(event.x_root,event.y_root); menu.grab_release()

    def delete_selected(self):
        item=self.tree.selection()
        if not item: return messagebox.showwarning(APP,"Please select one person first.")
        rid=int(item[0]); row=self.student_data(rid)
        if not row: return
        name=row[2] or "this person"
        if not messagebox.askyesno(APP,"Delete the record for %s permanently?\n\nThis action cannot be undone."%name): return
        self.store.delete_contact(rid); self.checked.discard(rid); self.refresh_students(); self.status.set("Record deleted: "+name)

'''
s=s[:start]+new+s[end:]
old='''    def refresh_students(self):\n        for x in self.tree.get_children(): self.tree.delete(x)\n        self.checked=set()\n        for r in self.store.contacts():\n            rid,roll,name,father,cls,section,phone,group_name,kind=r\n            self.tree.insert("","end",iid=str(rid),values=("☐",roll or "",name or "",father or "",cls or "",section or "",phone or ""))'''
newrefresh='''    def refresh_students(self):\n        for x in self.tree.get_children(): self.tree.delete(x)\n        for r in self.store.contacts():\n            if not self._row_matches(r): continue\n            rid,roll,name,father,cls,section,phone,group_name,kind=r\n            self.tree.insert("","end",iid=str(rid),values=("☑" if rid in self.checked else "☐",roll or "",name or "",father or "",cls or "",section or "",phone or ""))'''
s=s.replace(old,newrefresh)
old_edit='''            tk.Label(f,text=lab,width=16,anchor="w").grid(row=i,column=0,pady=4)\n            e=tk.Entry(f,width=40);e.grid(row=i,column=1,pady=4);e.insert(0,str(val or ""));es.append(e)'''
new_edit='''            tk.Label(f,text=lab,width=16,anchor="w").grid(row=i,column=0,pady=4)\n            if lab=="Class":\n                e=ttk.Combobox(f,values=CLASS_OPTIONS,state="readonly",width=37); e.set(str(val or "6th"))\n            else:\n                e=tk.Entry(f,width=40); e.insert(0,str(val or ""))\n            e.grid(row=i,column=1,pady=4); es.append(e)'''
s=s.replace(old_edit,new_edit)
old_select='''    def select_all(self):\n        for item in self.tree.get_children():\n            rid=int(item); self.checked.add(rid); vals=list(self.tree.item(item,"values")); vals[0]="☑"; self.tree.item(item,values=vals)\n        self.status.set("All visible students checked.")'''
new_select='''    def select_all(self):\n        for r in self.store.contacts():\n            if self._row_matches(r): self.checked.add(r[0])\n        self.refresh_students(); self.status.set("All visible people checked.")'''
s=s.replace(old_select,new_select)
old_clear='''    def clear_checks(self):\n        self.checked.clear()\n        for item in self.tree.get_children():\n            vals=list(self.tree.item(item,"values")); vals[0]="☐"; self.tree.item(item,values=vals)\n        self.status.set("Checks cleared.")'''
new_clear='''    def clear_checks(self):\n        self.checked.clear(); self.refresh_students(); self.status.set("Checks cleared.")'''
s=s.replace(old_clear,new_clear)
s=s.replace('messagebox.showinfo(APP,"Imported %d student(s)."%count)', 'messagebox.showinfo(APP,"Imported %d person(s).\\n\\nRecords are stored locally and do not need re-importing on every launch."%count)')
p.write_text(s,encoding='utf-8')

# Final GSMS v1.0 corrections applied AFTER all feature patches:
# 1) Force a compact main window so the Send SMS button remains above the taskbar.
# 2) Force a compact two-line message box.
# 3) Use the USB Modem / Wingle path by default for the PC-connected Wingle setup.
s = s.replace('self.root.geometry("1280x820")', 'self.root.geometry("1180x560")')
s = s.replace('self.root.geometry("1220x650")', 'self.root.geometry("1180x560")')
s = s.replace('self.root.geometry("1220x600")', 'self.root.geometry("1180x560")')
s = s.replace('self.message=tk.Text(self.root,height=6,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken")',
              'self.message=tk.Text(self.root,height=2,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken")')
s = s.replace('self.store.set("gateway_mode", "Android Gateway")', 'self.store.set("gateway_mode", "USB Modem / Wingle")')
s = s.replace('self.get("gateway_mode") is None: self.set("gateway_mode", "Android Gateway")',
              'self.get("gateway_mode") is None: self.set("gateway_mode", "USB Modem / Wingle")')
p.write_text(s,encoding='utf-8')

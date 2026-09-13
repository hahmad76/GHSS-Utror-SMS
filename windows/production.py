import tkinter as tk
from tkinter import messagebox

import main

APP = main.APP
DEFAULT_SCHOOL = getattr(main, "SCHOOL", "Govt. Higher Secondary School Utror Swat")
DEFAULT_SERVICE = "GSMS SMS SOFTWARE"
DEFAULT_VERSION = "Version 1.0"

_original_label = main.tk.Label

def _front_label(master=None, *args, **kwargs):
    text = kwargs.get("text")
    if text == "GSMS SMS SOFTWARE":
        kwargs["text"] = main.DEFAULT_SERVICE
    elif text == "Version 1.0":
        kwargs["text"] = main.DEFAULT_VERSION
    return _original_label(master, *args, **kwargs)

class ProductionApp(main.App):
    def __init__(self, root):
        bootstrap = main.DBStore()
        main.SCHOOL = bootstrap.get("school_name") or DEFAULT_SCHOOL
        main.DEFAULT_SERVICE = bootstrap.get("service_title") or DEFAULT_SERVICE
        main.DEFAULT_VERSION = bootstrap.get("version_text") or DEFAULT_VERSION
        main.tk.Label = _front_label
        super().__init__(root)

    def gateway_candidates(self):
        saved = (self.store.get("android_url") or "").strip().rstrip("/")
        candidates = []
        if saved:
            candidates.append(saved)
        for host in (
            "192.168.42.129", "192.168.43.1", "192.168.44.1",
            "192.168.42.1", "192.168.137.1", "192.168.1.100",
            "192.168.1.1"
        ):
            url = "http://" + host + ":8765"
            if url not in candidates:
                candidates.append(url)
        return candidates

    def gateway_test(self):
        results = []
        for base in self.gateway_candidates():
            try:
                with main.request.urlopen(base + "/health", timeout=2) as response:
                    body = response.read().decode(errors="replace")
                    if response.status == 200:
                        self.store.set("android_url", base)
                        return True, "CONNECTED: " + base + "\n" + body
            except Exception:
                results.append("No response: " + base)
        return False, "\n".join(results)

    def run_gateway_test(self):
        messagebox.showinfo(
            main.APP,
            "Gateway Test will check the saved Android address and common USB/private-network addresses.\n"
            "Keep the GSMS Android Gateway running on the phone."
        )
        self.status.set("Testing Android gateway...")
        import threading
        threading.Thread(target=self._gateway_test_worker, daemon=True).start()

    def _gateway_test_worker(self):
        ok, detail = self.gateway_test()
        def show():
            self.status.set("Android gateway connected." if ok else "Android gateway not found.")
            if ok:
                messagebox.showinfo(main.APP, "Gateway Test PASSED\n\n" + detail)
            else:
                messagebox.showwarning(
                    main.APP,
                    "Gateway Test could not connect.\n\n" + detail +
                    "\n\nIf using USB, enable USB tethering and keep the Android gateway active."
                )
        self.root.after(0, show)

    def settings(self):
        win = tk.Toplevel(self.root)
        win.title("GSMS Settings — Front Page & Gateway")
        frame = tk.Frame(win, padx=20, pady=18)
        frame.pack()

        fields = [
            ("Front Page / School Name", "school_name", self.store.get("school_name") or DEFAULT_SCHOOL),
            ("Front Page / Service Title", "service_title", self.store.get("service_title") or DEFAULT_SERVICE),
            ("Front Page / Version Text", "version_text", self.store.get("version_text") or DEFAULT_VERSION),
            ("Android Gateway URL", "android_url", self.store.get("android_url") or ""),
            ("Pairing Token", "token", self.store.get("token") or "")
        ]
        entries = {}
        for row, (label, key, value) in enumerate(fields):
            tk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            entry = tk.Entry(frame, width=52, show="*" if key == "token" else "")
            entry.grid(row=row, column=1, pady=5)
            entry.insert(0, value)
            entries[key] = entry

        def save():
            self.store.set("school_name", entries["school_name"].get().strip() or DEFAULT_SCHOOL)
            self.store.set("service_title", entries["service_title"].get().strip() or DEFAULT_SERVICE)
            self.store.set("version_text", entries["version_text"].get().strip() or DEFAULT_VERSION)
            self.store.set("android_url", entries["android_url"].get().strip())
            self.store.set("token", entries["token"].get().strip())
            main.SCHOOL = self.store.get("school_name") or DEFAULT_SCHOOL
            main.DEFAULT_SERVICE = self.store.get("service_title") or DEFAULT_SERVICE
            main.DEFAULT_VERSION = self.store.get("version_text") or DEFAULT_VERSION
            win.destroy()
            self.build_main()

        buttons = tk.Frame(frame)
        buttons.grid(row=len(fields), column=1, sticky="e", pady=(12, 0))
        tk.Button(buttons, text="Gateway Test", command=self.run_gateway_test).pack(side="left", padx=4)
        tk.Button(buttons, text="Save & Apply", command=save).pack(side="left", padx=4)

if __name__ == "__main__":
    root = tk.Tk()
    ProductionApp(root)
    root.mainloop()

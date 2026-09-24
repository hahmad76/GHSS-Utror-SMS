from pathlib import Path

# Final screen-fit adjustment for the GSMS Windows build.
# Keeps the existing interface and SMS logic unchanged, while ensuring
# the compose area and SEND SMS button remain visible above the taskbar.
p = Path("main.py")
s = p.read_text(encoding="utf-8")

old_geometry = 'self.root.geometry("1280x820")'
new_geometry = 'self.root.geometry("1220x650")'
if old_geometry in s:
    s = s.replace(old_geometry, new_geometry, 1)

old_message = 'self.message=tk.Text(self.root,height=6,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken")'
new_message = 'self.message=tk.Text(self.root,height=2,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken")'
if old_message in s:
    s = s.replace(old_message, new_message, 1)

p.write_text(s, encoding="utf-8")
print("GSMS UI adjustment applied: message box height=2; window height=650.")

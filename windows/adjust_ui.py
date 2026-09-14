from pathlib import Path

# Final screen-fit adjustment for the GSMS Windows build.
# Keeps the existing interface and SMS logic unchanged, but makes the
# message area shorter so the SEND SMS button remains visible above
# the Windows taskbar on typical 1366x768 / 1280x720 displays.
p = Path("main.py")
s = p.read_text(encoding="utf-8")

old_geometry = 'self.root.geometry("1280x820")'
new_geometry = 'self.root.geometry("1280x700")'
if old_geometry in s:
    s = s.replace(old_geometry, new_geometry, 1)

old_message = 'self.message=tk.Text(self.root,height=6,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken")'
new_message = 'self.message=tk.Text(self.root,height=4,wrap="word",font=("Segoe UI",11),bd=2,relief="sunken")'
if old_message in s:
    s = s.replace(old_message, new_message, 1)

p.write_text(s, encoding="utf-8")
print("GSMS UI adjustment applied: message box height=4; window height=700.")

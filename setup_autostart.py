import os
import sys
from pathlib import Path

startup_dir = (
    Path(os.environ["APPDATA"])
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)
vbs_path = startup_dir / "SideDock.vbs"

pythonw = Path(sys.executable).with_name("pythonw.exe")
if not pythonw.exists():
    pythonw = Path(sys.executable)


if vbs_path.exists():
    vbs_path.unlink()
    print("SideDock auto-start DISABLED.")
else:
    vbs_content = (
        f'CreateObject("Wscript.Shell").Run '
        f'"""{pythonw}"" -m sidedock", 0, False\n'
    )
    vbs_path.write_text(vbs_content, encoding="utf-8")
    print(f"SideDock auto-start ENABLED at: {vbs_path}")
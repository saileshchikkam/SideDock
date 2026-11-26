"""Toggle SideDock startup for a Python installation."""
from sidedock.autostart import is_enabled, set_enabled


def main():
    enabled = not is_enabled()
    set_enabled(enabled)
    print(f"SideDock auto-start {'ENABLED' if enabled else 'DISABLED'}.")


if __name__ == "__main__":
    main()

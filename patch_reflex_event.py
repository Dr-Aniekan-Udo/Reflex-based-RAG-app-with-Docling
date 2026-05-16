"""
Patch Reflex to respect transport='polling' when generating env.json.

Reflex 0.8.x hardcodes wss:// for the EVENT endpoint regardless of
the transport config. This patch makes it check config.transport first.

Run this before 'reflex init' or 'reflex run'.
"""
import sys
import site
from pathlib import Path


def find_reflex_event_module() -> Path | None:
    """Find the installed reflex_base/constants/event.py file."""
    search_paths = []
    
    # Check current directory venv first
    cwd = Path.cwd()
    search_paths.append(str(cwd / ".venv" / "lib"))
    search_paths.append(str(cwd / ".venv" / "Lib"))
    
    # Check site-packages directories
    try:
        search_paths.extend(site.getsitepackages())
    except AttributeError:
        pass
    
    user_site = site.getusersitepackages()
    if user_site:
        search_paths.append(user_site)
    
    # Also check sys.path (includes venv)
    search_paths.extend(sys.path)
    
    for sp in search_paths:
        if not sp:
            continue
        path = Path(sp) / "reflex_base" / "constants" / "event.py"
        if path.exists():
            return path
        # Also check under site-packages
        for site_pkg in Path(sp).rglob("site-packages"):
            path = site_pkg / "reflex_base" / "constants" / "event.py"
            if path.exists():
                return path
    
    return None


def apply_patch():
    event_file = find_reflex_event_module()
    if not event_file:
        print("ERROR: Could not find reflex_base/constants/event.py")
        print("Searched paths:")
        for p in sys.path:
            print(f"  {p}")
        sys.exit(1)
    
    content = event_file.read_text()
    
    # Check if already patched
    if 'config.transport != "polling"' in content:
        print("[OK] Reflex event patch already applied.")
        return
    
    # The exact code to patch (from Reflex 0.8.x)
    # Use simpler string matching to avoid whitespace issues
    old_code = 'if self == Endpoint.EVENT:'
    
    if old_code not in content:
        print("WARNING: Could not find the expected code to patch.")
        print("The Reflex version may have changed.")
        print(f"File: {event_file}")
        sys.exit(1)
    
    # Replace the specific block
    content = content.replace(
        """        # The event endpoint is a websocket.
        if self == Endpoint.EVENT:
            # Replace the protocol with ws.
            url = url.replace("https://", "wss://").replace("http://", "ws://")""",
        """        # The event endpoint is a websocket (unless polling is configured).
        if self == Endpoint.EVENT:
            from reflex_base.config import get_config
            if get_config().transport != "polling":
                # Replace the protocol with ws.
                url = url.replace("https://", "wss://").replace("http://", "ws://")"""
    )
    
    event_file.write_text(content)
    print(f"[OK] Patched: {event_file}")


if __name__ == "__main__":
    apply_patch()

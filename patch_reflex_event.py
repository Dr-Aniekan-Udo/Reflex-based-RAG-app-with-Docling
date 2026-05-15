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
        print("✅ Reflex event patch already applied.")
        return
    
    # The exact code to patch (from Reflex 0.8.x)
    old_code = """        # The event endpoint is a websocket.
        if self == Endpoint.EVENT:
            # Replace the protocol with ws.
            url = url.replace("https://", "wss://").replace("http://", "ws://")"""
    
    new_code = """        # The event endpoint is a websocket (unless polling is configured).
        if self == Endpoint.EVENT:
            from reflex_base.config import get_config
            if get_config().transport != "polling":
                # Replace the protocol with ws.
                url = url.replace("https://", "wss://").replace("http://", "ws://")"""
    
    if old_code not in content:
        print("WARNING: Could not find the expected code to patch.")
        print("The Reflex version may have changed.")
        print(f"File: {event_file}")
        sys.exit(1)
    
    content = content.replace(old_code, new_code)
    event_file.write_text(content)
    print(f"✅ Patched: {event_file}")


if __name__ == "__main__":
    apply_patch()

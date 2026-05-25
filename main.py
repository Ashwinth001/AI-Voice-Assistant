"""
ARIA -- Main Entry Point
Launches holographic UI and wires orchestrator
"""
import tkinter as tk
import threading
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from core.config_loader import cfg

def main():
    root = tk.Tk()

    theme = cfg["app"].get("theme", "holographic")
    if theme == "holographic":
        from ui.themes.holographic import HolographicUI
        ui = HolographicUI(root)
    elif theme == "neon_glass":
        from ui.themes.neon_glass import NeonGlassUI
        ui = NeonGlassUI(root)
    elif theme == "minimal":
        from ui.themes.minimal_dark import MinimalDarkUI
        ui = MinimalDarkUI(root)
    else:
        from ui.themes.holographic import HolographicUI
        ui = HolographicUI(root)

    # Wire orchestrator
    try:
        from core.orchestrator import ARIAOrchestrator

        orch = ARIAOrchestrator(
            on_state_change = lambda s: root.after(0, ui.set_state, s),
            on_transcript   = lambda t: root.after(0, ui.set_transcript, t),
            on_response     = lambda r: root.after(0, ui.set_response, r),
        )
        ui.orchestrator = orch

        def run():
            orch.start()
        threading.Thread(target=run, daemon=True).start()

        def update_stats():
            try:
                ui.set_stats(orch.get_stats())
            except Exception:
                pass
            root.after(5000, update_stats)
        root.after(3000, update_stats)

    except ImportError as e:
        print(f"[ARIA] Running in demo mode -- missing dep: {e}")
    except Exception as e:
        print(f"[ARIA] Orchestrator error: {e}")

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()

if __name__ == "__main__":
    main()

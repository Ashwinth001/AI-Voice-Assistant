"""
ASTRA -- Main Entry Point
Runs setup wizard on first launch, then starts the AI assistant.
"""
import tkinter as tk
import threading
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

USER_PROFILE = ROOT / "data" / "user_profile.json"


def run_first_time_setup():
    """Run the setup wizard for first-time users."""
    print("[ASTRA] First run detected - launching setup wizard...")
    from installer_ui import run_setup
    run_setup()


def main():
    # Check if first run
    if not USER_PROFILE.exists():
        run_first_time_setup()
        # Check again after setup
        if not USER_PROFILE.exists():
            print("[ASTRA] Setup cancelled. Exiting.")
            return
    
    # Reload config after setup
    from core.config_loader import load_config
    cfg = load_config()
    
    root = tk.Tk()
    
    # Get theme from config
    theme = cfg["app"].get("theme", "holographic")
    ai_name = cfg["app"].get("ai_name", "Astra")
    
    print(f"[ASTRA] Starting with AI name: {ai_name}")
    print(f"[ASTRA] Theme: {theme}")
    
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
        print(f"[ASTRA] Running in demo mode -- missing dep: {e}")
    except Exception as e:
        print(f"[ASTRA] Orchestrator error: {e}")
        import traceback
        traceback.print_exc()

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()

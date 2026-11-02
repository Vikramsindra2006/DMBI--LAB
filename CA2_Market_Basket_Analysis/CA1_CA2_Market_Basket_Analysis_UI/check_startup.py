r"""Command Prompt diagnostic: .venv\Scripts\python.exe -u check_startup.py"""
import importlib
import platform
import time

print("Python:", platform.python_version(), flush=True)
for name in ["streamlit", "pandas", "market_basket.core", "market_basket.charts", "market_basket.exports"]:
    print("Loading", name, "...", flush=True)
    start = time.perf_counter()
    try:
        importlib.import_module(name)
    except Exception:
        print("FAILED:", name, flush=True)
        raise
    print("Ready:", name, f"({time.perf_counter()-start:.2f}s)", flush=True)
print("All imports ready. Run: python -m streamlit run app.py", flush=True)

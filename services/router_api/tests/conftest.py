import os
import sys

# Ensure `app.main` is importable when pytest is invoked from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

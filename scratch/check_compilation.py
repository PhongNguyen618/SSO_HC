import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import backend.main
    print("Syntax and imports check: SUCCESS!")
except Exception as e:
    import traceback
    traceback.print_exc()

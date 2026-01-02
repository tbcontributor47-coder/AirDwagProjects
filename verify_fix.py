import sys
import os

# Add tests directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'tests'))

try:
    import test_outputs
    path = test_outputs.get_source_path()
    print(f"Result from get_source_path: {path}")
    if os.path.exists(path):
        print("SUCCESS: File exists.")
        sys.exit(0)
    else:
        print("FAILURE: File does not exist.")
        sys.exit(1)
except Exception as e:
    print(f"EXCEPTION: {e}")
    sys.exit(1)

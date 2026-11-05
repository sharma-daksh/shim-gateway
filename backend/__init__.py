"""
SHIM Backend Package
"""
import sys
import os

# Automatically add backend folder to sys.path so both top-level and relative imports resolve in any environment
backend_path = os.path.dirname(os.path.abspath(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

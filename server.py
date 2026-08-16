"""
Backward-compatibility root server entry point.
Forwards to the standardized popmely package.
"""
import sys
import os

# Add src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from popmely.server import main

if __name__ == "__main__":
    main()

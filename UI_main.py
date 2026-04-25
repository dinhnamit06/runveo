import sys
from pathlib import Path

# Add root directory to sys.path so 'src' can be imported
sys.path.insert(0, str(Path(__file__).parent))

from src.core.UI_main import main

if __name__ == "__main__":
    main()

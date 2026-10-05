"""Make the api_tool package importable when running `python -m pytest tests`."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # widget tests run without a display
os.environ.setdefault("API_TOOL_NO_UPDATE_CHECK", "1")  # tests never contact GitHub

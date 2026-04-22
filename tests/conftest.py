"""
Pytest configuration and fixtures for market_research_skill tests
"""

import sys
import os
from pathlib import Path

# Add scripts directory to path so tests can import modules
scripts_path = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_path))

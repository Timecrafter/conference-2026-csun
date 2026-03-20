"""Console script entry point for csun-analytics.

Loads .env files and delegates to main.main().
"""

import sys
from pathlib import Path


def main():
    # Load .env from project root before anything else
    try:
        from dotenv import load_dotenv
        project_root = Path(__file__).resolve().parents[2]
        # .env.local overrides .env
        load_dotenv(project_root / ".env")
        load_dotenv(project_root / ".env.local", override=True)
    except ImportError:
        pass

    # Import and run main CLI
    # We import here (not at top) so dotenv is loaded first
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from main import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()

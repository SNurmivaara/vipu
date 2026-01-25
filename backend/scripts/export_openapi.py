#!/usr/bin/env python3
"""Export OpenAPI spec to JSON file."""

import json
import os
import sys
from pathlib import Path

# Set testing environment to use SQLite (no external DB needed)
os.environ["FLASK_ENV"] = "testing"

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app


def main() -> None:
    """Export OpenAPI spec."""
    app = create_app()

    with app.app_context():
        spec = app.spec

    output_dir = Path(__file__).parent.parent.parent / "docs"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "openapi.json"
    with open(output_file, "w") as f:
        json.dump(spec, f, indent=2)

    print(f"OpenAPI spec exported to {output_file}")


if __name__ == "__main__":
    main()

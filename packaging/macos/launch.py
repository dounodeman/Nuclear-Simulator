"""Entry point for the packaged Mac app."""

import sys

from reactorsim.app.desktop import main

if __name__ == "__main__":
    # Older macOS passes a -psn_ process serial number when an app is opened from Finder.
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith("-psn")]))

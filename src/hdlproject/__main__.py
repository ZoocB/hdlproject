"""Allow running as: python -m hdlproject"""
import sys

from hdlproject.main import main

if __name__ == "__main__":
    sys.exit(main())

"""Allow running as: python -m hdlproject"""
from hdlproject.main import main
import sys

if __name__ == "__main__":
    sys.exit(main())
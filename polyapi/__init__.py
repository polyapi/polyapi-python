import os
import sys

__all__ = ["poly"]


if sys.argv[-1] not in ["generate", "help"]:
    currdir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(currdir, "poly")):
        print("No 'poly' found. Please run 'python3 -m polyapi generate' to generate the 'poly' library for your tenant.")
        sys.exit(1)
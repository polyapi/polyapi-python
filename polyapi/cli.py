import sys
from .generate import generate


def execute_from_cli():
    try:
        subcommand = sys.argv[1]
    except IndexError:
        subcommand = "help"  # Display help if no arguments were given.

    if subcommand == "help":
        print(f"executing subcommand {subcommand}")
    elif subcommand == "generate":
        generate()

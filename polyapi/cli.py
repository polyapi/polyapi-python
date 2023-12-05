import sys
from .generate import generate


def execute_from_cli():
    try:
        subcommand = sys.argv[1]
    except IndexError:
        subcommand = "help"  # Display help if no arguments were given.

    if subcommand == "help":
        print("Use `python3 -m polyapi generate` to generate the PolyAPI library.")
    elif subcommand == "generate":
        print("Generating...")
        generate()
    else:
        print("Invalid command {subcommand}. Available commands are 'generate' and 'help'.")
        exit(1)

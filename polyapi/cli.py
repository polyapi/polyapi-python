import sys
from .generate import generate
from .function_cli import function_add_or_update


CLI_COMMANDS = ["generate", "help", "function"]


def execute_from_cli():
    try:
        command = sys.argv[1]
    except IndexError:
        command = "help"  # Display help if no arguments were given.

    if command == "help":
        print("Use `python3 -m polyapi generate` to generate the PolyAPI library.")
    elif command == "generate":
        print("Generating...")
        generate()
    elif command == "function":
        function_add_or_update(*sys.argv[2:])
    else:
        print("Invalid command {subcommand}. Available commands are 'generate' and 'help'.")
        exit(1)

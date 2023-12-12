import sys
import argparse
from .generate import generate
from .function_cli import function_add_or_update


CLI_COMMANDS = ["generate", "help", "function"]


def execute_from_cli():
    parser = argparse.ArgumentParser(
        prog="python -m polyapi", description="PolyAPI Client"
    )
    parser.add_argument("--context", required=False, default="")
    parser.add_argument("--description", required=False, default="")
    parser.add_argument("--server", action="store_true")
    parser.add_argument("command", choices=CLI_COMMANDS)
    parser.add_argument("subcommands", nargs="*")
    args = parser.parse_args()
    command = args.command

    if command == "help":
        print("Use `python3 -m polyapi generate` to generate the PolyAPI library.")
    elif command == "generate":
        print("Generating...")
        generate()
    elif command == "function":
        function_add_or_update(args.context, args.description, args.server, args.subcommands)

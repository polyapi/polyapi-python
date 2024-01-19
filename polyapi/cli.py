import sys
import argparse
from .generate import generate, clear
from .function_cli import function_add_or_update


CLI_COMMANDS = ["generate", "clear", "function", "help"]


def execute_from_cli():
    parser = argparse.ArgumentParser(
        prog="python -m polyapi", description="PolyAPI Client"
    )
    parser.add_argument("--context", required=False, default="")
    parser.add_argument("--description", required=False, default="")
    parser.add_argument("--server", action="store_true", help="Pass --server if you want this to be a server function. By default, it will be a client function.")
    parser.add_argument("--logs", action="store_true", help="Pass --logs if you want to store and see the logs from this function executing")
    parser.add_argument("command", choices=CLI_COMMANDS)
    parser.add_argument("subcommands", nargs="*")
    args = parser.parse_args()
    command = args.command

    if command == "help":
        parser.print_help()
    elif command == "generate":
        print("Generating...")
        generate()
    elif command == "clear":
        print("Clearing the generated library...")
        clear()
    elif command == "function":
        function_add_or_update(args.context, args.description, args.server, args.logs, args.subcommands)

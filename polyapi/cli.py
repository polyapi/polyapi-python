import argparse

from polyapi.utils import print_green

from .config import clear_config, set_api_key_and_url
from .generate import generate, clear, save_rendered_specs
from .function_cli import function_add_or_update


CLI_COMMANDS = ["setup", "generate", "function", "clear", "help", "save_rendered_specs"]

CLIENT_DESC = """Commands
  python -m polyapi setup                Setup your Poly connection
  python -m polyapi generate             Generates Poly library
  python -m polyapi function <command>   Manages functions
  python -m polyapi clear                Clear current generated Poly library
"""


def execute_from_cli():
    parser = argparse.ArgumentParser(
        prog="python -m polyapi", description=CLIENT_DESC, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--context", required=False, default="")
    parser.add_argument("--description", required=False, default="")
    parser.add_argument("--server", action="store_true", help="Pass --server when adding function to add a server function. By default, new functions are client.")
    parser.add_argument("--logs", action="store_true", help="Pass --logs when adding function if you want to store and see the function logs.")
    parser.add_argument("command", choices=CLI_COMMANDS)
    parser.add_argument("subcommands", nargs="*")
    args = parser.parse_args()
    command = args.command

    if command == "help":
        parser.print_help()
    elif command == "generate":
        print("Generating Poly functions...", end="")
        generate()
        print_green("DONE")
    elif command == "setup" and len(args.subcommands) == 2:
        set_api_key_and_url(args.subcommands[1], args.subcommands[0])
    elif command == "setup":
        clear_config()
        generate()
    elif command == "save_rendered_specs":
        save_rendered_specs()
    elif command == "clear":
        print("Clearing the generated library...")
        clear()
    elif command == "function":
        function_add_or_update(args.context, args.description, args.server, args.logs, args.subcommands)

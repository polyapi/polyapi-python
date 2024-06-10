import argparse

from polyapi.utils import print_green

from .config import clear_config, set_api_key_and_url
from .generate import generate, clear
from .function_cli import function_add_or_update
from .rendered_spec import get_and_update_rendered_spec


CLI_COMMANDS = ["setup", "generate", "function", "clear", "help", "update_rendered_spec"]

CLIENT_DESC = """Commands
  python -m polyapi setup                Setup your Poly connection
  python -m polyapi generate             Generates Poly library
  python -m polyapi function <command>   Manages functions
  python -m polyapi clear                Clear current generated Poly library
"""


def execute_from_cli() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m polyapi", description=CLIENT_DESC, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--context", required=False, default="")
    parser.add_argument("--description", required=False, default="")
    parser.add_argument("--client", action="store_true", help="Pass --client when adding function to add a client function.")
    parser.add_argument("--server", action="store_true", help="Pass --server when adding function to add a server function.")
    parser.add_argument("--logs", action="store_true", help="Pass --logs when adding function if you want to store and see the function logs.")
    parser.add_argument("--skip-generate", action="store_true", help="Pass --skip-generate to skip generating the library after adding a function.")
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
    elif command == "update_rendered_spec":
        assert len(args.subcommands) == 2
        updated = get_and_update_rendered_spec(args.subcommands[0], args.subcommands[1])
        if updated:
            print("Updated rendered spec!")
        else:
            print("Failed to update rendered spec!")
            exit(1)
    elif command == "clear":
        print("Clearing the generated library...")
        clear()
    elif command == "function":
        function_add_or_update(args.context, args.description, args.client, args.server, args.logs, args.subcommands, not args.skip_generate)

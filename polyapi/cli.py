import argparse

from polyapi.utils import print_green

from .config import initialize_config, set_api_key_and_url
from .generate import generate, clear
from .function_cli import function_add_or_update, function_execute
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
    parser.add_argument("--logs", choices=["enabled", "disabled"], default="disabled", help="Enable or disable logs for the function.")
    parser.add_argument("--skip-generate", action="store_true", help="Pass --skip-generate to skip generating the library after adding a function.")
    parser.add_argument("--execution-api-key", required=False, default="", help="API key for execution (for server functions only).")
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
        initialize_config(force=True)
        generate()
    elif command == "update_rendered_spec":
        assert len(args.subcommands) == 1
        updated = get_and_update_rendered_spec(args.subcommands[0])
        if updated:
            print("Updated rendered spec!")
        else:
            print("Failed to update rendered spec!")
            exit(1)
    elif command == "clear":
        print("Clearing the generated library...")
        clear()
    elif command == "function":
        logs_enabled = args.logs == "enabled"
        if args.subcommands[0] == "execute":
            print(function_execute(args.context, args.subcommands))
        else:
            function_add_or_update(
                context=args.context,
                description=args.description,
                client=args.client,
                server=args.server,
                logs_enabled=logs_enabled,
                subcommands=args.subcommands,
                generate=not args.skip_generate,
                execution_api_key=args.execution_api_key
            )

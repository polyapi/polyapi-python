import os
import argparse

from polyapi.utils import print_green, print_red

from .config import clear_config, set_api_key_and_url, initialize_config
from .generate import generate, clear
from .function_cli import function_add_or_update, function_execute
from .rendered_spec import get_and_update_rendered_spec
from .prepare import prepare_deployables
from .sync import sync_deployables


CLI_COMMANDS = ["setup", "generate", "function", "clear", "help", "update_rendered_spec"]

def execute_from_cli():
    # First we setup all our argument parsing logic
    # Then we parse the arguments (waaay at the bottom)
    parser = argparse.ArgumentParser(
        prog="python -m polyapi",
        description="Manage your Poly API configurations and functions",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    subparsers = parser.add_subparsers(help="Available commands")

    ###########################################################################
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Setup your Poly connection")
    setup_parser.add_argument("api_key", nargs="?", help="API key for Poly API")
    setup_parser.add_argument("url", nargs="?", help="URL for the Poly API")

    def setup(args):
        if args.api_key and args.url:
            set_api_key_and_url(args.url, args.api_key)
        else:
            clear_config()
            generate()

    setup_parser.set_defaults(command=setup)


    ###########################################################################
    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generates Poly library")

    def generate_command(args):
        initialize_config()
        print("Generating Poly functions...", end="")
        generate()
        print_green("DONE")

    generate_parser.set_defaults(command=generate_command)


    ###########################################################################
    # Function commands
    fn_parser = subparsers.add_parser("function", help="Manage and execute functions")
    fn_subparsers = fn_parser.add_subparsers(help="Available commands")

    # Function - Add command
    fn_add_parser = fn_subparsers.add_parser("add", help="Add or update the function")
    fn_add_parser.add_argument("name", help="Name of the function")
    fn_add_parser.add_argument("file", help="Path to the function file")
    fn_add_parser.add_argument("--context", required=False, default="", help="Context of the function")
    fn_add_parser.add_argument("--description", required=False, default="", help="Description of the function")
    fn_add_parser.add_argument("--server", action="store_true", help="Marks the function as a server function")
    fn_add_parser.add_argument("--client", action="store_true", help="Marks the function as a client function")
    fn_add_parser.add_argument("--logs", "--logs-enabled", action="store_true", help="Pass --logs if you want to store and see server function logs.")
    fn_add_parser.add_argument("--disable-ai", "--skip-generate", action="store_true", help="Pass --disable-ai skip AI generation of missing descriptions")

    def add_function(args):
        initialize_config()
        err = ""
        if args.server and args.client:
            err = "Specify either `--server` or `--client`. Found both."
        elif not args.server and not args.client:
            err = "You must specify `--server` or `--client`."
        elif args.logs and not args.server:
            err = "Option `logs` is only for server functions (--server)."

        if err:
            print_red("ERROR")
            print(err)
            exit(1)

        function_add_or_update(args.name, args.file, args.context, args.description, args.client, args.server, args.logs, not args.disable_ai)

    fn_add_parser.set_defaults(command=add_function)


    # Function - Execute command
    fn_exec_parser = fn_subparsers.add_parser("execute", help="Execute a function with the provided arguments")
    fn_exec_parser.add_argument("name", help="Name of the function")
    fn_exec_parser.add_argument("args", nargs="*", help="Arguments for the function")
    fn_exec_parser.add_argument("--context", required=False, default="", help="Context of the function")

    def execute_function(args):
        initialize_config()
        print(function_execute(args.context, args.name, args.args))

    fn_exec_parser.set_defaults(command=execute_function)


    ###########################################################################
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear current generated Poly library")

    def clear_command(_):
        print("Clearing the generated library...")
        clear()

    clear_parser.set_defaults(command=clear_command)


    ###########################################################################
    # Update rendered spec command
    update_spec_parser = subparsers.add_parser("update_rendered_spec", help="Update the rendered spec file")
    update_spec_parser.add_argument("spec", help="Specification file to update")

    def update_rendered_spec(args):
        updated = get_and_update_rendered_spec(args.spec)
        if updated:
            print("Updated rendered spec!")
        else:
            print("Failed to update rendered spec!")
            exit(1)

    update_spec_parser.set_defaults(command=update_rendered_spec)


    ###########################################################################
    # Prepare command
    prepare_parser = subparsers.add_parser('prepare', help="Find and prepare all Poly deployables")
    prepare_parser.add_argument("--lazy", action="store_true", help="Skip prepare work if the cache is up to date. (Relies on `git`)")
    prepare_parser.add_argument("--disable-docs", action="store_true", help="Don't write any docstrings into the deployable files.")
    prepare_parser.add_argument("--disable-ai", action="store_true", help="Don't use AI to fill in any missing descriptions.")

    def prepare(args):
        initialize_config()
        disable_ai = args.disable_ai or bool(os.getenv("DISABLE_AI"))
        prepare_deployables(lazy=args.lazy, disable_docs=args.disable_docs, disable_ai=disable_ai)

    prepare_parser.set_defaults(command=prepare)


    ###########################################################################
    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Find and sync all Poly deployables")
    sync_parser.add_argument("--dry-run", action="store_true", help="Run through sync steps with logging but don't make any changes.")

    def sync(args):
        initialize_config()
        prepare_deployables(lazy=True, disable_docs=True, disable_ai=True)
        if args.dry_run:
            print("Running dry-run of sync...")
        sync_deployables(dry_run=args.dry_run)
        print("Poly deployments synced.")

    sync_parser.set_defaults(command=sync)

    ###########################################################################
    #         _------.                                                        #
    #        /  ,     \_             __         __ _          ________        #
    #      /   /  /{}\ |o\_         / /   ___  / /( )_____   / ____/ /_  __   #
    #     /    \  `--' /-' \       / /   / _ \/ __/// ___/  / /_  / / / / /   #
    #    |      \     \     |     / /___/  __/ /_  (__  )  / __/ / / /_/ /    #
    #   |              |`-, |    /_____/\___/\__/ /____/  /_/   /_/\__, /     #
    #  /               /__/)/                                     /____/      #
    # /               |                                                       #
    ###########################################################################
    parsed_args = parser.parse_args()
    if hasattr(parsed_args, "command"):
        parsed_args.command(parsed_args)
    else:
        parser.print_help()

import re
import os
from colorama import Fore, Style


# this string should be in every __init__ file.
# it contains all the imports needed for the function or variable code to run
CODE_IMPORTS = "from typing import List, Dict, Any, TypedDict\nfrom polyapi.execute import execute, variable_get, variable_update\n\n"


def init_the_init(full_path: str) -> None:
    init_path = os.path.join(full_path, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write(CODE_IMPORTS)


def add_import_to_init(full_path: str, next: str) -> None:
    init_the_init(full_path)

    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a+") as f:
        import_stmt = "from . import {}\n".format(next)
        f.seek(0)
        lines = f.readlines()
        if import_stmt not in set(lines):
            f.write(import_stmt)


def get_auth_headers(api_key: str):
    return {"Authorization": f"Bearer {api_key}"}


def camelCase(s):
    s = s.strip()
    if " " in s or "-" in s:
        s = re.sub(r"(_|-)+", " ", s).title().replace(" ", "")
        return ''.join([s[0].lower(), s[1:]])
    else:
        # s is already in camelcase as best as we can tell, just move on!
        return s


def print_green(s: str):
    print(Fore.GREEN + s + Style.RESET_ALL)


def print_yellow(s: str):
    print(Fore.YELLOW + s + Style.RESET_ALL)


def print_red(s: str):
    print(Fore.RED + s + Style.RESET_ALL)
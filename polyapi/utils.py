import re
import os


def append_init(full_path: str, next: str) -> None:
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
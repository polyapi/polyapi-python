import os


def append_init(full_path: str, next: str) -> None:
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a+") as f:
        import_stmt = "from . import {}\n".format(next)
        f.seek(0)
        lines = f.readlines()
        if import_stmt not in set(lines):
            f.write(import_stmt)
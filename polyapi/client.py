from typing import Any, Dict, List, Tuple

from polyapi.typedefs import PropertySpecification
from polyapi.utils import camelCase, add_type_import_path, parse_arguments, get_type_and_def

DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict
{args_def}
{return_type_def}
"""


def _wrap_code_in_try_except(code: str) -> str:
    """ this is necessary because client functions with imports will blow up ALL server functions,
    even if they don't use them.
    because the server function will try to load all client functions when loading the library
    """
    prefix = """logger = logging.getLogger("poly")
try:
    """
    suffix = """except ImportError as e:
    logger.debug(e)"""

    lines = code.split("\n")
    code = "\n    ".join(lines)
    return "".join([prefix, code, "\n", suffix])


def render_client_function(
    function_name: str,
    code: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str]:
    args, args_def = parse_arguments(function_name, arguments)
    return_type_name, return_type_def = get_type_and_def(return_type)  # type: ignore
    func_type_defs = DEFS_TEMPLATE.format(
        args_def=args_def,
        return_type_def=return_type_def,
    )

    code = _wrap_code_in_try_except(code)

    return code + "\n\n", func_type_defs
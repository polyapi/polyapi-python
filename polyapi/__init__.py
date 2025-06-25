import os
import sys
import copy
import truststore
from typing import Any, Dict, Optional, overload, Literal
from typing_extensions import TypedDict
truststore.inject_into_ssl()
from .cli import CLI_COMMANDS

__all__ = ["poly"]


if len(sys.argv) > 1 and sys.argv[1] not in CLI_COMMANDS:
    currdir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(currdir, "poly")):
        print("No 'poly' found. Please run 'python3 -m polyapi generate' to generate the 'poly' library for your tenant.")
        sys.exit(1)


class PolyCustomDict(TypedDict, total=False):
    """Type definition for polyCustom dictionary."""
    executionId: Optional[str]  # Read-only
    executionApiKey: Optional[str]
    responseStatusCode: int
    responseContentType: Optional[str]
    responseHeaders: Dict[str, str]


class _PolyCustom:
    def __init__(self):
        self._internal_store = {
            "executionId": None,
            "executionApiKey": None,
            "responseStatusCode": 200,
            "responseContentType": None,
            "responseHeaders": {},
        }
        self._execution_id_locked = False

    def set_once(self, key: str, value: Any) -> None:
        if key == "executionId" and self._execution_id_locked:
            # Silently ignore attempts to overwrite locked executionId
            return
        self._internal_store[key] = value
        if key == "executionId":
            # Lock executionId after setting it
            self.lock_execution_id()

    def get(self, key: str, default: Any = None) -> Any:
        return self._internal_store.get(key, default)

    def lock_execution_id(self) -> None:
        self._execution_id_locked = True

    def unlock_execution_id(self) -> None:
        self._execution_id_locked = False

    @overload
    def __getitem__(self, key: Literal["executionId"]) -> Optional[str]: ...
    
    @overload
    def __getitem__(self, key: Literal["executionApiKey"]) -> Optional[str]: ...
    
    @overload
    def __getitem__(self, key: Literal["responseStatusCode"]) -> int: ...
    
    @overload
    def __getitem__(self, key: Literal["responseContentType"]) -> Optional[str]: ...

    @overload
    def __getitem__(self, key: Literal["responseHeaders"]) -> Dict[str, str]: ...
    
    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    @overload
    def __setitem__(self, key: Literal["executionApiKey"], value: Optional[str]) -> None: ...
    
    @overload
    def __setitem__(self, key: Literal["responseStatusCode"], value: int) -> None: ...
    
    @overload
    def __setitem__(self, key: Literal["responseContentType"], value: Optional[str]) -> None: ...

    @overload
    def __setitem__(self, key: Literal["responseHeaders"], value: Dict[str, str]) -> None: ...
    
    def __setitem__(self, key: str, value: Any) -> None:
        self.set_once(key, value)

    def __repr__(self) -> str:
        return f"PolyCustom({self._internal_store})"

    def copy(self) -> '_PolyCustom':
        new = _PolyCustom()
        new._internal_store = copy.deepcopy(self._internal_store)
        new._execution_id_locked = self._execution_id_locked
        return new


polyCustom: PolyCustomDict = _PolyCustom()
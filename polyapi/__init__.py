import copy
import os
import sys
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, overload

import truststore
from typing_extensions import TypedDict

from .cli_constants import CLI_COMMANDS

truststore.inject_into_ssl()

__all__ = ["poly"]


if len(sys.argv) > 1 and sys.argv[1] not in CLI_COMMANDS:
    currdir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(currdir, "poly")):
        print("No 'poly' found. Please run 'python3 -m polyapi generate' to generate the 'poly' library for your tenant.")
        sys.exit(1)


class PolyCustomDict(TypedDict, total=False):
    """Type definition for polyCustom dictionary."""

    executionId: Optional[str]  # Read-only unless explicitly unlocked
    executionApiKey: Optional[str]
    userSessionId: Optional[str]
    responseStatusCode: Optional[int]
    responseContentType: Optional[str]
    responseHeaders: Dict[str, Any]


@dataclass
class _PolyCustomState:
    internal_store: Dict[str, Any]
    execution_id_locked: bool = False


class PolyCustom:
    def __init__(self) -> None:
        object.__setattr__(
            self,
            "_default_store",
            {
                "executionId": None,
                "executionApiKey": None,
                "userSessionId": None,
                "responseStatusCode": 200,
                "responseContentType": None,
                "responseHeaders": {},
            },
        )
        object.__setattr__(self, "_state_var", ContextVar("_poly_custom_state", default=None))

    def _make_state(self) -> _PolyCustomState:
        return _PolyCustomState(internal_store=copy.deepcopy(self._default_store))

    def _get_state(self) -> _PolyCustomState:
        state = self._state_var.get()
        if state is None:
            state = self._make_state()
            self._state_var.set(state)
        return state

    def push_scope(self, initial_values: Optional[Dict[str, Any]] = None) -> Token:
        state = self._make_state()
        if initial_values:
            state.internal_store.update(copy.deepcopy(initial_values))
            if state.internal_store.get("executionId") is not None:
                state.execution_id_locked = True
        return self._state_var.set(state)

    def pop_scope(self, token: Token) -> None:
        self._state_var.reset(token)

    def set_once(self, key: str, value: Any) -> None:
        state = self._get_state()
        if key == "executionId" and state.execution_id_locked:
            return
        state.internal_store[key] = value
        if key == "executionId":
            state.execution_id_locked = True

    def get(self, key: str, default: Any = None) -> Any:
        return self._get_state().internal_store.get(key, default)

    def lock_execution_id(self) -> None:
        self._get_state().execution_id_locked = True

    def unlock_execution_id(self) -> None:
        self._get_state().execution_id_locked = False

    @overload
    def __getitem__(self, key: Literal["executionId"]) -> Optional[str]: ...

    @overload
    def __getitem__(self, key: Literal["executionApiKey"]) -> Optional[str]: ...

    @overload
    def __getitem__(self, key: Literal["userSessionId"]) -> Optional[str]: ...

    @overload
    def __getitem__(self, key: Literal["responseStatusCode"]) -> Optional[int]: ...

    @overload
    def __getitem__(self, key: Literal["responseContentType"]) -> Optional[str]: ...

    @overload
    def __getitem__(self, key: Literal["responseHeaders"]) -> Dict[str, Any]: ...

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    @overload
    def __setitem__(self, key: Literal["executionApiKey"], value: Optional[str]) -> None: ...

    @overload
    def __setitem__(self, key: Literal["userSessionId"], value: Optional[str]) -> None: ...

    @overload
    def __setitem__(self, key: Literal["responseStatusCode"], value: Optional[int]) -> None: ...

    @overload
    def __setitem__(self, key: Literal["responseContentType"], value: Optional[str]) -> None: ...

    @overload
    def __setitem__(self, key: Literal["responseHeaders"], value: Dict[str, Any]) -> None: ...

    def __setitem__(self, key: str, value: Any) -> None:
        self.set_once(key, value)

    def __getattr__(self, key: str) -> Any:
        if key in self._default_store:
            return self.get(key)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {key!r}")

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith("_"):
            object.__setattr__(self, key, value)
            return
        self.set_once(key, value)

    def __repr__(self) -> str:
        return f"PolyCustom({self._get_state().internal_store})"

    def copy(self) -> "PolyCustom":
        new = PolyCustom()
        state = self._get_state()
        new._state_var.set(
            _PolyCustomState(
                internal_store=copy.deepcopy(state.internal_store),
                execution_id_locked=state.execution_id_locked,
            )
        )
        return new


_PolyCustom = PolyCustom

polyCustom: PolyCustom = PolyCustom()

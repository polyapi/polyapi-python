from typing import Any, List, Literal, Dict, TypedDict
from typing_extensions import NotRequired


class PropertySpecification(TypedDict):
    name: str
    description: str
    required: bool
    nullable: NotRequired[bool]
    type: "PropertyType"


class PropertyType(TypedDict):
    kind: Literal['void', 'primitive', 'array', 'object', 'function', 'plain']
    spec: NotRequired[Dict]
    name: NotRequired[str]
    type: NotRequired[str]
    items: NotRequired['PropertyType']
    schema: NotRequired[Dict]
    properties: NotRequired[List[PropertySpecification]]
    typeName: NotRequired[str]
    value: NotRequired[str]


class FunctionSpecification(TypedDict):
    arguments: List[PropertySpecification]
    returnType: Dict[str, Any]
    synchronous: NotRequired[bool]


class SpecificationDto(TypedDict):
    id: str
    context: str
    name: str
    description: str
    # function is none (or function key not present) if this is actually VariableSpecDto
    function: NotRequired[FunctionSpecification | None]
    type: Literal['apiFunction', 'customFunction', 'serverFunction', 'authFunction', 'webhookHandle', 'serverVariable']
    code: NotRequired[str]
    language: str


class VariableSpecification(TypedDict):
    environmentId: str
    value: Any
    valueType: PropertyType
    secret: bool


class VariableSpecDto(TypedDict):
    id: str
    context: str
    name: str
    description: str
    variable: VariableSpecification
    type: Literal['serverVariable']
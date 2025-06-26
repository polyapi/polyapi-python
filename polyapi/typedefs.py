from typing import Any, List, Literal, Dict, Union
from typing_extensions import NotRequired, TypedDict


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


# Enum for variable secrecy levels
Secrecy = Literal['SECRET', 'OBSCURED', 'NONE']


class VariableSpecification(TypedDict):
    environmentId: str
    value: Any
    valueType: PropertyType
    secrecy: Secrecy


class VariableSpecDto(TypedDict):
    id: str
    context: str
    name: str
    description: str
    variable: VariableSpecification
    type: Literal['serverVariable']


class SchemaSpecDto(TypedDict):
    id: str
    context: str
    name: str
    contextName: str
    type: Literal['schema']
    definition: Dict[Any, Any]
    visibilityMetadata: object
    unresolvedPolySchemaRefs: List
    # TODO add more


Visibility = Union[Literal['PUBLIC'], Literal['TENANT'], Literal['ENVIRONMENT']]


class PolyDeployable(TypedDict, total=False):
    context: str
    name: str
    description: NotRequired[str]
    disable_ai: NotRequired[bool]  # Optional field to disable AI


class PolyServerFunction(PolyDeployable):
    logs_enabled: NotRequired[bool]
    always_on: NotRequired[bool]
    visibility: NotRequired[Visibility]


class PolyClientFunction(PolyDeployable):
    logs_enabled: NotRequired[bool]
    visibility: NotRequired[Visibility]

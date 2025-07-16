from typing import Any, List, Literal, Dict, Union
from typing_extensions import NotRequired, TypedDict


class PropertySpecification(TypedDict):
    name: str
    description: str
    required: bool
    nullable: NotRequired[bool]
    type: "PropertyType"


class PropertyType(TypedDict):
    kind: Literal['void', 'primitive', 'array', 'object', 'function', 'plain', 'any']
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
    type: Literal['apiFunction', 'customFunction', 'serverFunction', 'authFunction', 'webhookHandle', 'serverVariable', 'table']
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


class TableSpecDto(TypedDict):
    id: str
    context: str
    name: str
    contextName: str
    description: str
    type: Literal['table']
    schema: Dict[Any, Any]
    unresolvedPolySchemaRefs: List


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


class Table(TypedDict):
    id: str
    createdAt: str
    updatedAt: str


class PolyCountResult(TypedDict):
    count: int


class PolyDeleteResults(TypedDict):
    deleted: int



QueryMode = Literal["default", "insensitive"]


SortOrder = Literal["asc", "desc"]

# Using functional form because of use of reserved keywords
StringFilter = TypedDict("StringFilter", {
    "equals": NotRequired[str],
    "in": NotRequired[List[str]],
    "not_in": NotRequired[List[str]],
    "lt": NotRequired[str],
    "lte": NotRequired[str],
    "gt": NotRequired[str],
    "gte": NotRequired[str],
    "contains": NotRequired[str],
    "starts_with": NotRequired[str],
    "ends_with": NotRequired[str],
    "mode": NotRequired[QueryMode],
    "not": NotRequired[Union[str, "StringFilter"]],
})

# Using functional form because of use of reserved keywords
NullableStringFilter = TypedDict("NullableStringFilter", {
    "equals": NotRequired[Union[str, None]],
    "in": NotRequired[List[str]],
    "not_in": NotRequired[List[str]],
    "lt": NotRequired[str],
    "lte": NotRequired[str],
    "gt": NotRequired[str],
    "gte": NotRequired[str],
    "contains": NotRequired[str],
    "starts_with": NotRequired[str],
    "ends_with": NotRequired[str],
    "mode": NotRequired[QueryMode],
    "not": NotRequired[Union[str, None, "NullableStringFilter"]],
})

# Using functional form because of use of reserved keywords
NumberFilter = TypedDict("NumberFilter", {
    "equals": NotRequired[Union[int, float]],
    "in": NotRequired[List[Union[int, float]]],
    "not_in": NotRequired[List[Union[int, float]]],
    "lt": NotRequired[Union[int, float]],
    "lte": NotRequired[Union[int, float]],
    "gt": NotRequired[Union[int, float]],
    "gte": NotRequired[Union[int, float]],
    "not": NotRequired[Union[int, float, "NumberFilter"]],
})

# Using functional form because of use of reserved keywords
NullableNumberFilter = TypedDict("NullableNumberFilter", {
    "equals": NotRequired[Union[int, float, None]],
    "in": NotRequired[List[Union[int, float]]],
    "not_in": NotRequired[List[Union[int, float]]],
    "lt": NotRequired[Union[int, float]],
    "lte": NotRequired[Union[int, float]],
    "gt": NotRequired[Union[int, float]],
    "gte": NotRequired[Union[int, float]],
    "not": NotRequired[Union[int, float, None, "NullableNumberFilter"]],
})


# Using functional form because of use of reserved keywords
BooleanFilter = TypedDict("BooleanFilter", {
    "equals": NotRequired[bool],
    "not": NotRequired[Union[bool, "BooleanFilter"]],
})

# Using functional form because of use of reserved keywords
NullableBooleanFilter = TypedDict("NullableBooleanFilter", {
    "equals": NotRequired[Union[bool, None]],
    "not": NotRequired[Union[bool, None, "NullableBooleanFilter"]],
})

# Using functional form because of use of reserved keywords
NullableObjectFilter = TypedDict("NullableObjectFilter", {
    "equals": NotRequired[None],
    "not": NotRequired[Union[None, "NullableObjectFilter"]],
})

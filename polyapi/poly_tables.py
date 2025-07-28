import os
import requests
from typing_extensions import NotRequired, TypedDict
from typing import List, Union, Type, Dict, Any, Literal, Tuple, Optional, get_args, get_origin
from polyapi.utils import add_import_to_init, init_the_init
from polyapi.typedefs import TableSpecDto
from polyapi.constants import JSONSCHEMA_TO_PYTHON_TYPE_MAP


def scrub_keys(e: Exception) -> Dict[str, Any]:
    """
    Scrub the keys of an exception to remove sensitive information.
    Returns a dictionary with the error message and type.
    """
    return {
        "error": str(e),
        "type": type(e).__name__,
        "message": str(e),
        "args": getattr(e, 'args', None)
    }


def execute_query(table_id, method, query):
    from polyapi import polyCustom
    from polyapi.poly.client_id import client_id
    try:
        url = f"/tables/{table_id}/{method}?clientId={client_id}"
        headers = {{
            'x-poly-execution-id': polyCustom.get('executionId')
        }}
        response = requests.post(url, json=query, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return scrub_keys(e)


def first_result(rsp):
    if isinstance(rsp, dict) and isinstance(rsp.get('results'), list):
        return rsp['results'][0] if rsp['results'] else None
    return rsp


_key_transform_map = {
    "not_": "not",
    "in": "in",
    "starts_with": "startsWith",
    "ends_with": "startsWith",
    "not_in": "notIn",
}


def _transform_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            _key_transform_map.get(k, k): _transform_keys(v)
            for k, v in obj.items()
        }

    elif isinstance(obj, list):
        return [_transform_keys(v) for v in obj]

    else:
        return obj


def transform_query(query: dict) -> dict:
    if query["where"] or query["order_by"]:
        return {
            **query,
            "where": _transform_keys(query["where"]) if query["where"] else None,
            "orderBy": query["order_by"] if query["order_by"] else None
        }

    return query


TABI_TABLE_TEMPLATE = '''
{table_name}Columns = Literal[{table_columns}]



{table_row_classes}



{table_row_subset_class}



{table_where_class}



class {table_name}SelectManyQuery(TypedDict):
    where: NotRequired[{table_name}WhereFilter]
    order_by: NotRequired[Dict[{table_name}Columns, SortOrder]]
    limit: NotRequired[int]
    offset: NotRequired[int]



class {table_name}SelectOneQuery(TypedDict):
    where: NotRequired[{table_name}WhereFilter]
    order_by: NotRequired[Dict[{table_name}Columns, SortOrder]]



class {table_name}InsertOneQuery(TypedDict):
    data: {table_name}Subset



class {table_name}InsertManyQuery(TypedDict):
    data: List[{table_name}Subset]



class {table_name}UpdateManyQuery(TypedDict):
    where: NotRequired[{table_name}WhereFilter]
    data: {table_name}Subset



class {table_name}DeleteQuery(TypedDict):
    where: NotRequired[{table_name}WhereFilter]



class {table_name}QueryResults(TypedDict):
    results: List[{table_name}Row]
    pagination: None # Pagination not yet supported



class {table_name}CountQuery(TypedDict):
    where: NotRequired[{table_name}WhereFilter]



class {table_name}:{table_description}
    table_id = "{table_id}"

    @overload
    @staticmethod
    def count(query: {table_name}CountQuery) -> PolyCountResult: ...
    @overload
    @staticmethod
    def count(*, where: Optional[{table_name}WhereFilter]) -> PolyCountResult: ...

    @staticmethod
    def count(*args, **kwargs) -> PolyCountResult:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query({table_name}.table_id, "count", transform_query(query))

    @overload
    @staticmethod
    def select_many(query: {table_name}SelectManyQuery) -> {table_name}QueryResults: ...
    @overload
    @staticmethod
    def select_many(*, where: Optional[{table_name}WhereFilter], order_by: Optional[Dict[{table_name}Columns, SortOrder]], limit: Optional[int], offset: Optional[int]) -> {table_name}QueryResults: ...

    @staticmethod
    def select_many(*args, **kwargs) -> {table_name}QueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        if query.get('limit') is None:
            query['limit'] = 1000
        if query['limit'] > 1000:
            raise ValueError("Cannot select more than 1000 rows at a time.")
        return execute_query({table_name}.table_id, "select", transform_query(query))

    @overload
    @staticmethod
    def select_one(query: {table_name}SelectOneQuery) -> {table_name}Row: ...
    @overload
    @staticmethod
    def select_one(*, where: Optional[{table_name}WhereFilter], order_by: Optional[Dict[{table_name}Columns, SortOrder]]) -> {table_name}Row: ...

    @staticmethod
    def select_one(*args, **kwargs) -> {table_name}Row:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        query['limit'] = 1
        return first_result(execute_query({table_name}.table_id, "select", transform_query(query)))

    @overload
    @staticmethod
    def insert_many(query: {table_name}InsertManyQuery) -> {table_name}QueryResults: ...
    @overload
    @staticmethod
    def insert_many(*, data: List[{table_name}Subset]) -> {table_name}QueryResults: ...

    @staticmethod
    def insert_many(*args, **kwargs) -> {table_name}QueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        if len(query['data']) > 1000:
            raise ValueError("Cannot insert more than 1000 rows at a time.")
        return execute_query({table_name}.table_id, "insert", query)

    @overload
    @staticmethod
    def insert_one(query: {table_name}InsertOneQuery) -> {table_name}Row: ...
    @overload
    @staticmethod
    def insert_one(*, data: {table_name}Subset) -> {table_name}Row: ...

    @staticmethod
    def insert_one(*args, **kwargs) -> {table_name}Row:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return first_result(execute_query({table_name}.table_id, "insert", {{ 'data': [query['data']] }}))

    @overload
    @staticmethod
    def upsert_many(query: {table_name}InsertManyQuery) -> {table_name}QueryResults: ...
    @overload
    @staticmethod
    def upsert_many(*, data: List[{table_name}Subset]) -> {table_name}QueryResults: ...

    @staticmethod
    def upsert_many(*args, **kwargs) -> {table_name}QueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        if len(data) > 1000:
            raise ValueError("Cannot upsert more than 1000 rows at a time.")
        return execute_query({table_name}.table_id, "upsert", query)

    @overload
    @staticmethod
    def upsert_one(query: {table_name}InsertOneQuery) -> {table_name}Row: ...
    @overload
    @staticmethod
    def upsert_one(*, data: {table_name}Subset) -> {table_name}Row: ...

    @staticmethod
    def upsert_one(*args, **kwargs) -> {table_name}Row:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return first_result(execute_query({table_name}.table_id, "upsert", {{ 'data': [query['data']] }}))

    @overload
    @staticmethod
    def update_many(query: {table_name}UpdateManyQuery) -> {table_name}QueryResults: ...
    @overload
    @staticmethod
    def update_many(*, where: Optional[{table_name}WhereFilter], data: {table_name}Subset) -> {table_name}QueryResults: ...

    @staticmethod
    def update_many(*args, **kwargs) -> {table_name}QueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query({table_name}.table_id, "update", transform_query(query))

    @overload
    @staticmethod
    def delete_many(query: {table_name}DeleteQuery) -> PolyDeleteResults: ...
    @overload
    @staticmethod
    def delete_many(*, where: Optional[{table_name}WhereFilter]) -> PolyDeleteResults: ...

    @staticmethod
    def delete_many(*args, **kwargs) -> PolyDeleteResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query({table_name}.table_id, "delete", query)
'''


def _get_column_type_str(name: str, schema: Dict[str, Any], is_required: bool) -> str:
    result = ""

    col_type = schema.get("type", "object")
    if isinstance(col_type, list):
        subtypes = [_get_column_type_str(name, { **schema, "type": t }, is_required) for t in col_type]
        result = f"Union[{', '.join(subtypes)}]"
    elif col_type == "array":
        if isinstance(schema["items"], list):
            subtypes = [_get_column_type_str(f"{name}{i}", s, True) for i, s in enumerate(schema["items"])]
            result = f"Tuple[{', '.join(subtypes)}]"
        elif isinstance(schema["items"], dict):
            result = f"List[{_get_column_type_str(name, schema['items'], True)}]"
        else:
            result = "List[Any]"
    elif col_type == "object":
        if isinstance(schema.get("patternProperties"), dict):
            # TODO: Handle multiple pattern properties
            result = f"Dict[str, {_get_column_type_str(f'{name}_', schema['patternProperties'], True)}]"
        elif isinstance(schema.get("properties"), dict) and len(schema["properties"].values()) > 0:
            # TODO: Handle x-poly-refs
            result = f'"{name}"'
        else:
            result = "Dict[str, Any]"
    else:
        result = JSONSCHEMA_TO_PYTHON_TYPE_MAP.get(schema["type"], "")

    if result:
        return result if is_required else f"Optional[{result}]"

    return "Any"


def _render_table_row_classes(table_name: str, schema: Dict[str, Any]) -> str:
    from polyapi.schema import wrapped_generate_schema_types

    output = wrapped_generate_schema_types(schema, f"{table_name}Row", "Dict")

    return output[1].split("\n", 1)[1].strip()


def _render_table_subset_class(table_name: str, columns: List[Tuple[str, Dict[str, Any]]], required: List[str]) -> str:
    # Generate class which can match any subset of a table row
    lines = [f"class {table_name}Subset(TypedDict):"]

    for name, schema in columns:
        type_str = _get_column_type_str(f"_{table_name}Row{name}", schema, name in required)
        lines.append(f"    {name}: NotRequired[{type_str}]")

    return "\n".join(lines)


def _render_table_where_class(table_name: str, columns: List[Tuple[str, Dict[str, Any]]], required: List[str]) -> str:
    # Generate class for the 'where' part of the query
    lines = [f"class {table_name}WhereFilter(TypedDict):"]

    for name, schema in columns:
        ftype_str = ""
        type_str = _get_column_type_str(f"_{table_name}Row{name}", schema, True) # force required to avoid wrapping type in Optional[]
        is_required = name in required
        if type_str == "bool":
            ftype_str = "BooleanFilter" if is_required else "NullableBooleanFilter"
        elif type_str == "str":
            ftype_str = "StringFilter" if is_required else "NullableStringFilter"
        elif type_str in ["int", "float"]:
            ftype_str = "NumberFilter" if is_required else "NullableNumberFilter"
        elif is_required == False:
            type_str = "None"
            ftype_str = "NullableObjectFilter"

        if ftype_str:
            lines.append(f"    {name}: NotRequired[Union[{type_str}, {ftype_str}]]")

    lines.append(f'    AND: NotRequired[Union["{table_name}WhereFilter", List["{table_name}WhereFilter"]]]')
    lines.append(f'    OR: NotRequired[List["{table_name}WhereFilter"]]')
    lines.append(f'    NOT: NotRequired[Union["{table_name}WhereFilter", List["{table_name}WhereFilter"]]]')

    return "\n".join(lines)


def _render_table(table: TableSpecDto) -> str:
    columns = list(table["schema"]["properties"].items())
    required_colunms = table["schema"].get("required", [])

    table_columns = ",".join([ f'"{k}"' for k,_ in columns])
    table_row_classes = _render_table_row_classes(table["name"], table["schema"])
    table_row_subset_class = _render_table_subset_class(table["name"], columns, required_colunms)
    table_where_class = _render_table_where_class(table["name"], columns, required_colunms)
    if table.get("description", ""):
        table_description =  '\n    """'
        table_description += '\n       '.join(table["description"].replace('"', "'").split("\n"))
        table_description += '\n    """'
    else:
        table_description = ""

    return TABI_TABLE_TEMPLATE.format(
        table_name=table["name"],
        table_id=table["id"],
        table_description=table_description,
        table_columns=table_columns,
        table_row_classes=table_row_classes,
        table_row_subset_class=table_row_subset_class,
        table_where_class=table_where_class,
    )


def generate_tables(tables: List[TableSpecDto]):
    for table in tables:
        _create_table(table)


def _create_table(table: TableSpecDto) -> None:
    folders = ["tabi"]
    if table["context"]:
        folders += table["context"].split(".")

    # build up the full_path by adding all the folders
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    full_path = base_path

    for idx, folder in enumerate(folders):
        full_path = os.path.join(full_path, folder)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
        next = folders[idx + 1] if idx + 1 < len(folders) else None
        if next:
            add_import_to_init(full_path, next, "")

    init_path = os.path.join(full_path, "__init__.py")

    imports = "\n".join([
        "from typing_extensions import NotRequired, TypedDict",
        "from typing import Union, List, Dict, Any, Literal, Optional, Required, overload",
        "from polyapi.poly_tables import execute_query, first_result, transform_query",
        "from polyapi.typedefs import Table, PolyCountResult, PolyDeleteResults, SortOrder, StringFilter, NullableStringFilter, NumberFilter, NullableNumberFilter, BooleanFilter, NullableBooleanFilter, NullableObjectFilter",
    ])
    table_contents = _render_table(table)

    file_contents = ""
    if os.path.exists(init_path):
        with open(init_path, "r") as f:
            file_contents = f.read()

    with open(init_path, "w") as f:
        if not file_contents.startswith(imports):
            f.write(imports + "\n\n\n")
        if file_contents:
            f.write(file_contents + "\n\n\n")
        f.write(table_contents)

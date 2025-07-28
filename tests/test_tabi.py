import unittest
from polyapi.poly_tables import _render_table


TABLE_SPEC_SIMPLE = {
    "type": "table",
    "id": "123456789",
    "name": "MyTable",
    "context": "some.context.here",
    "contextName": "some.context.here.MyTable",
    "description": "This table stores:\n  - User name\n  - User age\n  - If user is active on the platform",
    "schema": {
        "$schema": "http://json-schema.org/draft-06/schema#",
        "type": "object",
        "properties": {
            "id": { "type": "string" },
            "createdAt": { "type": "string" },
            "updatedAt": { "type": "string" },
            "name": { "type": "string" },
            "age": { "type": "integer" },
            "active": { "type": "boolean" },
            "optional": { "type": "object" }
        },
        "required": [
            "id",
            "createdAt",
            "updatedAt",
            "name",
            "age",
            "active"
        ],
        "additionalProperties": False,
    }
}

EXPECTED_SIMPLE = '''
MyTableColumns = Literal["id","createdAt","updatedAt","name","age","active","optional"]



class MyTableRow(TypedDict, total=False):
    id: Required[str]
    """ Required property """

    createdAt: Required[str]
    """ Required property """

    updatedAt: Required[str]
    """ Required property """

    name: Required[str]
    """ Required property """

    age: Required[int]
    """ Required property """

    active: Required[bool]
    """ Required property """

    optional: dict[str, Any]



class MyTableSubset(TypedDict):
    id: NotRequired[str]
    createdAt: NotRequired[str]
    updatedAt: NotRequired[str]
    name: NotRequired[str]
    age: NotRequired[int]
    active: NotRequired[bool]
    optional: NotRequired[Optional[Dict[str, Any]]]



class MyTableWhereFilter(TypedDict):
    id: NotRequired[Union[str, StringFilter]]
    createdAt: NotRequired[Union[str, StringFilter]]
    updatedAt: NotRequired[Union[str, StringFilter]]
    name: NotRequired[Union[str, StringFilter]]
    age: NotRequired[Union[int, NumberFilter]]
    active: NotRequired[Union[bool, BooleanFilter]]
    optional: NotRequired[Union[None, NullableObjectFilter]]
    AND: NotRequired[Union["MyTableWhereFilter", List["MyTableWhereFilter"]]]
    OR: NotRequired[List["MyTableWhereFilter"]]
    NOT: NotRequired[Union["MyTableWhereFilter", List["MyTableWhereFilter"]]]



class MyTableSelectManyQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]
    order_by: NotRequired[Dict[MyTableColumns, SortOrder]]
    limit: NotRequired[int]
    offset: NotRequired[int]



class MyTableSelectOneQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]
    order_by: NotRequired[Dict[MyTableColumns, SortOrder]]



class MyTableInsertOneQuery(TypedDict):
    data: MyTableSubset



class MyTableInsertManyQuery(TypedDict):
    data: List[MyTableSubset]



class MyTableUpdateManyQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]
    data: MyTableSubset



class MyTableDeleteQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]



class MyTableQueryResults(TypedDict):
    results: List[MyTableRow]
    pagination: None # Pagination not yet supported



class MyTableCountQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]



class MyTable:
    """This table stores:
         - User name
         - User age
         - If user is active on the platform
    """
    table_id = "123456789"

    @overload
    @staticmethod
    def count(query: MyTableCountQuery) -> PolyCountResult: ...
    @overload
    @staticmethod
    def count(*, where: Optional[MyTableWhereFilter]) -> PolyCountResult: ...

    @staticmethod
    def count(*args, **kwargs) -> PolyCountResult:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query(MyTable.table_id, "count", transform_query(query))

    @overload
    @staticmethod
    def select_many(query: MyTableSelectManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def select_many(*, where: Optional[MyTableWhereFilter], order_by: Optional[Dict[MyTableColumns, SortOrder]], limit: Optional[int], offset: Optional[int]) -> MyTableQueryResults: ...

    @staticmethod
    def select_many(*args, **kwargs) -> MyTableQueryResults:
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
        return execute_query(MyTable.table_id, "select", transform_query(query))

    @overload
    @staticmethod
    def select_one(query: MyTableSelectOneQuery) -> MyTableRow: ...
    @overload
    @staticmethod
    def select_one(*, where: Optional[MyTableWhereFilter], order_by: Optional[Dict[MyTableColumns, SortOrder]]) -> MyTableRow: ...

    @staticmethod
    def select_one(*args, **kwargs) -> MyTableRow:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        query['limit'] = 1
        return first_result(execute_query(MyTable.table_id, "select", transform_query(query)))

    @overload
    @staticmethod
    def insert_many(query: MyTableInsertManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def insert_many(*, data: List[MyTableSubset]) -> MyTableQueryResults: ...

    @staticmethod
    def insert_many(*args, **kwargs) -> MyTableQueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        if len(query['data']) > 1000:
            raise ValueError("Cannot insert more than 1000 rows at a time.")
        return execute_query(MyTable.table_id, "insert", query)

    @overload
    @staticmethod
    def insert_one(query: MyTableInsertOneQuery) -> MyTableRow: ...
    @overload
    @staticmethod
    def insert_one(*, data: MyTableSubset) -> MyTableRow: ...

    @staticmethod
    def insert_one(*args, **kwargs) -> MyTableRow:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return first_result(execute_query(MyTable.table_id, "insert", { 'data': [query['data']] }))

    @overload
    @staticmethod
    def upsert_many(query: MyTableInsertManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def upsert_many(*, data: List[MyTableSubset]) -> MyTableQueryResults: ...

    @staticmethod
    def upsert_many(*args, **kwargs) -> MyTableQueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        if len(data) > 1000:
            raise ValueError("Cannot upsert more than 1000 rows at a time.")
        return execute_query(MyTable.table_id, "upsert", query)

    @overload
    @staticmethod
    def upsert_one(query: MyTableInsertOneQuery) -> MyTableRow: ...
    @overload
    @staticmethod
    def upsert_one(*, data: MyTableSubset) -> MyTableRow: ...

    @staticmethod
    def upsert_one(*args, **kwargs) -> MyTableRow:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return first_result(execute_query(MyTable.table_id, "upsert", { 'data': [query['data']] }))

    @overload
    @staticmethod
    def update_many(query: MyTableUpdateManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def update_many(*, where: Optional[MyTableWhereFilter], data: MyTableSubset) -> MyTableQueryResults: ...

    @staticmethod
    def update_many(*args, **kwargs) -> MyTableQueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query(MyTable.table_id, "update", transform_query(query))

    @overload
    @staticmethod
    def delete_many(query: MyTableDeleteQuery) -> PolyDeleteResults: ...
    @overload
    @staticmethod
    def delete_many(*, where: Optional[MyTableWhereFilter]) -> PolyDeleteResults: ...

    @staticmethod
    def delete_many(*args, **kwargs) -> PolyDeleteResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query(MyTable.table_id, "delete", query)
'''

TABLE_SPEC_COMPLEX = {
    "type": "table",
    "id": "123456789",
    "name": "MyTable",
    "context": "some.context.here",
    "contextName": "some.context.here.MyTable",
    "schema": {
        "$schema": "http://json-schema.org/draft-06/schema#",
        "type": "object",
        "properties": {
            "id": { "type": "string" },
            "createdAt": { "type": "string" },
            "updatedAt": { "type": "string" },
            "data": {
                "type": "object",
                "properties": {
                    "foo": { "type": "string" },
                    "nested": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": { "name": { "type": "string" } },
                            "required": ["name"]
                        }
                    },
                    "other": { "x-poly-ref": { "path": "some.other.Schema" }}
                }
            }
        },
        "required": [
            "id",
            "createdAt",
            "updatedAt",
            "data"
        ],
        "additionalProperties": False,
    }
}

EXPECTED_COMPLEX = '''
MyTableColumns = Literal["id","createdAt","updatedAt","data"]



class MyTableRow(TypedDict, total=False):
    id: Required[str]
    """ Required property """

    createdAt: Required[str]
    """ Required property """

    updatedAt: Required[str]
    """ Required property """

    data: Required["_MyTableRowdata"]
    """ Required property """



class _MyTableRowdata(TypedDict, total=False):
    foo: str
    nested: list["_MyTableRowdatanesteditem"]
    other: str | int | float | dict[str, Any] | list[Any] | bool | None
    """
    x-poly-ref:
      path: some.other.Schema
    """



class _MyTableRowdatanesteditem(TypedDict, total=False):
    name: Required[str]
    """ Required property """



class MyTableSubset(TypedDict):
    id: NotRequired[str]
    createdAt: NotRequired[str]
    updatedAt: NotRequired[str]
    data: NotRequired["_MyTableRowdata"]



class MyTableWhereFilter(TypedDict):
    id: NotRequired[Union[str, StringFilter]]
    createdAt: NotRequired[Union[str, StringFilter]]
    updatedAt: NotRequired[Union[str, StringFilter]]
    AND: NotRequired[Union["MyTableWhereFilter", List["MyTableWhereFilter"]]]
    OR: NotRequired[List["MyTableWhereFilter"]]
    NOT: NotRequired[Union["MyTableWhereFilter", List["MyTableWhereFilter"]]]



class MyTableSelectManyQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]
    order_by: NotRequired[Dict[MyTableColumns, SortOrder]]
    limit: NotRequired[int]
    offset: NotRequired[int]



class MyTableSelectOneQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]
    order_by: NotRequired[Dict[MyTableColumns, SortOrder]]



class MyTableInsertOneQuery(TypedDict):
    data: MyTableSubset



class MyTableInsertManyQuery(TypedDict):
    data: List[MyTableSubset]



class MyTableUpdateManyQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]
    data: MyTableSubset



class MyTableDeleteQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]



class MyTableQueryResults(TypedDict):
    results: List[MyTableRow]
    pagination: None # Pagination not yet supported



class MyTableCountQuery(TypedDict):
    where: NotRequired[MyTableWhereFilter]



class MyTable:
    table_id = "123456789"

    @overload
    @staticmethod
    def count(query: MyTableCountQuery) -> PolyCountResult: ...
    @overload
    @staticmethod
    def count(*, where: Optional[MyTableWhereFilter]) -> PolyCountResult: ...

    @staticmethod
    def count(*args, **kwargs) -> PolyCountResult:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query(MyTable.table_id, "count", transform_query(query))

    @overload
    @staticmethod
    def select_many(query: MyTableSelectManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def select_many(*, where: Optional[MyTableWhereFilter], order_by: Optional[Dict[MyTableColumns, SortOrder]], limit: Optional[int], offset: Optional[int]) -> MyTableQueryResults: ...

    @staticmethod
    def select_many(*args, **kwargs) -> MyTableQueryResults:
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
        return execute_query(MyTable.table_id, "select", transform_query(query))

    @overload
    @staticmethod
    def select_one(query: MyTableSelectOneQuery) -> MyTableRow: ...
    @overload
    @staticmethod
    def select_one(*, where: Optional[MyTableWhereFilter], order_by: Optional[Dict[MyTableColumns, SortOrder]]) -> MyTableRow: ...

    @staticmethod
    def select_one(*args, **kwargs) -> MyTableRow:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        query['limit'] = 1
        return first_result(execute_query(MyTable.table_id, "select", transform_query(query)))

    @overload
    @staticmethod
    def insert_many(query: MyTableInsertManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def insert_many(*, data: List[MyTableSubset]) -> MyTableQueryResults: ...

    @staticmethod
    def insert_many(*args, **kwargs) -> MyTableQueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        if len(query['data']) > 1000:
            raise ValueError("Cannot insert more than 1000 rows at a time.")
        return execute_query(MyTable.table_id, "insert", query)

    @overload
    @staticmethod
    def insert_one(query: MyTableInsertOneQuery) -> MyTableRow: ...
    @overload
    @staticmethod
    def insert_one(*, data: MyTableSubset) -> MyTableRow: ...

    @staticmethod
    def insert_one(*args, **kwargs) -> MyTableRow:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return first_result(execute_query(MyTable.table_id, "insert", { 'data': [query['data']] }))

    @overload
    @staticmethod
    def upsert_many(query: MyTableInsertManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def upsert_many(*, data: List[MyTableSubset]) -> MyTableQueryResults: ...

    @staticmethod
    def upsert_many(*args, **kwargs) -> MyTableQueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        if len(data) > 1000:
            raise ValueError("Cannot upsert more than 1000 rows at a time.")
        return execute_query(MyTable.table_id, "upsert", query)

    @overload
    @staticmethod
    def upsert_one(query: MyTableInsertOneQuery) -> MyTableRow: ...
    @overload
    @staticmethod
    def upsert_one(*, data: MyTableSubset) -> MyTableRow: ...

    @staticmethod
    def upsert_one(*args, **kwargs) -> MyTableRow:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return first_result(execute_query(MyTable.table_id, "upsert", { 'data': [query['data']] }))

    @overload
    @staticmethod
    def update_many(query: MyTableUpdateManyQuery) -> MyTableQueryResults: ...
    @overload
    @staticmethod
    def update_many(*, where: Optional[MyTableWhereFilter], data: MyTableSubset) -> MyTableQueryResults: ...

    @staticmethod
    def update_many(*args, **kwargs) -> MyTableQueryResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query(MyTable.table_id, "update", transform_query(query))

    @overload
    @staticmethod
    def delete_many(query: MyTableDeleteQuery) -> PolyDeleteResults: ...
    @overload
    @staticmethod
    def delete_many(*, where: Optional[MyTableWhereFilter]) -> PolyDeleteResults: ...

    @staticmethod
    def delete_many(*args, **kwargs) -> PolyDeleteResults:
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError("Expected query as a single argument or as kwargs")
            query = args[0]
        else:
            query = kwargs
        return execute_query(MyTable.table_id, "delete", query)
'''

class T(unittest.TestCase):
    def test_render_simple(self):
        self.maxDiff = 20000
        output = _render_table(TABLE_SPEC_SIMPLE)
        self.assertEqual(output, EXPECTED_SIMPLE)
    
    def test_render_complex(self):
        self.maxDiff = 20000
        output = _render_table(TABLE_SPEC_COMPLEX)
        self.assertEqual(output, EXPECTED_COMPLEX)
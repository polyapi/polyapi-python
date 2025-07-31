import unittest
from polyapi.schema import clean_malformed_examples, wrapped_generate_schema_types, generate_schema_types

SCHEMA = {
    "$schema": "http://json-schema.org/draft-06/schema#",
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
    "additionalProperties": False,
    "definitions": {},
}

CHARACTER_SCHEMA = {
    "$schema": "http://json-schema.org/draft-06/schema#",
    "type": "object",
    "properties": {"CHARACTER_SCHEMA_NAME": {"description": "This is — “bad”, right?", "type": "string"}},
    "additionalProperties": False,
    "definitions": {},
}

APALEO_MALFORMED_EXAMPLE = 'from typing import List, TypedDict, Union\nfrom typing_extensions import Required\n\n\n# Body.\n# \n# example: {\n  "from": "2024-04-21",\n  "to": "2024-04-24",\n  "grossDailyRate": {\n    "amount": 160.0,\n    "currency": "EUR"\n  },\n  "timeSlices": [\n    {\n      "blockedUnits": 3\n    },\n    {\n      "blockedUnits": 0\n    },\n    {\n      "blockedUnits": 7\n    }\n  ]\n}\n# x-readme-ref-name: ReplaceBlockModel\nBody = TypedDict(\'Body\', {\n    # Start date and time from which the inventory will be blockedSpecify either a pure date or a date and time (without fractional second part) in UTC or with UTC offset as defined in <a href="https://en.wikipedia.org/wiki/ISO_8601">ISO8601:2004</a>\n    # \n    # Required property\n    \'from\': Required[str],\n    # End date and time until which the inventory will be blocked. Cannot be more than 5 years after the start date.Specify either a pure date or a date and time (without fractional second part) in UTC or with UTC offset as defined in <a href="https://en.wikipedia.org/wiki/ISO_8601">ISO8601:2004</a>\n    # \n    # Required property\n    \'to\': Required[str],\n    # x-readme-ref-name: MonetaryValueModel\n    # \n    # Required property\n    \'grossDailyRate\': Required["_BodygrossDailyRate"],\n    # The list of time slices\n    # \n    # Required property\n    \'timeSlices\': Required[List["_BodytimeSlicesitem"]],\n}, total=False)\n\n\nclass _BodygrossDailyRate(TypedDict, total=False):\n    """ x-readme-ref-name: MonetaryValueModel """\n\n    amount: Required[Union[int, float]]\n    """\n    format: double\n\n    Required property\n    """\n\n    currency: Required[str]\n    """ Required property """\n\n\n\nclass _BodytimeSlicesitem(TypedDict, total=False):\n    """ x-readme-ref-name: CreateBlockTimeSliceModel """\n\n    blockedUnits: Required[Union[int, float]]\n    """\n    Number of units blocked for the time slice\n\n    format: int32\n\n    Required property\n    """\n\n'


class T(unittest.TestCase):
    def test_fix_titles(self):
        output = wrapped_generate_schema_types(SCHEMA, "", "Dict")
        self.assertEqual("MyDict", output[0])
        self.assertIn("class MyDict", output[1])

        # should not throw with unknown dialect error

    def test_clean_malformed_examples(self):
        output = clean_malformed_examples(APALEO_MALFORMED_EXAMPLE)
        self.assertNotIn("# example: {", output)
    
    def test_character_encoding(self):
        output = generate_schema_types(CHARACTER_SCHEMA, "Dict")
        expected = 'from typing import TypedDict\n\n\nclass Dict(TypedDict, total=False):\n    CHARACTER_SCHEMA_NAME: str\n    """ This is — “bad”, right? """\n\n'
        self.assertEqual(output, expected)
        
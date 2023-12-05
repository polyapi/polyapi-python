import unittest

from polyapi.api import render_function

ACCUWEATHER = {
    "id": "f7588018-2364-4586-b60d-b08a285f1ea3",
    "name": "accuweatherGetlocation",
    "context": "",
    "description": "",
    "type": "apiFunction",
    "function": {
        "arguments": [
            {
                "name": "locationId",
                "description": "",
                "type": {"kind": "primitive", "type": "integer"},
                "required": True,
            },
            {
                "name": "AAPIKey",
                "description": "",
                "type": {"kind": "primitive", "type": "string"},
                "required": True,
            },
        ],
        "returnType": {"kind": "void"},
    },
}


ZILLOW = {
    "id": "1231234",
    "name": "zillowGetLocation",
    "context": "",
    "description": "",
    "type": "apiFunction",
    "function": {
        "arguments": [
            {
                "name": "locationId",
                "description": "",
                "type": {"kind": "primitive", "type": "integer"},
                "required": True,
            },
            {
                "name": "AAPIKey",
                "description": "",
                "type": {"kind": "primitive", "type": "string"},
                "required": True,
            },
        ],
        "returnType": {"kind": "primitive", "type": "string"},
    },
}

TWILIO = {
    "id": "1203t8j342",
    "type": "apiFunction",
    "context": "twilio.conversations.messages",
    "name": "get",
    "description": "This API call retrieves messages from a specific conversation in Twilio. The messages are returned in descending order. The response includes message details such as body, author, date updated, and more. For more details: https://www.twilio.com/docs/conversations/api/conversation-message-resource#list-all-conversation-messages",
    "function": {
        "arguments": [
            {
                "name": "conversationSID",
                "description": "This is a string that represents the unique identifier of the specific conversation from which messages are to be retrieved.",
                "required": True,
                "type": {"kind": "primitive", "type": "string"},
            },
            {
                "name": "authToken",
                "description": "",
                "required": True,
                "type": {"kind": "primitive", "type": "string"},
            },
        ],
        "returnType": {
            "kind": "object",
            "schema": {
                "$schema": "http://json-schema.org/draft-06/schema#",
                "definitions": {
                    "Message": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "index": {"type": "integer"},
                            "date_updated": {
                                "type": "string",
                                "format": "date-time",
                            },
                            "media": {"type": "null"},
                            "participant_sid": {"type": "null"},
                            "delivery": {"type": "null"},
                            "url": {
                                "type": "string",
                                "format": "uri",
                                "qt-uri-protocols": ["https"],
                            },
                            "date_created": {
                                "type": "string",
                                "format": "date-time",
                            },
                            "content_sid": {
                                "anyOf": [{"type": "null"}, {"type": "string"}]
                            },
                            "sid": {"type": "string"},
                            "Attributes": {
                                "type": "string",
                                "enum": ["{'key':'value'}", "{}"],
                                "title": "Attributes",
                            },
                        },
                    }
                },
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/Message"},
                    }
                },
                "required": ["messages"],
                "title": "ResponseType",
            },
        },
    },
}


class T(unittest.TestCase):
    def test_render_function_accuweather(self):
        func_str = render_function(
            ACCUWEATHER["type"],
            ACCUWEATHER["name"],
            ACCUWEATHER["id"],
            ACCUWEATHER["function"]["arguments"],
            ACCUWEATHER["function"]["returnType"],
        )
        self.assertIn(ACCUWEATHER["id"], func_str)
        self.assertIn("locationId: int,", func_str)
        self.assertIn("-> None", func_str)

    def test_render_function_zillow(self):
        func_str = render_function(
            ZILLOW["type"],
            ZILLOW["name"],
            ZILLOW["id"],
            ZILLOW["function"]["arguments"],
            ZILLOW["function"]["returnType"],
        )
        self.assertIn(ZILLOW["id"], func_str)
        self.assertIn("locationId: int,", func_str)
        self.assertIn("-> str", func_str)

    def test_render_function_twilio(self):
        func_str = render_function(
            TWILIO["type"],
            TWILIO["name"],
            TWILIO["id"],
            TWILIO["function"]["arguments"],
            TWILIO["function"]["returnType"],
        )
        print(func_str)
        self.assertIn(TWILIO["id"], func_str)
        self.assertIn("conversationSID: str", func_str)
        self.assertIn("authToken: str", func_str)
        self.assertIn("-> Responsetype", func_str)

    # TODO figure out how to fix `polyapi.test.getProductsCount111`
    # TODO figure out how to fix `polyapi.twilio.conversation.get`
    # there is something here with quotes in Literal fields that blows up
    # polyapi/poly/_getProductsCount44.py:19:34: F821 undefined name 'Responsetype'
    # polyapi/poly/hubspot/companies/_createAdvanced.py:137:70: F821 undefined name 'unknown'
    # flake8 polyapi/poly/ --extend-ignore="W291,F401,E303,F811,E501,E402"

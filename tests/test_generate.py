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

GET_PRODUCTS_COUNT = {
    "id": "8f7d24b0-4a29-40c0-9091-b3d773c748fb",
    "type": "serverFunction",
    "context": "test",
    "name": "getProductsCount111",
    "description": "An API call to retrieve the count of products in the product list.",
    "requirements": ["snabbdom"],
    "function": {
        "arguments": [
            {
                "name": "products",
                "required": False,
                "type": {
                    "kind": "array",
                    "items": {"kind": "primitive", "type": "string"},
                },
            }
        ],
        "returnType": {"kind": "plain", "value": "number"},
        "synchronous": True,
    },
    "code": "",
    "language": "javascript",
    "visibilityMetadata": {"visibility": "ENVIRONMENT"},
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
        self.assertIn("-> ApiFunctionResponse", func_str)

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
        self.assertIn("-> ApiFunctionResponse", func_str)

    def test_render_function_twilio_api(self):
        func_str = render_function(
            TWILIO["type"],
            TWILIO["name"],
            TWILIO["id"],
            TWILIO["function"]["arguments"],
            TWILIO["function"]["returnType"],
        )
        self.assertIn(TWILIO["id"], func_str)
        self.assertIn("conversationSID: str", func_str)
        self.assertIn("authToken: str", func_str)
        self.assertIn("-> ApiFunctionResponse", func_str)

    def test_render_function_twilio_server(self):
        # same test but try it as a serverFunction rather than an apiFunction
        func_str = render_function(
            "serverFunction",
            TWILIO["name"],
            TWILIO["id"],
            TWILIO["function"]["arguments"],
            TWILIO["function"]["returnType"],
        )
        self.assertIn(TWILIO["id"], func_str)
        self.assertIn("conversationSID: str", func_str)
        self.assertIn("authToken: str", func_str)
        self.assertIn("-> Responsetype", func_str)

    def test_render_function_get_products_count(self):
        return_type = GET_PRODUCTS_COUNT["function"]["returnType"]
        func_str = render_function(
            GET_PRODUCTS_COUNT["type"],
            GET_PRODUCTS_COUNT["name"],
            GET_PRODUCTS_COUNT["id"],
            GET_PRODUCTS_COUNT["function"]["arguments"],
            return_type,
        )
        self.assertIn(GET_PRODUCTS_COUNT["id"], func_str)
        self.assertIn("products: List[str]", func_str)
        self.assertIn("-> float", func_str)
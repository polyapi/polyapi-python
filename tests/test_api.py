import unittest

from polyapi.api import render_api_function

ACCUWEATHER = {
    "id": "f7588018-2364-4586-b60d",
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

TWILIO_GET_DETAILS = {
    "id": "123abcde",
    "type": "apiFunction",
    "context": "OOB.twilio.messages",
    "name": "getDetails",
    "description": "Retrieves a message from a specific Twilio account. The API call includes parameters for the 'to' and 'from' phone numbers, and the date the message was sent. For more details: https://www.twilio.com/docs/sms/api/message-resource#fetch-a-message-resource",
    "function": {
        "arguments": [
            {
                "name": "accountSID",
                "description": "This is a unique identifier for the Twilio account from which the message is to be retrieved. It is a string that acts as an authentication token, ensuring that the user has the necessary permissions to access the desired information.",
                "required": True,
                "type": {"kind": "primitive", "type": "string"},
            },
            {
                "name": "messageSID",
                "description": "This is a unique identifier for the specific message that is to be retrieved. It is a string that Twilio uses to track and manage every individual message that is sent or received through their platform.",
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
                    "SubresourceUris": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "media": {"type": "string"},
                            "feedback": {"type": "string"},
                        },
                        "required": ["feedback", "media"],
                        "title": "SubresourceUris",
                    }
                },
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "body": {"type": "string"},
                    "num_segments": {"type": "string", "format": "integer"},
                    "direction": {"type": "string"},
                    "from": {"type": "string"},
                    "date_updated": {"type": "string"},
                    "price": {"type": "string"},
                    "error_message": {"type": "null"},
                    "uri": {"type": "string"},
                    "account_sid": {"type": "string"},
                    "num_media": {"type": "string", "format": "integer"},
                    "to": {"type": "string"},
                    "date_created": {"type": "string"},
                    "status": {"type": "string"},
                    "sid": {"type": "string"},
                    "date_sent": {"type": "string"},
                    "messaging_service_sid": {"type": "null"},
                    "error_code": {"type": "null"},
                    "price_unit": {"type": "string"},
                    "api_version": {"type": "string", "format": "date"},
                    "subresource_uris": {"$ref": "#/definitions/SubresourceUris"},
                },
                "required": [
                    "account_sid",
                    "api_version",
                    "body",
                    "date_created",
                    "date_sent",
                    "date_updated",
                    "direction",
                    "error_code",
                    "error_message",
                    "from",
                    "messaging_service_sid",
                    "num_media",
                    "num_segments",
                    "price",
                    "price_unit",
                    "sid",
                    "status",
                    "subresource_uris",
                    "to",
                    "uri",
                ],
                "title": "ResponseType",
            },
        },
    },
}


class T(unittest.TestCase):
    def test_render_function_accuweather(self):
        name = ACCUWEATHER["name"]
        func_str, _ = render_api_function(
            ACCUWEATHER["type"],
            name,
            ACCUWEATHER["id"],
            ACCUWEATHER["description"],
            ACCUWEATHER["function"]["arguments"],
            ACCUWEATHER["function"]["returnType"],
        )
        self.assertIn(ACCUWEATHER["id"], func_str)
        self.assertIn("locationId: int,", func_str)
        self.assertIn(f"-> _{name}.{name}Response", func_str)

    def test_render_function_zillow(self):
        name = ZILLOW["name"]
        func_str, _ = render_api_function(
            ZILLOW["type"],
            name,
            ZILLOW["id"],
            ZILLOW["description"],
            ZILLOW["function"]["arguments"],
            ZILLOW["function"]["returnType"],
        )
        self.assertIn(ZILLOW["id"], func_str)
        self.assertIn("locationId: int,", func_str)
        self.assertIn(f"-> _{name}.{name}Response", func_str)

    def test_render_function_twilio_api(self):
        name = TWILIO["name"]
        func_str, _ = render_api_function(
            TWILIO["type"],
            TWILIO["name"],
            TWILIO["id"],
            TWILIO["description"],
            TWILIO["function"]["arguments"],
            TWILIO["function"]["returnType"],
        )
        self.assertIn(TWILIO["id"], func_str)
        self.assertIn("conversationSID: str", func_str)
        self.assertIn("authToken: str", func_str)
        self.assertIn(f"-> _{name}.{name}Response", func_str)

    def test_render_function_twilio_get_details(self):
        # same test but try it as a serverFunction rather than an apiFunction
        name = TWILIO_GET_DETAILS["name"]
        func_str, func_type_defs = render_api_function(
            TWILIO_GET_DETAILS["type"],
            TWILIO_GET_DETAILS["name"],
            TWILIO_GET_DETAILS["id"],
            TWILIO_GET_DETAILS["description"],
            TWILIO_GET_DETAILS["function"]["arguments"],
            TWILIO_GET_DETAILS["function"]["returnType"],
        )
        self.assertIn(TWILIO_GET_DETAILS["id"], func_str)
        self.assertIn(f"-> _{name}.{name}Response", func_str)
        self.assertIn("class SubresourceUris", func_type_defs)
        # self.assertIn('Required["SubresourceUris"]', func_type_defs)

from typing import Literal, TypedDict, Union
from typing_extensions import Required


Accountsid = Union[Literal['ACc7909001d2d0b9f8eaf5172bb0758c83']]
""" AccountSid. """
ACCOUNTSID_ACC7909001D2D0B9F8EAF5172BB0758C83: Literal['ACc7909001d2d0b9f8eaf5172bb0758c83'] = "ACc7909001d2d0b9f8eaf5172bb0758c83"
"""The values for the 'AccountSid' enum"""



Attributes = Union[Literal["{'key':'value'}"], Literal['{}']]
""" Attributes. """
ATTRIBUTES___APOSTROPHE_KEY_APOSTROPHE__COLON__APOSTROPHE_VALUE_APOSTROPHE__: Literal["{'key':'value'}"] = "{'key':'value'}"
"""The values for the 'Attributes' enum"""
ATTRIBUTES___: Literal['{}'] = "{}"
"""The values for the 'Attributes' enum"""



Author = Union[Literal["'nancy'"], Literal['system'], Literal["'user123'"]]
""" Author. """
AUTHOR__APOSTROPHE_NANCY_APOSTROPHE_: Literal["'nancy'"] = "'nancy'"
"""The values for the 'Author' enum"""
AUTHOR_SYSTEM: Literal['system'] = "system"
"""The values for the 'Author' enum"""
AUTHOR__APOSTROPHE_USER123_APOSTROPHE_: Literal["'user123'"] = "'user123'"
"""The values for the 'Author' enum"""



Body = Union[Literal["'Hello, how can I assist you?'"], Literal[''], Literal['this is a test media ']]
""" Body. """
BODY__APOSTROPHE_HELLO_COMMA__HOW_CAN_I_ASSIST_YOU_QUESTION_MARK__APOSTROPHE_: Literal["'Hello, how can I assist you?'"] = "'Hello, how can I assist you?'"
"""The values for the 'Body' enum"""
BODY_: Literal[''] = ""
"""The values for the 'Body' enum"""
BODY_THIS_IS_A_TEST_MEDIA_: Literal['this is a test media '] = "this is a test media "
"""The values for the 'Body' enum"""



Conversationsid = Union[Literal['CHd1f2051f658f4101b944876b7600768f']]
""" ConversationSid. """
CONVERSATIONSID_CHD1F2051F658F4101B944876B7600768F: Literal['CHd1f2051f658f4101b944876b7600768f'] = "CHd1f2051f658f4101b944876b7600768f"
"""The values for the 'ConversationSid' enum"""



class Links(TypedDict, total=False):
    """ Links. """

    delivery_receipts: Required[str]
    """
    format: uri

    Required property
    """

    channel_metadata: Required[str]
    """
    format: uri

    Required property
    """



class Message(TypedDict, total=False):
    """ Message. """

    body: Required["Body"]
    """
    Body.

    Required property
    """

    index: Required[int]
    """ Required property """

    author: Required["Author"]
    """
    Author.

    Required property
    """

    date_updated: Required[str]
    """
    format: date-time

    Required property
    """

    media: Required[None]
    """ Required property """

    participant_sid: Required[None]
    """ Required property """

    conversation_sid: Required["Conversationsid"]
    """
    ConversationSid.

    Required property
    """

    account_sid: Required["Accountsid"]
    """
    AccountSid.

    Required property
    """

    delivery: Required[None]
    """ Required property """

    url: Required[str]
    """
    format: uri

    Required property
    """

    date_created: Required[str]
    """
    format: date-time

    Required property
    """

    sid: Required[str]
    """ Required property """

    attributes: Required["Attributes"]
    """
    Attributes.

    Required property
    """

    links: Required["Links"]
    """
    Links.

    Required property
    """



class Meta(TypedDict, total=False):
    """ Meta. """

    page: Required[int]
    """ Required property """

    page_size: Required[int]
    """ Required property """

    first_page_url: Required[str]
    """
    format: uri

    Required property
    """

    previous_page_url: Required[None]
    """ Required property """

    url: Required[str]
    """
    format: uri

    Required property
    """

    next_page_url: Required[None]
    """ Required property """

    key: Required[str]
    """ Required property """



class Responsetype(TypedDict, total=False):
    """
    ResponseType.

    id: #main
    """

    meta: Required["Meta"]
    """
    Meta.

    Required property
    """

    message: Required["Message"]
    """
    Message.

    Required property
    """


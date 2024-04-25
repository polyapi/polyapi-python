import os
import sys
import truststore
from typing import Dict, Any
truststore.inject_into_ssl()
from .cli import CLI_COMMANDS

__all__ = ["poly"]


if len(sys.argv) > 1 and sys.argv[1] not in CLI_COMMANDS:
    currdir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(os.path.join(currdir, "poly")):
        print("No 'poly' found. Please run 'python3 -m polyapi generate' to generate the 'poly' library for your tenant.")
        sys.exit(1)


polyCustom: Dict[str, Any] = {
  "executionId": None,
  "executionApiKey": None,
  "responseStatusCode": 200,
  "responseContentType": None,
}
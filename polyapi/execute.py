import requests
from requests import Response
from polyapi.config import get_api_key_and_url
from polyapi.exceptions import PolyApiException


# TODO use this to cleanup generated code
def execute(function_type, function_id, data) -> Response:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/functions/{function_type}/{function_id}/execute"
    resp = requests.post(url, json=data, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp
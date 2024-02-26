import requests
from requests import Response
from polyapi.config import get_api_key_and_url
from polyapi.exceptions import PolyApiException


def execute(function_type, function_id, data) -> Response:
    """ execute a specific function id/type
    """
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/functions/{function_type}/{function_id}/execute"
    resp = requests.post(url, json=data, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp


def execute_post(path, data):
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.post(api_url + path, json=data, headers=headers)
    return resp


def variable_get(variable_id: str) -> Response:
    api_key, base_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/variables/{variable_id}/value"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp


def variable_update(variable_id: str, value) -> Response:
    api_key, base_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/variables/{variable_id}"
    resp = requests.patch(url, data={"value": value}, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp
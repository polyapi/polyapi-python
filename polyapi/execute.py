from typing import Dict, Optional
import requests
from requests import Response
from polyapi.config import get_api_key_and_url, get_mtls_config
from polyapi.exceptions import PolyApiException

def direct_execute(function_type, function_id, data) -> Response:
    """ execute a specific function id/type
    """
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/functions/{function_type}/{function_id}/direct-execute"
    
    endpoint_info = requests.post(url, json=data, headers=headers)
    if endpoint_info.status_code < 200 or endpoint_info.status_code >= 300:
        raise PolyApiException(f"{endpoint_info.status_code}: {endpoint_info.content.decode('utf-8', errors='ignore')}")
    
    endpoint_info_data = endpoint_info.json()
    request_params = endpoint_info_data.copy()
    request_params.pop("url", None)
    
    if "maxRedirects" in request_params:
        request_params["allow_redirects"] = request_params.pop("maxRedirects") > 0
    
    has_mtls, cert_path, key_path, ca_path = get_mtls_config()
    
    if has_mtls:
        resp = requests.request(
            url=endpoint_info_data["url"],
            cert=(cert_path, key_path),
            verify=ca_path,
            **request_params
        )
    else:
        resp = requests.request(
            url=endpoint_info_data["url"],
            verify=False,
            **request_params
        )

    if resp.status_code < 200 or resp.status_code >= 300:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    
    return resp

def execute(function_type, function_id, data) -> Response:
    """ execute a specific function id/type
    """
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}

    url = f"{api_url}/functions/{function_type}/{function_id}/execute"
    
    # Make the request
    resp = requests.post(
        url, 
        json=data, 
        headers=headers,
    )

    if resp.status_code < 200 or resp.status_code >= 300:
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
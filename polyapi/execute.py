from typing import Dict, Optional
import requests
from requests import Response
import ssl
import certifi
from polyapi.config import get_api_key_and_url, get_mtls_config, get_direct_execute_config
from polyapi.exceptions import PolyApiException


def _create_https_agent() -> Optional[ssl.SSLContext]:
    """Create an SSL context with MTLS if configured"""
    has_mtls, cert_path, key_path, ca_path = get_mtls_config()
    if not has_mtls:
        return None

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    if ca_path:
        ssl_context.load_verify_locations(cafile=ca_path)
    return ssl_context


def execute(function_type, function_id, data) -> Response:
    """ execute a specific function id/type
    """
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Check if direct execute is enabled - only for API functions
    if function_type == 'api' and get_direct_execute_config():
        # Get the direct endpoint from the specs
        specs_url = f"{api_url}/specs"
        specs_resp = requests.get(specs_url, headers=headers)
        if specs_resp.status_code < 200 or specs_resp.status_code >= 300:
            raise PolyApiException(f"Failed to get specs: {specs_resp.status_code}")
        
        specs_data = specs_resp.json()
        direct_endpoint = specs_data.get("direct_endpoint")
        if not direct_endpoint:
            raise PolyApiException("Direct endpoint not found in specs response")
        
        url = f"{direct_endpoint}/functions/{function_type}/{function_id}/execute"
    else:
        url = f"{api_url}/functions/{function_type}/{function_id}/execute"

    # Create SSL context if MTLS is configured - only for API function execute calls
    ssl_context = None
    if function_type == 'api':
        ssl_context = _create_https_agent()
    
    # Make the request
    resp = requests.post(
        url, 
        json=data, 
        headers=headers,
        verify=ssl_context if ssl_context else True
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
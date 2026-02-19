import httpx
import os
import logging
from polyapi.config import get_api_key_and_url, get_mtls_config
from polyapi.exceptions import PolyApiException
from polyapi import http_client

logger = logging.getLogger("poly")

def _check_response_error(resp, function_type, function_id, data):
    if resp.status_code < 200 or resp.status_code >= 300:
        error_content = resp.content.decode("utf-8", errors="ignore")
        if function_type == 'api' and os.getenv("LOGS_ENABLED"):
            logger.error(f"Error executing api function with id: {function_id}. Status code: {resp.status_code}. Request data: {data}, Response: {error_content}")
        elif function_type != 'api':
            raise PolyApiException(f"{resp.status_code}: {error_content}")


def _check_endpoint_error(resp, function_type, function_id, data):
    if resp.status_code < 200 or resp.status_code >= 300:
        error_content = resp.content.decode("utf-8", errors="ignore")
        if function_type == 'api' and os.getenv("LOGS_ENABLED"):
            raise PolyApiException(f"Error executing api function with id: {function_id}. Status code: {resp.status_code}. Request data: {data}, Response: {error_content}")
        elif function_type != 'api':
            raise PolyApiException(f"{resp.status_code}: {error_content}")


def _build_direct_execute_params(endpoint_info_data):
    request_params = endpoint_info_data.copy()
    request_params.pop("url", None)
    if "maxRedirects" in request_params:
        request_params["follow_redirects"] = request_params.pop("maxRedirects") > 0
    return request_params


def _sync_direct_execute(function_type, function_id, data) -> httpx.Response:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/functions/{function_type}/{function_id}/direct-execute"

    endpoint_info = http_client.post(url, json=data, headers=headers)
    _check_endpoint_error(endpoint_info, function_type, function_id, data)

    endpoint_info_data = endpoint_info.json()
    request_params = _build_direct_execute_params(endpoint_info_data)

    has_mtls, cert_path, key_path, ca_path = get_mtls_config()

    # Direct-execute hits URL that may need custom TLS
    # settings (mTLS certs or disabled verification). httpx Client.request()
    # doesn't accept per-request transport kwargs, so use one-off calls.
    if has_mtls:
        resp = httpx.request(
            url=endpoint_info_data["url"],
            cert=(cert_path, key_path),
            verify=ca_path,
            timeout=None,
            **request_params
        )
    else:
        resp = httpx.request(
            url=endpoint_info_data["url"],
            verify=False,
            timeout=None,
            **request_params
        )

    _check_response_error(resp, function_type, function_id, data)
    return resp


async def _async_direct_execute(function_type, function_id, data) -> httpx.Response:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/functions/{function_type}/{function_id}/direct-execute"

    endpoint_info = await http_client.async_post(url, json=data, headers=headers)
    _check_endpoint_error(endpoint_info, function_type, function_id, data)

    endpoint_info_data = endpoint_info.json()
    request_params = _build_direct_execute_params(endpoint_info_data)

    has_mtls, cert_path, key_path, ca_path = get_mtls_config()

    # One-off async client for custom TLS settings on external URLs.
    if has_mtls:
        async with httpx.AsyncClient(
            cert=(cert_path, key_path), verify=ca_path, timeout=None
        ) as client:
            resp = await client.request(
                url=endpoint_info_data["url"], **request_params
            )
    else:
        async with httpx.AsyncClient(verify=False, timeout=None) as client:
            resp = await client.request(
                url=endpoint_info_data["url"], **request_params
            )

    _check_response_error(resp, function_type, function_id, data)
    return resp


def direct_execute(function_type, function_id, data) -> httpx.Response:
    """ execute a specific function id/type (sync)
    """
    return _sync_direct_execute(function_type, function_id, data)


async def direct_execute_async(function_type, function_id, data) -> httpx.Response:
    """ execute a specific function id/type (async)
    """
    return await _async_direct_execute(function_type, function_id, data)


def _sync_execute(function_type, function_id, data) -> httpx.Response:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/functions/{function_type}/{function_id}/execute"

    resp = http_client.post(url, json=data, headers=headers)
    _check_response_error(resp, function_type, function_id, data)
    return resp


async def _async_execute(function_type, function_id, data) -> httpx.Response:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/functions/{function_type}/{function_id}/execute"

    resp = await http_client.async_post(url, json=data, headers=headers)
    _check_response_error(resp, function_type, function_id, data)
    return resp


def execute(function_type, function_id, data) -> httpx.Response:
    """ execute a specific function id/type (sync)
    """
    return _sync_execute(function_type, function_id, data)


async def execute_async(function_type, function_id, data) -> httpx.Response:
    """ execute a specific function id/type (async)
    """
    return await _async_execute(function_type, function_id, data)


def _sync_execute_post(path, data):
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    return http_client.post(api_url + path, json=data, headers=headers)


async def _async_execute_post(path, data):
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    return await http_client.async_post(api_url + path, json=data, headers=headers)


def execute_post(path, data):
    return _sync_execute_post(path, data)


async def execute_post_async(path, data):
    return await _async_execute_post(path, data)


def _sync_variable_get(variable_id: str) -> httpx.Response:
    api_key, base_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/variables/{variable_id}/value"
    resp = http_client.get(url, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp


async def _async_variable_get(variable_id: str) -> httpx.Response:
    api_key, base_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/variables/{variable_id}/value"
    resp = await http_client.async_get(url, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp


def variable_get(variable_id: str) -> httpx.Response:
    return _sync_variable_get(variable_id)


async def variable_get_async(variable_id: str) -> httpx.Response:
    return await _async_variable_get(variable_id)


def _sync_variable_update(variable_id: str, value) -> httpx.Response:
    api_key, base_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/variables/{variable_id}"
    resp = http_client.patch(url, data={"value": value}, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp


async def _async_variable_update(variable_id: str, value) -> httpx.Response:
    api_key, base_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/variables/{variable_id}"
    resp = await http_client.async_patch(url, data={"value": value}, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        error_content = resp.content.decode("utf-8", errors="ignore")
        raise PolyApiException(f"{resp.status_code}: {error_content}")
    return resp


def variable_update(variable_id: str, value) -> httpx.Response:
    return _sync_variable_update(variable_id, value)


async def variable_update_async(variable_id: str, value) -> httpx.Response:
    return await _async_variable_update(variable_id, value)

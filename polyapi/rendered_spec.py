import os
from typing import Optional

import requests
from polyapi.config import get_api_key_and_url
from polyapi.generate import read_cached_specs, render_spec
from polyapi.typedefs import SpecificationDto


def update_rendered_spec(api_key: str, spec: SpecificationDto):
    print("Updating rendered spec...")
    func_str, type_defs = render_spec(spec)
    data = {
        "language": "python",
        "signature": func_str,
        "typedefs": type_defs,
    }
    if spec["type"] == "apiFunction":
        data["apiFunctionId"] = spec["id"]
    elif spec["type"] == "serverFunction":
        data["customFunctionId"] = spec["id"]
    elif spec["type"] == "clientFunction":
        data["customFunctionId"] = spec["id"]
    elif spec["type"] == "webhookHandle":
        data["webhookHandleId"] = spec["id"]
    else:
        raise NotImplementedError("todo")

    # use super key on develop-k8s here!
    _, base_url = get_api_key_and_url()
    if not base_url:
        base_url = os.environ.get("HOST_URL")

    url = f"{base_url}/functions/rendered-specs"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.post(url, json=data, headers=headers)
    assert resp.status_code == 201, (resp.text, resp.status_code)


def _get_spec(api_key: str, spec_id: str) -> Optional[SpecificationDto]:
    _, base_url = get_api_key_and_url()
    if not base_url:
        base_url = os.environ.get("HOST_URL")

    url = f"{base_url}/specs"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        specs = resp.json()
        for spec in specs:
            if spec['id'] == spec_id:
                return spec
        return None
    else:
        raise NotImplementedError(resp.content)


def get_and_update_rendered_spec(api_key: str, spec_id: str) -> bool:
    spec = _get_spec(api_key, spec_id)
    if spec:
        update_rendered_spec(api_key, spec)
        return True
    return False


def save_rendered_specs() -> None:
    specs = read_cached_specs()
    # right now we just support rendered apiFunctions
    api_specs = [spec for spec in specs if spec["type"] == "apiFunction"]
    for spec in api_specs:
        assert spec["function"]
        print("adding", spec["context"], spec["name"])
        update_rendered_spec("FIXME", spec)

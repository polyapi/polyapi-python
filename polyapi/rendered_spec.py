from typing import Dict
from polyapi.generate import read_cached_specs, render_spec
from polyapi.execute import execute_post
from polyapi.typedefs import SpecificationDto


def update_rendered_spec(spec: SpecificationDto):
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
    else:
        raise NotImplementedError("todo")

    resp = execute_post("/functions/rendered-specs", data)
    assert resp.status_code == 201, (resp.text, resp.status_code)
    # this needs to run with something like `kn func run...`


def save_rendered_specs() -> None:
    specs = read_cached_specs()
    # right now we just support rendered apiFunctions
    api_specs = [spec for spec in specs if spec["type"] == "apiFunction"]
    for spec in api_specs:
        assert spec["function"]
        print("adding", spec["context"], spec["name"])
        update_rendered_spec(spec)

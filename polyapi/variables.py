import os

from polyapi.utils import append_init


TEMPLATE = """
import requests
from polyapi.config import get_api_key, get_api_base_url
from polyapi.exceptions import PolyApiException


class {variable_name}:
    @staticmethod
    def get():
        secret = {secret}
        if secret:
            raise ValueError('Cannot access secret variable from client. Use .inject() instead within Poly function.')
        else:
            base_url = get_api_base_url()
            api_key = get_api_key()
            headers = {{"Authorization": f"Bearer {{api_key}}"}}
            url = f"{{base_url}}/variables/{variable_id}/value"
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200 and resp.status_code != 201:
                raise PolyApiException(f"{{resp.status_code}}: {{resp.content}}")
            return resp.text

    @staticmethod
    def update(value):
        base_url = get_api_base_url()
        api_key = get_api_key()
        headers = {{"Authorization": f"Bearer {{api_key}}"}}
        url = f"{{base_url}}/variables/{variable_id}"
        resp = requests.patch(url, data={{"value": value}}, headers=headers)
        if resp.status_code != 200 and resp.status_code != 201:
            raise PolyApiException(f"{{resp.status_code}}: {{resp.content}}")
        return resp.json()

    def inject(path=None):
        return {{
            "type": "PolyVariable",
            "id": "{variable_id}",
            "path": path,
        }}
"""


def generate_variables(variables):
    for variable in variables:
        create_variable(*variable)
    print("Variables generated!")


def add_variable_file(full_path: str, variable_name: str, variable_id: str, secret: str):
    # first lets add the import to the __init__
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a") as f:
        f.write(f"from ._{variable_name} import {variable_name}\n")

    # now lets add the code!
    file_path = os.path.join(full_path, f"_{variable_name}.py")
    with open(file_path, "w") as f:
        f.write(
            TEMPLATE.format(
                variable_name=variable_name,
                variable_id=variable_id,
                secret=secret,
            )
        )


def create_variable(path: str, variable_id: str, secret: str) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))

    folders = path.split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            variable_name = folder
            add_variable_file(full_path, variable_name, variable_id, secret)
        else:
            full_path = os.path.join(full_path, folder)
            if not os.path.exists(full_path):
                os.makedirs(full_path)

            # append to __init__.py file if nested folders
            next = folders[idx + 1] if idx + 2 < len(folders) else ""
            if next:
                append_init(full_path, next)
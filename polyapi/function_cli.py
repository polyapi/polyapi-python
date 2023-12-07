import requests
from polyapi.config import get_api_key_and_url


def _parse_arguments(*args):
    return args


def function_add_or_update(*args):
    if not args or not args[0] == "add":
        print(
            "Please provide a subcommand. The only available subcommand is 'add' currently, which can be used to both add and update."
        )
        exit(1)
    data = _parse_arguments(*args)
    base_url, key = get_api_key_and_url()
    base_url = "https://example.com"  # hack for testing
    # TODO add key
    resp = requests.post(f"{base_url}/functions", json=data)
    if resp.status_code == 200:
        print("Function added successfully.")
    else:
        print("Error adding function.")
        print(resp.status_code)
        print(resp.content)
        exit(1)
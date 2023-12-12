import argparse
import requests
from polyapi.config import get_api_key_and_url


def function_add_or_update(context, description, server, subcommands):
    print(context)
    print(description)
    print(server)
    print(subcommands)

    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", choices=["add"])
    parser.add_argument("function_name")
    parser.add_argument("filename")
    args = parser.parse_args(subcommands)
    print(args)
    return

    base_url, key = get_api_key_and_url()
    base_url = "https://example.com"  # hack for testing
    # TODO add key
    data = {}
    resp = requests.post(f"{base_url}/functions", json=data)
    if resp.status_code == 200:
        print("Function added successfully.")
    else:
        print("Error adding function.")
        print(resp.status_code)
        print(resp.content)
        exit(1)
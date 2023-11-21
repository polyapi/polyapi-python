import os


def get_api_key():
    return os.environ.get("POLY_API_KEY")


def get_api_base_url():
    return os.environ.get("POLY_API_BASE_URL")
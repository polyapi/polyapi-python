# import os
# import requests
# from polyapi.config import get_api_key, get_api_base_url


# class functions:
#     class api:
#         @classmethod
#         def list(cls):
#             function_id = "504f9b27-74db-4e1f-bef9-2400ddd3f779"
#             api_key = get_api_key()
#             headers = {"Authorization": f"Bearer {api_key}"}
#             url = f"{get_api_base_url()}/functions/api/{function_id}/execute"
#             data = {"instanceId": "develop-k8s", "polyApiKey": os.environ.get("HACKY_SECRET")}
#             resp = requests.post(url, data=data, headers=headers)
#             assert resp.status_code == 201, resp.content
#             return resp.text
# requests.post(url, data={"token": token}
# return f"your function id is {function_id} and your token is {token}"

# requests.post()
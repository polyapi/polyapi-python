import os
from datetime import datetime
from typing import List, Dict
import requests

from polyapi.deployables import (
    prepare_deployable_directory, load_deployable_records,
    save_deployable_records, remove_deployable_records,
    get_cache_deployments_revision, write_updated_deployable,
    DeployableRecord, SyncDeployment, Deployment
)

DEPLOY_ORDER = [
    'server-function',
    'client-function',
]

def read_file(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def group_by(items: List[Dict], key: str) -> Dict[str, List[Dict]]:
    grouped = {}
    for item in items:
        grouped.setdefault(item[key], []).append(item)
    return grouped

def remove_deployable(deployable: SyncDeployment) -> bool:
    # Example function call, adjust as needed
    url = f"{deployable['instance']}/{deployable['type']}/{deployable['name']}"
    response = requests.get(url)
    if response.status_code != 200:
        return False
    requests.delete(url)
    return True

def sync_deployable_and_get_id(deployable: SyncDeployment, code: str) -> str:
    # Example function call, adjust as needed
    url = f"{deployable['instance']}/{deployable['type']}"
    print(deployable)
    payload = {
        "context": deployable["context"],
        "name": deployable["name"],
        "description": deployable["description"],
        "code": code,
        "typeSchemas": deployable["typeSchemas"],
        "config": deployable["config"]
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()['id']

def sync_deployable(deployable: SyncDeployment) -> Deployment:
    code = read_file(deployable['file'])
    id = sync_deployable_and_get_id(deployable, code)
    return {
        "name": deployable["name"],
        "context": deployable["context"],
        "instance": deployable["instance"],
        "type": deployable["type"],
        "id": id,
        "deployed": datetime.now().isoformat(),
        "fileRevision": deployable["fileRevision"],
    }

def sync_deployables(dry_run: bool, instance: str = os.getenv('POLY_API_BASE_URL')):
    prepare_deployable_directory()
    git_revision = get_cache_deployments_revision()
    all_deployables = load_deployable_records()
    to_remove: List[DeployableRecord] = []

    if not all_deployables:
        print('No deployables found. Skipping sync.')
        return

    # TODO: Improve our deploy ordering.
    # Right now we're doing rudimentary ordering by type
    # But this does not safely handle cases where one server function may reference another
    # We should parse the functions bodies for references to other Poly deployables and work them into a DAG
    grouped_deployables = group_by(all_deployables, 'type')
    for type_name in DEPLOY_ORDER:
        deployables = grouped_deployables.get(type_name, [])
        for deployable in deployables:
            previous_deployment = next((d for d in deployable.get('deployments', []) if d['instance'] == instance), None)
            git_revision_changed = git_revision != deployable['gitRevision']
            file_revision_changed = not previous_deployment or previous_deployment['fileRevision'] != deployable['fileRevision']

            action = 'REMOVED' if git_revision_changed else \
                     'ADDED' if not previous_deployment else \
                     'UPDATED' if file_revision_changed else 'OK'

            if not dry_run and (git_revision_changed or file_revision_changed):
                # Any deployable may be deployed to multiple instances/environments at the same time
                # So we reduce the deployable record down to a single instance we want to deploy to
                if previous_deployment:
                    sync_deployment = { **deployable, **previous_deployment, "instance": instance }
                else:
                    sync_deployment = { **deployable, "instance": instance }
                if git_revision == deployable['gitRevision']:
                    deployment = sync_deployable(sync_deployment)
                    print(deployment)
                    if previous_deployment:
                        previous_deployment.update(deployment)
                    else:
                        deployable['deployments'].insert(0, deployment)
                else:
                    found = remove_deployable(sync_deployment)
                    action = 'NOT FOUND' if not found else action
                    remove_index = all_deployables.index(deployable)
                    to_remove.append(all_deployables.pop(remove_index))

            print(f"{'Would sync' if dry_run else 'Synced'} {deployable['type'].replace('-', ' ')} {deployable['context']}.{deployable['name']}: {'TO BE ' if dry_run else ''}{action}")

    if dry_run:
        return

    for deployable in all_deployables:
        write_updated_deployable(deployable, True)

    save_deployable_records(all_deployables)
    if to_remove:
        remove_deployable_records(to_remove)

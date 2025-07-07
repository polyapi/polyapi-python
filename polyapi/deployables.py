import os
import subprocess
import json
import hashlib
from pathlib import Path
from typing import TypedDict, List, Dict, Tuple, Optional, Any, Union
from subprocess import check_output, CalledProcessError


# Constants
CACHE_VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployments_revision")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cached_deployables")


class DeployableTypes(str):
    pass

class DeployableTypeNames(str):
    pass

class Deployment(TypedDict):
    context: str
    name: str
    type: DeployableTypes
    instance: str
    id: str
    deployed: str
    fileRevision: str

class ParsedDeployableConfig(TypedDict):
    context: str
    name: str
    type: DeployableTypes
    description: Optional[str]
    disableAi: Optional[bool]
    config: Dict[str, Any]

class DeployableFunctionParamBase(TypedDict):
    type: str
    typeSchema: Optional[Dict[str, Any]]
    description: str

class DeployableFunctionParam(DeployableFunctionParamBase):
    name: str

class DeployableFunctionTypes(TypedDict):
    description: str
    params: List[DeployableFunctionParam]
    returns: DeployableFunctionParamBase

class DeployableRecord(ParsedDeployableConfig, total=False):
    gitRevision: str
    fileRevision: str
    file: str
    types: DeployableFunctionTypes
    typeSchemas: Dict[str, Any]
    dependencies: List[str]
    deployments: List[Deployment]
    deploymentCommentRanges: List[Tuple[int, int]]
    docStartIndex: int
    docEndIndex: int
    dirty: Optional[bool]

class SyncDeployment(TypedDict, total=False):
    context: str
    name: str
    description: str
    type: str
    fileRevision: str
    file: str
    types: DeployableFunctionTypes
    typeSchemas: Dict[str, any]
    dependencies: List[str]
    config: Dict[str, any]
    instance: str
    id: Optional[str] = None
    deployed: Optional[str] = None

DeployableTypeEntries: List[Tuple[DeployableTypeNames, DeployableTypes]] = [
    ("PolyServerFunction", "server-function"),
    ("PolyClientFunction", "client-function"),
]

DeployableTypeToName: Dict[DeployableTypeNames, DeployableTypes] = {name: type for name, type in DeployableTypeEntries}

def prepare_deployable_directory() -> None:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

def load_deployable_records() -> List[DeployableRecord]:
    return [read_json_file(os.path.join(CACHE_DIR, name)) for name in os.listdir(CACHE_DIR) if name.endswith(".json")]

def save_deployable_records(records: List[DeployableRecord]) -> None:
    for record in records:
        write_json_file(os.path.join(CACHE_DIR, f'{record["context"]}.{record["name"]}.json'), record)

def remove_deployable_records(records: List[DeployableRecord]) -> None:
    for record in records:
        os.remove(os.path.join(CACHE_DIR, f'{record["context"]}.{record["name"]}.json'))

def read_json_file(path: Union[str, Path]) -> Any:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

def write_json_file(path: Union[str, Path], contents: Any) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(contents, file, indent=2)

class PolyDeployConfig(TypedDict):
    type_names: List[str]
    include_dirs: List[str]
    include_files_or_extensions: List[str]
    exclude_dirs: List[str]

def get_all_deployable_files_windows(config: PolyDeployConfig) -> List[str]:
    # Constructing the Windows command using dir and findstr
    include_pattern = " ".join(f"*.{f}" for f in config["include_files_or_extensions"]) or "*"
    exclude_pattern = ' '.join(f"\\{f}" for f in config["exclude_dirs"])
    pattern = ' '.join(f"/C:\"polyConfig: {name}\"" for name in config["type_names"]) or '/C:"polyConfig"'

    exclude_command = f" | findstr /V /I \"{exclude_pattern}\"" if exclude_pattern else ''
    search_command = f" | findstr /M /I /F:/ {pattern}"

    result = []
    for dir_path in config["include_dirs"]:
        if dir_path != '.':
            include_pattern = " ".join(f"{dir_path}*.{f}" for f in config["include_files_or_extensions"]) or "*"
        dir_command = f"dir {include_pattern} /S /P /B"
        full_command = f"{dir_command}{exclude_command}{search_command}"
        try:
            output = subprocess.check_output(full_command, shell=True, text=True)
            result.extend(output.strip().split('\n'))
        except subprocess.CalledProcessError:
            pass
    return result

def get_all_deployable_files_linux(config: PolyDeployConfig) -> List[str]:
    # Constructing the Linux grep command
    include = " ".join(f'--include={f if "." in f else f"*.{f}"}' for f in config["include_files_or_extensions"])
    exclude_dir = " ".join(f"--exclude-dir={dir}" for dir in config["exclude_dirs"])

    search_path = " ".join(config["include_dirs"]) or "."
    patterns = " ".join(f"-e 'polyConfig: {name}'" for name in config["type_names"]) or "-e 'polyConfig'"
    grep_command = f'grep {include} {exclude_dir} -Rl {patterns} {search_path}'

    try:
        output = subprocess.check_output(grep_command, shell=True, text=True)
        return output.strip().split('\n')
    except subprocess.CalledProcessError:
        return []

def get_all_deployable_files(config: PolyDeployConfig) -> List[str]:
    # Setting default values if not provided
    if not config.get("type_names"):
        config["type_names"] = [entry[0] for entry in DeployableTypeEntries]  # Assuming DeployableTypeEntries is defined elsewhere
    if not config.get("include_dirs"):
        config["include_dirs"] = ["."]
    if not config.get("include_files_or_extensions"):
        config["include_files_or_extensions"] = ["py"]
    if not config.get("exclude_dirs"):
        config["exclude_dirs"] = ["Lib", "node_modules", "dist", "build", "output", ".vscode", ".poly", ".github", ".husky", ".yarn", ".venv"]

    is_windows = os.name == "nt"
    if is_windows:
        return get_all_deployable_files_windows(config)
    else:
        return get_all_deployable_files_linux(config)

def get_deployable_file_revision(file_contents: str) -> str:
    # Remove leading single-line comments and hash the remaining contents
    file_contents = "\n".join(line for line in file_contents.split("\n") if not line.strip().startswith("#"))
    return hashlib.sha256(file_contents.encode('utf-8')).hexdigest()[:7]

def get_git_revision(branch_or_tag: str = "HEAD") -> str:
    try:
        return check_output(["git", "rev-parse", "--short", branch_or_tag], text=True).strip()
    except CalledProcessError:
        # Return a random 7-character hash as a fallback
        return "".join(format(ord(c), 'x') for c in os.urandom(4))[:7]

def get_cache_deployments_revision() -> str:
    """Retrieve the cache deployments revision from a file."""
    try:
        with open(CACHE_VERSION_FILE, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        return ''

def write_cache_revision(git_revision: Optional[str] = None) -> None:
    if git_revision is None:
        git_revision = get_git_revision()
    with open(CACHE_VERSION_FILE, 'w', encoding='utf-8') as file:
        file.write(git_revision)

def is_cache_up_to_date() -> bool:
    if not Path(CACHE_VERSION_FILE).exists():
        return False
    with open(CACHE_VERSION_FILE, 'r', encoding='utf-8') as file:
        cached_revision = file.read().strip()
    git_revision = get_git_revision()
    return cached_revision == git_revision

def is_cache_up_to_date() -> bool:
    """Check if the cached revision matches the current Git revision."""
    cached_revision = get_cache_deployments_revision()
    git_revision = get_git_revision()  # This function needs to be defined or imported
    return cached_revision == git_revision

def write_deploy_comments(deployments: List[Dict]) -> str:
    """Generate a string of deployment comments for each deployment."""
    canopy_path = 'polyui/collections' if 'localhost' in os.getenv('POLY_API_BASE_URL', '') else 'canopy/polyui/collections'
    comments = []
    for d in deployments:
        instance_url = d['instance'].replace(':8000', ':3000') if d['instance'].endswith(':8000') else d['instance']
        comment = f"# Poly deployed @ {d['deployed']} - {d['context']}.{d['name']} - {instance_url}/{canopy_path}/{d['type']}s/{d['id']} - {d['fileRevision']}"
        comments.append(comment)
    return '\n'.join(comments)

def print_docstring_function_comment(description: str, args: list, returns: dict) -> str:
    docstring = f'"""{description}\n\n'
    if args:
        docstring += '    Args:\n'
        for arg in args:
            name = arg.get('name')
            arg_type = arg.get('type', '')
            desc = arg.get('description', '')
            if arg_type:
                docstring += f'        {name} ({arg_type}): {desc}\n'
            else:
                docstring += f'        {name}: {desc}\n'

    return_type = returns.get('type', '')
    return_description = returns.get('description', '')
    if return_type:
        docstring += f'\n    Returns:\n        {return_type}: {return_description}\n'
    else:
        docstring += f'\n    Returns:\n        {return_description}\n'

    docstring += '    """'
    return docstring


def update_deployment_comments(file_content: str, deployable: dict) -> str:
    """
    Remove old deployment comments based on the provided ranges and add new ones.
    """
    for range in reversed(deployable['deploymentCommentRanges']):
        file_content = file_content[:range[0]] + file_content[range[1]:]
    if deployable['deployments']:
        deployment_comments = write_deploy_comments(deployable['deployments'])
        deployable['deploymentCommentRanges'] = [(0, len(deployment_comments) + 1)]
        file_content = f"{deployment_comments}\n{file_content}"
    return file_content

def update_deployable_function_comments(file_content: str, deployable: dict, disable_docs: bool = False) -> str:
    """
    Update the docstring in the file content based on the deployable's documentation data.
    """
    if not disable_docs:
        docstring = print_docstring_function_comment(
            deployable['types']['description'],
            deployable['types']['params'],
            deployable['types']['returns']
        )
        if deployable["docStartIndex"] == deployable["docEndIndex"]:
            # Function doesn't yet have any docstrings so we need to add additional whitespace
            docstring = "    " + docstring + "\n"

        return f"{file_content[:deployable['docStartIndex']]}{docstring}{file_content[deployable['docEndIndex']:]}"
    return file_content

def write_updated_deployable(deployable: dict, disable_docs: bool = False) -> dict:
    """
    Read the deployable's file, update its comments and docstring, and write back to the file.
    """
    with open(deployable['file'], 'r', encoding='utf-8') as file:
        file_contents = file.read()

    if deployable['type'] in ['client-function', 'server-function']:
        file_contents = update_deployable_function_comments(file_contents, deployable, disable_docs)
    else:
        raise ValueError(f"Unsupported deployable type: '{deployable['type']}'")

    file_contents = update_deployment_comments(file_contents, deployable)

    with open(deployable['file'], 'w', encoding='utf-8') as file:
        file.write(file_contents)

    deployable['fileRevision'] = get_deployable_file_revision(file_contents)
    return deployable

def write_deploy_comments(deployments: list) -> str:
    """
    Generate deployment comments for each deployment record.
    """
    canopy_path = 'polyui/collections' if 'localhost' in os.getenv('POLY_API_BASE_URL', '') else 'canopy/polyui/collections'
    comments = []
    for d in deployments:
        instance_url = d['instance'].replace(':8000', ':3000') if d['instance'].endswith(':8000') else d['instance']
        comments.append(f"# Poly deployed @ {d['deployed']} - {d['context']}.{d['name']} - {instance_url}/{canopy_path}/{d['type']}s/{d['id']} - {d['fileRevision']}")
    return "\n".join(comments)
import requests
from requests.auth import HTTPBasicAuth
import json
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# Hard-coded variables
SOURCE_BASE_URL = "https://source.atlassian.net"
TARGET_BASE_URL = "https://target.atlassian.net"
USERNAME = ""
TOKEN = ""

# Authentication setup
auth = HTTPBasicAuth(USERNAME, TOKEN)

# Headers for the requests
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def search_filters_from_source():
    """Search for all filters in the source instance with pagination."""
    filters = []
    start_at = 0
    max_results = 50
    while True:
        url = f"{SOURCE_BASE_URL}/rest/api/3/filter/search?expand=description,owner,jql,sharePermissions,editPermissions&startAt={start_at}&maxResults={max_results}"
        response = requests.get(url, headers=headers, auth=auth)
        if response.status_code == 200:
            data = response.json()
            filters.extend(data.get('values', []))
            if data.get('isLast', True):
                break
            start_at += max_results
        else:
            logging.error(f"Failed to search filters from source: {response.status_code} - {response.text}")
            break
    return filters

def get_filters_from_target():
    """Get all filters from the target instance with pagination."""
    filters = []
    start_at = 0
    max_results = 50
    while True:
        url = f"{TARGET_BASE_URL}/rest/api/3/filter/search?expand=description,owner,jql,sharePermissions,editPermissions&startAt={start_at}&maxResults={max_results}"
        response = requests.get(url, headers=headers, auth=auth)
        if response.status_code == 200:
            data = response.json()
            filters.extend(data.get('values', []))
            if data.get('isLast', True):
                break
            start_at += max_results
        else:
            logging.error(f"Failed to get filters from target: {response.status_code} - {response.text}")
            break
    return filters

def get_projects_from_target():
    """Get all projects from the target instance."""
    url = f"{TARGET_BASE_URL}/rest/api/3/project"
    response = requests.get(url, headers=headers, auth=auth)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Failed to get projects from target: {response.status_code} - {response.text}")
        return []

def get_groups_from_target():
    """Get all groups from the target instance."""
    url = f"{TARGET_BASE_URL}/rest/api/3/group/bulk?maxResults=1000"
    response = requests.get(url, headers=headers, auth=auth)
    if response.status_code == 200:
        return response.json().get('values', [])
    else:
        logging.error(f"Failed to get groups from target: {response.status_code} - {response.text}")
        return []

def map_project_key_to_id(project_key, target_projects):
    """Map project key to its corresponding ID in the target instance."""
    for project in target_projects:
        if project['key'] == project_key:
            return project['id']
    return None

def map_group_name_to_id(group_name, target_groups):
    """Map group name to its corresponding ID in the target instance."""
    for group in target_groups:
        if group['name'] == group_name:
            return group['groupId']
    return None

def create_filter_in_target(filter_data, target_projects, target_groups):
    """Create a filter in the target instance."""
    url = f"{TARGET_BASE_URL}/rest/api/3/filter"

    share_permissions = []
    for permission in filter_data['sharePermissions']:
        if permission['type'] == 'project':
            project_id = map_project_key_to_id(permission['project']['key'], target_projects)
            if project_id:
                share_permissions.append({
                    'type': 'project',
                    'project': {'id': project_id}
                })
            else:
                logging.warning(f"Project '{permission['project']['key']}' not found in target instance, skipping permission.")
        elif permission['type'] == 'group':
            group_id = map_group_name_to_id(permission['group']['name'], target_groups)
            if group_id:
                share_permissions.append({
                    'type': 'group',
                    'group': {'groupId': group_id}
                })
            else:
                logging.warning(f"Group '{permission['group']['name']}' not found in target instance, skipping permission.")
        elif permission['type'] == 'user':
            if permission['user']:
                share_permissions.append({
                    'type': 'user',
                    "user": {
                        "accountId": permission['user']['accountId']
                    }
                })
            else:
                logging.warning(f"User '{permission['user']['accountId']}' not found in target instance, skipping permission.")
        elif permission['type'] == 'loggedin':
            share_permissions.append({
                'type': 'authenticated'
            })
        else:
            logging.warning(f"Unsupported share permission type: {permission['type']}")

    # Ensure the dashboard owner has edit permissions
    edit_permissions = []
    for permission in filter_data['editPermissions']:
        if permission['type'] == 'project':
            project_id = map_project_key_to_id(permission['project']['key'], target_projects)
            if project_id:
                edit_permissions.append({
                    'type': 'project',
                    'project': {'id': project_id}
                })
            else:
                logging.warning(f"Project '{permission['project']['key']}' not found in target instance, skipping permission.")
        elif permission['type'] == 'group':
            group_id = map_group_name_to_id(permission['group']['name'], target_groups)
            if group_id:
                edit_permissions.append({
                    'type': 'group',
                    'group': {'groupId': group_id}
                })
            else:
                logging.warning(f"Group '{permission['group']['name']}' not found in target instance, skipping permission.")
        elif permission['type'] == 'user':
            if permission['user']:
                edit_permissions.append({
                    'type': 'user',
                    "user": {
                        "accountId": permission['user']['accountId']
                    }
                })
            else:
                logging.warning(f"User '{permission['user']['accountId']}' not found in target instance, skipping permission.")
        else:
            logging.warning(f"Unsupported edot permission type: {permission['type']}")

    #filter_data["owner"]["accountId"]

    payload = {
        "name": filter_data["name"],
        "description": filter_data.get("description", ""),
        "jql": filter_data["jql"],
        "sharePermissions": share_permissions,
        "editPermissions": edit_permissions
    }
    response = requests.post(url, headers=headers, auth=auth, data=json.dumps(payload))

    if response.status_code == 201:
        filter_id = response.json()['id']
        owner_url = f"{TARGET_BASE_URL}/rest/api/3/filter/{filter_id}/owner"
        owner_payload = json.dumps({"accountId": permission['owner']['accountId']})

        owner_response = requests.put(owner_url, headers=headers, auth=auth, data=owner_payload)
        if owner_response.status_code == 200:
            logging.info(f"Filter owner changed successfully for filter ID {filter_id}")
        else:
            logging.error(f"Failed to change filter owner for filter ID {filter_id}: {owner_response.text}")
    else:
        logging.error(f"Failed to create filter: {response.text}")

    return response

def update_filter_owner(filter_id, new_owner):
    """Update the owner of a filter."""
    url = f"{TARGET_BASE_URL}/rest/api/3/filter/{filter_id}/owner"
    payload = json.dumps({
        "accountId": new_owner
    })
    response = requests.put(url, headers=headers, auth=auth, data=payload)
    return response

def filter_exists_in_target(filter_name, target_filters):
    """Check if a filter with the same name exists in the target instance."""
    for target_filter in target_filters:
        if target_filter['name'] == filter_name:
            return True
    return False

# Download filters from source and target instances
source_filters = search_filters_from_source()
target_filters = get_filters_from_target()
target_projects = get_projects_from_target()
target_groups = get_groups_from_target()
filter_count = 0

# Process and create filters in target instance
for filter_data in source_filters:
    filter_name = filter_data["name"]
    filter_owner = filter_data["owner"]["accountId"]

    # Check if the filter already exists in the target instance
    if filter_exists_in_target(filter_name, target_filters):
        logging.info(f"Filter '{filter_name}' already exists in target instance, skipping creation.")
        continue

    # Create filter in the target instance
    response = create_filter_in_target(filter_data, target_projects, target_groups)
    if response.status_code == 200:
        new_filter_id = response.json()["id"]
        logging.info(f"Successfully created filter {new_filter_id} in target instance")

        # Update filter owner in target instance
        owner_response = update_filter_owner(new_filter_id, filter_owner)
        if owner_response.status_code == 200:
            logging.info(f"Successfully updated filter {filter_name} owner to {filter_owner}")
        else:
            logging.error(f"Failed to update filter {filter_name} owner: {owner_response.status_code} - {owner_response.text}")
    else:
        logging.error(f"Failed to create filter in target instance: {response.status_code} - {response.text}")

    filter_count += 1

logging.info(f"Processed {filter_count} filters")

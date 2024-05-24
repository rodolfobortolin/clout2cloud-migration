import requests
from requests.auth import HTTPBasicAuth
import logging
import os
import csv
import json

# Configuration for source and target instances
source_config = {
    'email': '',
    'token': '',
    'base_url': ''
}

target_config = {
    'email': '',
    'token': '',
    'base_url': ''
}

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

script_location = os.path.dirname(os.path.abspath(__file__))
error_csv_path = os.path.join(script_location, 'dashboard_transfer_errors.csv')

# Headers for the requests
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# Function to get dashboards with pagination
def get_dashboards(config):
    dashboards = []
    start_at = 0
    max_results = 50
    while True:
        response = requests.get(
            f"{config['base_url']}/rest/api/2/dashboard",
            auth=HTTPBasicAuth(config['email'], config['token']),
            headers={"Accept": "application/json"},
            params={'startAt': start_at, 'maxResults': max_results}
        )
        response.raise_for_status()
        data = response.json()
        dashboards.extend(data['dashboards'])
        if start_at + max_results >= data['total']:
            break
        start_at += max_results
    logging.info(f"Fetched {len(dashboards)} dashboards from {config['base_url']}")
    return dashboards

# Function to check if a dashboard exists in the target instance by name
def dashboard_exists(target_config, dashboard_name):
    dashboards = get_dashboards(target_config)
    return any(dashboard['name'] == dashboard_name for dashboard in dashboards)

# Function to get filters with pagination
def get_filters(config):
    filters = []
    start_at = 0
    max_results = 50
    while True:
        response = requests.get(
            f"{config['base_url']}/rest/api/2/filter/search",
            auth=HTTPBasicAuth(config['email'], config['token']),
            headers={"Accept": "application/json"},
            params={'startAt': start_at, 'maxResults': max_results}
        )
        response.raise_for_status()
        data = response.json()
        filters.extend(data['values'])
        if start_at + max_results >= data['total']:
            break
        start_at += max_results
    logging.info(f"Fetched {len(filters)} filters from {config['base_url']}")
    return filters

# Function to get a filter by its ID
def get_filter_by_id(config, filter_id):
    response = requests.get(
        f"{config['base_url']}/rest/api/2/filter/{filter_id}",
        auth=HTTPBasicAuth(config['email'], config['token']),
        headers={"Accept": "application/json"}
    )
    response.raise_for_status()
    return response.json()

# Function to get projects from the target instance
def get_projects_from_target():
    url = f"{target_config['base_url']}/rest/api/2/project"
    response = requests.get(url, headers=headers, auth=HTTPBasicAuth(target_config['email'], target_config['token']))
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Failed to get projects from target: {response.status_code} - {response.text}")
        return []

# Function to get groups from the target instance
def get_groups_from_target():
    url = f"{target_config['base_url']}/rest/api/2/group/bulk?maxResults=1000"
    response = requests.get(url, headers=headers, auth=HTTPBasicAuth(target_config['email'], target_config['token']))
    if response.status_code == 200:
        return response.json().get('values', [])
    else:
        logging.error(f"Failed to get groups from target: {response.status_code} - {response.text}")
        return []

# Function to map project key to project ID
def map_project_key_to_id(project_key, target_projects):
    for project in target_projects:
        if project['key'] == project_key:
            return project['id']
    return None

# Function to map group name to group ID
def map_group_name_to_id(group_name, target_groups):
    for group in target_groups:
        if group['name'] == group_name:
            return group['groupId']
    return None

# Function to transfer dashboards from source to target
def transfer_dashboards(source_config, target_config):
    dashboards = get_dashboards(source_config)
    target_projects = get_projects_from_target()
    target_groups = get_groups_from_target()
    error_entries = []

    for dashboard in dashboards:
        if dashboard['name'] == 'Default Dashboard':
            logging.info(f"Skipping 'Default Dashboard'")
            continue

        if not dashboard_exists(target_config, dashboard['name']):
            try:
                transfer_dashboard(source_config, target_config, dashboard, target_projects, target_groups)
            except Exception as e:
                logging.error(f"Error transferring dashboard {dashboard['name']}: {str(e)}")
                error_entries.append([dashboard['name'], str(e)])
        else:
            logging.info(f"Dashboard {dashboard['name']} already exists in target instance")

    if error_entries:
        with open(error_csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Dashboard Name', 'Error'])
            writer.writerows(error_entries)
        logging.info(f"Errors logged to {error_csv_path}")

# Function to transfer a single dashboard
def transfer_dashboard(source_config, target_config, dashboard, target_projects, target_groups):
    # Map sharePermissions to target project/group IDs
    share_permissions = []
    for permission in dashboard['sharePermissions']:
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
    for permission in dashboard['editPermissions']:
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

    # Create the dashboard in the target instance
    response = requests.post(
        f"{target_config['base_url']}/rest/api/2/dashboard",
        auth=HTTPBasicAuth(target_config['email'], target_config['token']),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={
            'name': dashboard['name'],
            'description': dashboard['description'],
            'sharePermissions': share_permissions,
            'editPermissions': edit_permissions
        }
    )
    response.raise_for_status()
    new_dashboard = response.json()

    # Transfer gadgets
    gadgets = get_dashboard_gadgets(source_config, dashboard['id'])
    for gadget in gadgets:
        transfer_gadget(source_config, target_config, new_dashboard['id'], dashboard['id'], gadget)

# Function to get gadgets for a dashboard
def get_dashboard_gadgets(config, dashboard_id):
    response = requests.get(
        f"{config['base_url']}/rest/api/2/dashboard/{dashboard_id}/gadget",
        auth=HTTPBasicAuth(config['email'], config['token']),
        headers={"Accept": "application/json"}
    )
    response.raise_for_status()
    return response.json()['gadgets']

# Function to transfer a gadget
def transfer_gadget(source_config, target_config, new_dashboard_id, source_dashboard_id, gadget):
    gadget_properties = get_gadget_properties(source_config, source_dashboard_id, gadget['id'])
    new_properties = update_gadget_properties_for_target(target_config, gadget_properties, gadget)

    # Prepare the request payload for creating the gadget
    create_payload = {
        'color': gadget['color'],
        'position': gadget['position']
    }
    if 'moduleKey' in gadget and gadget['moduleKey']:
        create_payload['moduleKey'] = gadget['moduleKey']
    if 'uri' in gadget and gadget['uri']:
        create_payload['uri'] = gadget['uri']

    # Create the gadget
    response = requests.post(
        f"{target_config['base_url']}/rest/api/2/dashboard/{new_dashboard_id}/gadget",
        auth=HTTPBasicAuth(target_config['email'], target_config['token']),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=create_payload
    )
    response.raise_for_status()
    
    # Get the new item_id for the created gadget
    new_gadget = response.json()
    item_id = new_gadget['id']

    # Use PUT endpoint to set the config property
    if new_properties:
        config_payload = json.dumps({k: str(v) for k, v in new_properties.items()})
        response = requests.put(
            f"{target_config['base_url']}/rest/api/2/dashboard/{new_dashboard_id}/items/{item_id}/properties/config",
            auth=HTTPBasicAuth(target_config['email'], target_config['token']),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            data=config_payload
        )
        response.raise_for_status()

# Function to get gadget properties
def get_gadget_properties(config, dashboard_id, item_id):
    response = requests.get(
        f"{config['base_url']}/rest/api/2/dashboard/{dashboard_id}/items/{item_id}/properties/config",
        auth=HTTPBasicAuth(config['email'], config['token']),
        headers={"Accept": "application/json"}
    )
    if response.status_code == 200:
        return response.json().get('value', {})
    else:
        logging.warning(f"No config found for gadget {item_id} on dashboard {dashboard_id}")
        return {}

# Function to update gadget properties for the target instance
def update_gadget_properties_for_target(target_config, properties, gadget):
    new_properties = {}
    
    # Add moduleKey and uri only if they exist and are not empty
    if 'moduleKey' in gadget and gadget['moduleKey']:
        new_properties['moduleKey'] = gadget['moduleKey']
    if 'uri' in gadget and gadget['uri']:
        new_properties['uri'] = gadget['uri']
    
    # Update new_properties with other properties
    new_properties.update(properties)
    
    # Ensure that only one of moduleKey or uri is present
    if 'moduleKey' in new_properties and 'uri' in new_properties:
        logging.warning("Both uri and moduleKey are present. Removing uri to avoid conflict.")
        del new_properties['uri']
    
    return new_properties

# Start the dashboard transfer process
transfer_dashboards(source_config, target_config)

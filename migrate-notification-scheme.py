import logging
import requests
from requests.auth import HTTPBasicAuth

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# Configuration for both Jira instances
source_config = {
    'email': 'rodolfobortolin@gmail.com',
    'token': '',
    'base_url': 'https://source.atlassian.net'
}

target_config = {
    'email': 'rodolfobortolin@gmail.com',
    'token': '',
    'base_url': 'https://target.atlassian.net'
}

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def get_auth(config):
    return HTTPBasicAuth(config['email'], config['token'])

def get_notification_scheme(config, scheme_id):
    url = f"{config['base_url']}/rest/api/3/notificationscheme/{scheme_id}?expand=all"
    response = requests.get(url, headers=HEADERS, auth=get_auth(config))
    response.raise_for_status()
    return response.json()

def create_notification_scheme(config, scheme_data):
    url = f"{config['base_url']}/rest/api/3/notificationscheme"
    response = requests.post(url, headers=HEADERS, json=scheme_data, auth=get_auth(config))
    response.raise_for_status()
    return response.json()

def migrate_notification_scheme(source_config, target_config, source_scheme_id):
    logging.info(f'Starting migration of notification scheme {source_scheme_id}...')
    
    # Get the source notification scheme
    source_scheme = get_notification_scheme(source_config, source_scheme_id)
    
    # Prepare the target scheme data
    target_scheme_data = {
        "name": source_scheme["name"],
        "description": source_scheme.get("description", ""),
        "notificationSchemeEvents": []
    }
    
    for event in source_scheme["notificationSchemeEvents"]:
        target_event = {
            "event": {
                "id": event["event"]["id"]
            },
            "notifications": []
        }
        
        for notification in event["notifications"]:
            target_notification = {
                "notificationType": notification["notificationType"],
                "parameter": notification.get("parameter")
            }
            target_event["notifications"].append(target_notification)
        
        target_scheme_data["notificationSchemeEvents"].append(target_event)
    
    # Create the target notification scheme
    created_scheme = create_notification_scheme(target_config, target_scheme_data)
    
    logging.info(f'Notification scheme {source_scheme_id} migrated successfully as {created_scheme["id"]}')

if __name__ == "__main__":
    source_scheme_id = input("Enter the ID of the notification scheme to migrate: ")
    migrate_notification_scheme(source_config, target_config, source_scheme_id)

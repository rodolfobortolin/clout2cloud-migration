import requests
import logging
import json
import sys
import csv
from requests.auth import HTTPBasicAuth

SOURCE_BASE_URL = "https://source.atlassian.net"
TARGET_BASE_URL = "https://target.atlassian.net"
USERNAME = "rodolfobortolin@gmail.com"
TOKEN = '',

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

def get_attachments(page_id):
    """Retrieve all attachments for a given page."""
    url = f"{SOURCE_BASE_URL}/wiki/rest/api/content/{page_id}/child/attachment"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, TOKEN), headers={"Accept": "application/json"})
    if response.status_code == 200:
        return response.json()['results']
    else:
        logging.error(f"Failed to retrieve attachments for page {page_id}")
        return []

def download_attachment(attachment):
    """Download an attachment."""
    url = f"{SOURCE_BASE_URL}/wiki/{attachment['_links']['download']}"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, TOKEN))
    if response.status_code == 200:
        return response.content
    else:
        logging.error(f"Failed to download attachment {attachment['title']}")
        return None

def upload_attachment(page_id, filename, file_content):
    """Upload an attachment to a target page."""
    url = f"{TARGET_BASE_URL}/wiki/rest/api/content/{page_id}/child/attachment"
    headers = {"X-Atlassian-Token": "no-check"}
    files = {'file': (filename, file_content)}
    response = requests.post(url, headers=headers, files=files, auth=HTTPBasicAuth(USERNAME, TOKEN))
    if response.status_code in [200, 201]:
        logging.info(f"Uploaded attachment {filename}")
    else:
        logging.error(f"Failed to upload attachment {filename}: {response.text}")

def get_page_position(page):
    """Helper function to retrieve the position of a page."""
    return int(page.get('extensions', {}).get('position', 0))

def get_all_pages_for_space(space_key):
    """
    Retrieves all pages for a given space key from Confluence.
    """
    base_url = f"{SOURCE_BASE_URL}/wiki/rest/api/space/{space_key}/content?type=page&expand=body.storage,ancestors"
    pages = []
    start = 0
    limit = 50
    
    while True:
        url = f"{base_url}&start={start}&limit={limit}"
        response = requests.get(url, auth=HTTPBasicAuth(USERNAME, TOKEN), headers={"Accept": "application/json"})
        
        if response.status_code == 200:
            data = response.json()
            pages.extend(data['page']["results"])
            
            if start + limit >= data.get('size', 0):
                break
            start += limit
        else:
            logging.info(f"Failed to retrieve pages for space {space_key}")
            break

    sorted_pages = sorted(pages, key=get_page_position)
    
    return sorted_pages

def get_page_content(page_id):
    """
    Retrieves the content of a Confluence page by its ID.
    """
    url = f"{SOURCE_BASE_URL}/wiki/rest/api/content/{page_id}?expand=body.storage"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, TOKEN), headers={"Accept": "application/json"})
    if response.status_code == 200:
        page_data = response.json()
        return page_data['body']['storage']['value']
    else:
        logging.error(f"Failed to retrieve content for page {page_id}")
        return ""
    
def create_parent_page(space_key):
    """
    Creates a parent page with the title based on the specified language.
    """
    parent_page_title = "Migrated Pages"
    payload = {
        "type": "page",
        "title": parent_page_title,
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": f"<p>This is the root page for all content that was migrated</p>",
                "representation": "storage"
            }
        }
    }

    try:
        response = requests.post(
            f"{TARGET_BASE_URL}/wiki/rest/api/content",
            auth=HTTPBasicAuth(USERNAME, TOKEN),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            data=json.dumps(payload)
        )

        if response.status_code in [200, 201]:
            page_id = response.json().get('id')
            logging.info(f"Parent page created successfully in target Confluence with title: {parent_page_title} and ID: {page_id}")
            return page_id
        else:
            logging.error("Failed to create parent page in target Confluence")
            logging.error(f"Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error creating Confluence parent page in target instance: {e}")
        return None

def create_page_in_target_confluence(space_key, page_title, reconstructed_html, parent_page_id):
    """
    Creates a page in the target Confluence instance.
    """

    payload = {
        "type": "page",
        "title": page_title,
        "space": {"key": space_key},
        "ancestors": [{"id": parent_page_id}],
        "body": {"storage": {"value": reconstructed_html, "representation": "storage"}}
    }

    try:
        response = requests.post(
            f"{TARGET_BASE_URL}/wiki/rest/api/content",
            auth=HTTPBasicAuth(USERNAME, TOKEN), 
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            data=json.dumps(payload)
        )

        if response.status_code in [200, 201]:
            logging.info(f"Page created successfully in target Confluence with title: {page_title}")
            page_id = response.json().get('id')
            return page_id
        else:
            logging.error("Failed to create page in target Confluence")
            logging.error(f"Response: {response.text}")
    except Exception as e:
        logging.error(f"Error creating Confluence page in target instance: {e}")

def process_and_create_pages(source_space_key, target_space_key):
    """
    Process pages from source space and create them in target space.
    """
    parent_page_id = create_parent_page(target_space_key)
    if not parent_page_id:
        logging.error("Parent page ID is required!")
        return
    
    pages = get_all_pages_for_space(source_space_key)
    logging.info(f"Retrieved {len(pages)} pages for space {source_space_key}")

    for page in pages:
        source_page_id = page['id']
        source_page_title = page['title']
        logging.info(f"Processing page: {source_page_title} (ID: {source_page_id})")
  
        target_page_title = source_page_title
        source_html_content = get_page_content(source_page_id)
        
        logging.info(f"Creating translated page '{target_page_title}' in target space")
        target_page_id = create_page_in_target_confluence(target_space_key, target_page_title, source_html_content, parent_page_id)
        if target_page_id:            
            attachments = get_attachments(source_page_id)
            for attachment in attachments:
                attachment_data = download_attachment(attachment)
                if attachment_data:
                    upload_attachment(target_page_id, attachment['title'], attachment_data)
        else:
            logging.error(f"Failed to create page '{target_page_title}' in target space")

def read_spaces_from_csv(file_path):
    """
    Read source and target spaces from a CSV file.
    """
    spaces_to_process = []
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                source_space = row.get('SOURCE')
                target_space = row.get('TARGET')
                if source_space and target_space:
                    spaces_to_process.append((source_space, target_space))
    except Exception as e:
        logging.error(f"Error reading CSV file: {e}")
    
    return spaces_to_process

if __name__ == "__main__":
    csv_file_path = 'spaces.csv'  # Path to the CSV file
    spaces_to_process = read_spaces_from_csv(csv_file_path)
    
    for source_space, target_space in spaces_to_process:
        logging.info(f"Processing source space '{source_space}' to target space '{target_space}'")
        process_and_create_pages(source_space, target_space)

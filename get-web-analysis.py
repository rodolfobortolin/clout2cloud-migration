import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from docx import Document
from docx.shared import Inches
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# Base URLs for the Jira instances
base_urls = {
    'source': 'https://source.atlassian.net',
    'target': 'https://target.atlassian.net'
}

# Paths for the Jira pages
paths = {
    'global_permissions': '/secure/admin/GlobalPermissions!default.jspa',
    'time_tracking': '/secure/admin/TimeTrackingAdmin.jspa',
    'plans_permissions': '/jira/plans/settings/permissions',
    'issue_hierarchy': '/jira/settings/issues/issue-hierarchy',
    'plans_dependency': '/jira/plans/settings/dependencies'  # Assuming this is the correct path for plans dependency settings
}

# Initialize WebDriver (Make sure to have the ChromeDriver in your PATH)
driver = webdriver.Chrome()

def manual_login(base_url):
    driver.get(base_url)
    print(f"Please log in to Jira in the browser that opened and navigate to any page of the required Jira instance.")
    input("Press Enter here in the terminal after you have logged in...")

def navigate_to_page(base_url, path):
    url = f"{base_url}{path}"
    driver.get(url)
    time.sleep(4)  # Adjust sleep time as needed to ensure the page loads completely

def extract_permissions():
    permissions = {}
    table = driver.find_element(By.ID, 'global_perms')
    rows = table.find_elements(By.TAG_NAME, 'tr')[1:]  # Skip the header row
    
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, 'td')
        if len(cols) == 2:
            try:
                permission_name = cols[0].find_element(By.TAG_NAME, 'strong').text.strip()
                groups = []
                for group_elem in cols[1].find_elements(By.TAG_NAME, 'li'):
                    try:
                        group_name = group_elem.find_element(By.TAG_NAME, 'span').text.strip()
                        groups.append(group_name)
                    except Exception as e:
                        logging.error(f"Error extracting group name: {e}")
                permissions[permission_name] = groups
            except Exception as e:
                logging.error(f"Error extracting permission name: {e}")
    
    return permissions

def extract_plans_permissions():
    permissions = {}
    table = driver.find_element(By.CSS_SELECTOR, 'table.css-1h2ap37')
    rows = table.find_elements(By.TAG_NAME, 'tr')[1:]  # Skip the header row

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, 'td')
        if len(cols) == 3:
            try:
                permission_name = cols[0].text.strip()
                groups = [group.text.strip() for group in cols[2].find_elements(By.TAG_NAME, 'span')]
                permissions[permission_name] = groups
            except Exception as e:
                logging.error(f"Error extracting plans permission: {e}")

    return permissions

def extract_issue_hierarchy():
    hierarchy = {}
    table = driver.find_element(By.CSS_SELECTOR, 'table[data-testid="admin-pages-issue-hierarchy-directory.ui.table.dynamic-table-unrankable--table"]')
    rows = table.find_elements(By.TAG_NAME, 'tr')[1:]  # Skip the header row
    
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, 'td')
        if len(cols) >= 4:
            try:
                level_name = cols[1].find_element(By.TAG_NAME, 'input').get_attribute('value').strip()
                issue_types = cols[3].text.strip()
                hierarchy[level_name] = issue_types
            except Exception as e:
                logging.error(f"Error extracting issue hierarchy: {e}")
    
    return hierarchy

def add_permissions_to_doc(doc, title, permissions):
    doc.add_heading(title, level=1)
    
    for permission, groups in permissions.items():
        doc.add_heading(permission, level=2)
        if groups:
            for group in groups:
                doc.add_paragraph(group, style='ListBullet')
        else:
            doc.add_paragraph("No groups assigned", style='ListBullet')

def compare_permissions(source_permissions, target_permissions):
    missing_permissions = {}
    for permission, groups in source_permissions.items():
        if permission in target_permissions:
            missing_groups = set(groups) - set(target_permissions[permission])
            if missing_groups:
                missing_permissions[permission] = list(missing_groups)
        else:
            missing_permissions[permission] = groups
    return missing_permissions

def add_issue_hierarchy_to_doc(doc, title, hierarchy):
    doc.add_heading(title, level=1)
    
    for level, issue_types in hierarchy.items():
        doc.add_heading(level, level=2)
        doc.add_paragraph(issue_types, style='ListBullet')

def take_screenshot_of_div(base_url, path, div_identifier, filename, by=By.CLASS_NAME):
    navigate_to_page(base_url, path)
    div_element = driver.find_element(by, div_identifier)
    div_element.screenshot(filename)
    logging.info(f"Screenshot of {div_identifier} saved to {filename}")

def add_screenshot_to_doc(doc, title, filename):
    doc.add_heading(title, level=1)
    doc.add_picture(filename, width=Inches(6))

# Create a new Document
doc = Document()

# Manual login for the source instance
manual_login(base_urls['source'])

# Extract and add permissions from the source instance
navigate_to_page(base_urls['source'], paths['global_permissions'])
source_permissions = extract_permissions()

# Manual login for the target instance
manual_login(base_urls['target'])

# Extract and add permissions from the target instance
navigate_to_page(base_urls['target'], paths['global_permissions'])
target_permissions = extract_permissions()

# Compare permissions and add missing groups to the document
missing_permissions = compare_permissions(source_permissions, target_permissions)
add_permissions_to_doc(doc, 'Missing Permissions in Target Instance', missing_permissions)

# Take screenshots of the specific div for Time Tracking settings and add them to the document
take_screenshot_of_div(base_urls['source'], paths['time_tracking'], 'common-setting-items', 'source_time_tracking.png')
add_screenshot_to_doc(doc, 'Source Time Tracking Settings', 'source_time_tracking.png')

take_screenshot_of_div(base_urls['target'], paths['time_tracking'], 'common-setting-items', 'target_time_tracking.png')
add_screenshot_to_doc(doc, 'Target Time Tracking Settings', 'target_time_tracking.png')

# Extract and add plans permissions from the source instance
navigate_to_page(base_urls['source'], paths['plans_permissions'])
source_plans_permissions = extract_plans_permissions()
#add_permissions_to_doc(doc, 'Source Plans Permissions', source_plans_permissions)

# Extract and add plans permissions from the target instance
navigate_to_page(base_urls['target'], paths['plans_permissions'])
target_plans_permissions = extract_plans_permissions()
#add_permissions_to_doc(doc, 'Target Plans Permissions', target_plans_permissions)

# Compare plans permissions and add missing groups to the document
missing_plans_permissions = compare_permissions(source_plans_permissions, target_plans_permissions)
add_permissions_to_doc(doc, 'Missing Plans Permissions in Target Instance', missing_plans_permissions)

# Take screenshot of the issue hierarchy page and add it to the document
take_screenshot_of_div(base_urls['source'], paths['issue_hierarchy'], 'ak-main-content', 'source_issue_hierarchy.png', By.ID)
add_screenshot_to_doc(doc, 'Source Issue Hierarchy Settings', 'source_issue_hierarchy.png')

take_screenshot_of_div(base_urls['target'], paths['issue_hierarchy'], 'ak-main-content', 'target_issue_hierarchy.png', By.ID)
add_screenshot_to_doc(doc, 'Target Issue Hierarchy Settings', 'target_issue_hierarchy.png')

# Take screenshot of the plans dependency settings page and add it to the document
take_screenshot_of_div(base_urls['source'], paths['plans_dependency'], 'ak-main-content', 'source_plans_dependency.png', By.ID)
add_screenshot_to_doc(doc, 'Source Plans Dependency Settings', 'source_plans_dependency.png')

take_screenshot_of_div(base_urls['target'], paths['plans_dependency'], 'ak-main-content', 'target_plans_dependency.png', By.ID)
add_screenshot_to_doc(doc, 'Target Plans Dependency Settings', 'target_plans_dependency.png')

# Save the document
doc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jira_permissions.docx')
doc.save(doc_path)
logging.info(f"Document saved to {doc_path}")

# Close the WebDriver
driver.quit()


# Jira and Confluence Cloud-to-Cloud Migration Scripts

This repository contains scripts to facilitate the migration of Jira and Confluence components from one cloud instance to another. Currently, the repository includes scripts to migrate dashboards and filters in Jira.

#### Configuration
Provide the following configurations in the script:

```python
SOURCE_CONFIG = {
    'email': 'your-email@example.com',  # Replace with your source Jira email
    'token': 'your-source-api-token',  # Replace with your source Jira API token
    'base_url': 'https://source-instance.atlassian.net'  # Replace with your source Jira instance URL
}

DESTINATION_CONFIG = {
    'email': 'your-email@example.com',  # Replace with your destination Jira email
    'token': 'your-destination-api-token',  # Replace with your destination Jira API token
    'base_url': 'https://destination-instance.atlassian.net'  # Replace with your destination Jira instance URL
}
```

"""
Deeper Jira diagnostic -- splits "is my token valid at all", "does the
project exist / can I see it", and "can I actually create issues in it"
into separate checks, since Jira's create-issue endpoint lumps all of
these into one generic error message.

Run it:
    python test_jira_diagnose.py
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
email = os.environ.get("JIRA_EMAIL", "")
token = os.environ.get("JIRA_API_TOKEN", "")
project_key = os.environ.get("JIRA_PROJECT_KEY", "")

print(f"Base URL:    {base_url}")
print(f"Email:       {email}")
print(f"Project key: {project_key}")
print(f"Token:       {token[:12]}... ({len(token)} chars)\n")

auth = HTTPBasicAuth(email, token)

# 1) Is the token valid at all, and which account does it actually belong to?
print("1) Checking token validity (GET /rest/api/3/myself)...")
r = requests.get(f"{base_url}/rest/api/3/myself", auth=auth, timeout=15)
if r.status_code == 200:
    me = r.json()
    print(f"   OK -- token authenticates as: {me.get('emailAddress')} ({me.get('displayName')})")
    if me.get("emailAddress", "").lower() != email.lower():
        print(f"   MISMATCH: .env says JIRA_EMAIL={email}, but token actually belongs to {me.get('emailAddress')}")
else:
    print(f"   FAILED -- status {r.status_code}: {r.text[:300]}")
    print("   -> Token is invalid/expired, or email/token pair is wrong. Regenerate at:")
    print("      https://id.atlassian.com/manage-profile/security/api-tokens")

print()

# 2) Does the project exist and can this account see it?
print(f"2) Checking project visibility (GET /rest/api/3/project/{project_key})...")
r = requests.get(f"{base_url}/rest/api/3/project/{project_key}", auth=auth, timeout=15)
if r.status_code == 200:
    proj = r.json()
    print(f"   OK -- project exists: '{proj.get('name')}' (id={proj.get('id')}, key={proj.get('key')})")
elif r.status_code == 404:
    print(f"   NOT FOUND -- either the key '{project_key}' is wrong, or this account can't see it at all.")
    print("   -> Double check Space settings -> Details -> Space key in the Jira UI.")
else:
    print(f"   FAILED -- status {r.status_code}: {r.text[:300]}")

print()

# 3) What issue types + permissions does this account actually have in the project?
print(f"3) Checking create-issue metadata (GET /rest/api/3/issue/createmeta?projectKeys={project_key})...")
r = requests.get(
    f"{base_url}/rest/api/3/issue/createmeta",
    params={"projectKeys": project_key, "expand": "projects.issuetypes"},
    auth=auth,
    timeout=15,
)
if r.status_code == 200:
    data = r.json()
    projects = data.get("projects", [])
    if not projects:
        print("   Empty result -- this account has NO create-issue permission in this project,")
        print("   even though the project itself may exist. Check Space settings -> Access,")
        print("   and make sure this account has a role that includes 'Create issues'.")
    else:
        for p in projects:
            types = [t["name"] for t in p.get("issuetypes", [])]
            print(f"   OK -- can create issues in '{p.get('key')}'. Available issue types: {types}")
            if "Task" not in types:
                print("   'Task' is not in the list above -- agent/jira_client.py hardcodes "
                      "issuetype name='Task'. Update it to one of the types listed here.")
else:
    print(f"   FAILED -- status {r.status_code}: {r.text[:300]}")

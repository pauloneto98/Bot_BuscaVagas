import os
import json
import requests

def create_pr(repo: str, head: str, base: str = 'main', title: str = '', body: str = '', token: str | None = None) -> str | None:
    if token is None:
        token = os.getenv('GITHUB_TOKEN')
    if not token:
        print('[WARN] GITHUB_TOKEN not set. Skipping PR creation.')
        return None
    url = f"https://api.github.com/repos/{repo}/pulls"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    payload = {
        'title': title or 'Release: Fast Bot',
        'head': head,
        'base': base,
        'body': body or 'Automated release PR for bot enhancements.'
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code in (200, 201):
        data = resp.json()
        pr_url = data.get('html_url') or data.get('url')
        print(f"[INFO] PR created: {pr_url}")
        return pr_url
    else:
        print(f"[ERR] Failed to create PR: {resp.status_code} {resp.text}")
        return None

import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.pr_helper import create_pr

def main():
    repo = os.getenv('GITHUB_REPO', 'pauloneto98/Bot_BuscaVagas')
    head = os.getenv('PR_HEAD', 'feat/release-fastbot-v1')
    base = os.getenv('PR_BASE', 'main')
    title = os.getenv('PR_TITLE', 'Release: Fast Bot v1')
    body = os.getenv('PR_BODY', 'Automated release PR with Gemini 1.5-flash, rate-limit metrics, reduced search, and fallback logic.')
    token = os.getenv('GITHUB_TOKEN')
    pr_url = create_pr(repo, head, base, title, body, token)
    if pr_url:
        print(f"PR URL: {pr_url}")

if __name__ == '__main__':
    main()

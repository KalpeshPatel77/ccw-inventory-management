# install-github-app

Install a GitHub App on this repository using the GitHub MCP tools.

## Steps

1. Use `mcp__github__list_repos` or check git remote to identify the owner and repo name for the current project.

2. Ask the user which GitHub App they want to install if not already specified. Common options:
   - **GitHub Actions** — CI/CD workflows
   - **Dependabot** — automated dependency updates
   - **CodeQL** — code security analysis
   - **Codecov** — test coverage reporting
   - A custom or third-party app by name

3. Inform the user that GitHub App installation requires browser-based authorization and cannot be done programmatically via the API without admin OAuth tokens. Provide the direct installation URL:
   - Marketplace app: `https://github.com/marketplace/<app-name>`
   - Direct install: `https://github.com/apps/<app-name>/installations/new`

4. Guide the user through the installation:
   - Navigate to the URL above
   - Click **Install** or **Configure**
   - Select **Only select repositories** and choose this repo (or **All repositories**)
   - Click **Install** / **Save**

5. After the user confirms installation, use `mcp__github__get_repo` to verify the app is reflected on the repo, or check `.github/` for any config files the app may have created.

6. If the app requires configuration files (e.g., `.github/dependabot.yml`, `.github/codecov.yml`), offer to create them.

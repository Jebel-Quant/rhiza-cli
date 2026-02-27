# Authentication for Private Template Repositories

Rhiza fetches template files by running `git clone` under the hood. If your template repository is **private**, Git needs credentials to access it. This guide explains how to configure authentication for GitHub and GitLab template repositories.

## Table of Contents

- [GitHub Authentication](#github-authentication)
  - [Option 1: GitHub CLI (Recommended)](#option-1-github-cli-recommended)
  - [Option 2: Personal Access Token (HTTPS)](#option-2-personal-access-token-https)
  - [Option 3: SSH Key](#option-3-ssh-key)
- [GitLab Authentication](#gitlab-authentication)
  - [Option 1: Personal Access Token (HTTPS)](#option-1-personal-access-token-https-1)
  - [Option 2: SSH Key](#option-2-ssh-key-1)
- [CI/CD Configuration](#cicd-configuration)
  - [GitHub Actions](#github-actions)
  - [GitLab CI](#gitlab-ci)
- [Verifying Your Setup](#verifying-your-setup)
- [Troubleshooting](#troubleshooting)

---

## GitHub Authentication

### Option 1: GitHub CLI (Recommended)

The [GitHub CLI](https://cli.github.com/) is the easiest way to configure Git credentials locally. It handles token management automatically.

```bash
# Install the GitHub CLI
# macOS
brew install gh

# Ubuntu / Debian
sudo apt install gh

# Windows (winget)
winget install GitHub.cli

# Authenticate
gh auth login

# Configure git to use the CLI's credentials
gh auth setup-git
```

After running `gh auth setup-git`, all `git clone` operations (including those run by `rhiza sync`) will automatically use your GitHub credentials.

### Option 2: Personal Access Token (HTTPS)

If you prefer not to install the GitHub CLI, you can use a Personal Access Token (PAT).

#### Step 1: Create a Personal Access Token

**Fine-grained token (recommended):**

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click **Generate new token**
3. Set a descriptive name (e.g., `rhiza-templates-read`)
4. Set an expiration date (90 days or less is recommended)
5. Under **Repository access**, select only the template repository
6. Under **Repository permissions**, grant **Contents: Read-only**
7. Click **Generate token** and copy the token immediately

**Classic token:**

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Set a descriptive name (e.g., `rhiza-templates-read`)
4. Set an expiration date
5. Select the **`repo`** scope (required for private repository access)
6. Click **Generate token** and copy the token immediately

#### Step 2: Configure Git to Use the Token

Store the token in your Git credential store so it is used automatically:

```bash
# Configure git to use the token for GitHub HTTPS URLs
git config --global credential.helper store
echo "https://YOUR_TOKEN@github.com" >> ~/.git-credentials
```

Or use a more secure credential helper (macOS Keychain, Windows Credential Manager):

```bash
# macOS — uses Keychain
git config --global credential.helper osxkeychain

# Windows — uses Windows Credential Manager
git config --global credential.helper manager
```

Then clone any private GitHub repository to trigger the credentials prompt, enter your username and the token as the password, and the helper will cache them.

Alternatively, embed the token directly in the Git URL rewrite rule (keep this out of version control):

```bash
git config --global url."https://YOUR_TOKEN@github.com/".insteadOf "https://github.com/"
```

> **Security note:** Embedding tokens in Git config stores them in plain text in `~/.gitconfig`. Prefer the credential helper approach or the GitHub CLI for better security.

### Option 3: SSH Key

SSH keys are a good choice for long-term local development setups.

#### Step 1: Generate an SSH key (if you don't have one)

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter to accept the default file location (~/.ssh/id_ed25519)
# Optionally set a passphrase
```

#### Step 2: Add the public key to GitHub

1. Copy the public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
2. Go to [GitHub Settings → SSH and GPG keys](https://github.com/settings/keys)
3. Click **New SSH key**
4. Paste the public key and save

#### Step 3: Configure your template to use SSH

Update `.rhiza/template.yml` to use an SSH-compatible URL format. Rhiza uses the `owner/repo` format internally, but you can set the host to control which URL prefix is used. For SSH you can override git's URL rewriting:

```bash
# Rewrite HTTPS GitHub URLs to SSH (applies globally)
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

After this, `rhiza sync` will use SSH for all GitHub clones automatically.

---

## GitLab Authentication

### Option 1: Personal Access Token (HTTPS)

#### Step 1: Create a Personal Access Token

1. Go to your GitLab profile → **Edit profile** → **Access tokens** (or navigate to `https://gitlab.com/-/profile/personal_access_tokens`)
2. Click **Add new token**
3. Set a descriptive name (e.g., `rhiza-templates-read`)
4. Set an expiration date
5. Select the **`read_repository`** scope
6. Click **Create personal access token** and copy the token immediately

#### Step 2: Configure Git to Use the Token

```bash
# Store the token using git credential helper
git config --global credential.helper store
echo "https://oauth2:YOUR_TOKEN@gitlab.com" >> ~/.git-credentials
```

Or use the URL rewrite approach:

```bash
git config --global url."https://oauth2:YOUR_TOKEN@gitlab.com/".insteadOf "https://gitlab.com/"
```

### Option 2: SSH Key

#### Step 1: Generate an SSH key (if you don't have one)

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

#### Step 2: Add the public key to GitLab

1. Copy the public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
2. Go to your GitLab profile → **Edit profile** → **SSH Keys**
3. Paste the key and save

#### Step 3: Configure URL rewriting for SSH

```bash
# Rewrite HTTPS GitLab URLs to SSH
git config --global url."git@gitlab.com:".insteadOf "https://gitlab.com/"
```

---

## CI/CD Configuration

### GitHub Actions

When running `rhiza sync` in GitHub Actions against a **private** template repository in the **same organization**, the default `GITHUB_TOKEN` may be sufficient:

```yaml
- name: Sync Rhiza templates
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    git config --global url."https://${{ secrets.GITHUB_TOKEN }}@github.com/".insteadOf "https://github.com/"
    uvx rhiza sync
```

For private template repositories in a **different organization**, or when the default token lacks access, use a Personal Access Token stored as a repository secret:

```yaml
- name: Sync Rhiza templates
  run: |
    git config --global url."https://${{ secrets.RHIZA_TEMPLATE_TOKEN }}@github.com/".insteadOf "https://github.com/"
    uvx rhiza sync
```

To add a secret to your repository:

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `RHIZA_TEMPLATE_TOKEN`
4. Value: paste your PAT
5. Click **Add secret**

### GitLab CI

For private GitLab template repositories in the same instance, use the built-in CI token:

```yaml
sync_templates:
  script:
    - git config --global url."https://oauth2:${CI_JOB_TOKEN}@gitlab.com/".insteadOf "https://gitlab.com/"
    - uvx rhiza sync
```

For cross-instance or cross-group access, use a Project Access Token or Group Access Token stored as a CI/CD variable:

```yaml
sync_templates:
  script:
    - git config --global url."https://oauth2:${RHIZA_TEMPLATE_TOKEN}@gitlab.com/".insteadOf "https://gitlab.com/"
    - uvx rhiza sync
```

---

## Verifying Your Setup

After configuring credentials, verify that Git can access your template repository before running `rhiza sync`:

```bash
# Replace with your actual template repository
git ls-remote https://github.com/myorg/my-templates.git
```

If the command lists refs without prompting for a password, your credentials are correctly configured. You can then run `rhiza sync` normally.

---

## Troubleshooting

### Error: `fatal: could not read Username for 'https://github.com'`

Git cannot find any credentials for the URL. Choose one of the authentication options above and configure it before retrying.

### Error: `fatal: repository 'https://github.com/myorg/my-templates.git/' not found`

This can mean either:
- The repository does not exist or the `owner/repo` path in `template.yml` is incorrect
- The credentials are valid but the token does not have access to the repository (check token scopes)
- The repository is private and no credentials are configured at all

### Error: `Permission denied (publickey)`

Your SSH key is not recognised by the server. Verify that:
1. The public key (`~/.ssh/id_ed25519.pub`) has been added to your GitHub/GitLab account
2. The SSH agent is running and the key is loaded: `ssh-add ~/.ssh/id_ed25519`
3. You can reach the host: `ssh -T git@github.com`

### Token expired or revoked

Tokens have expiry dates. If `rhiza sync` suddenly fails after working previously, check whether your PAT has expired and generate a new one.

### CI: `Repository not found` despite correct credentials

Ensure the secret containing your token is:
- Correctly named in the workflow YAML (e.g., `secrets.RHIZA_TEMPLATE_TOKEN`)
- Available to the workflow (organization secrets may need to be explicitly shared with repositories)
- Not expired

---

## Related Documentation

- [`.rhiza/docs/TOKEN_SETUP.md`](../.rhiza/docs/TOKEN_SETUP.md) — PAT setup for the automated Rhiza sync workflow
- [`.rhiza/docs/PRIVATE_PACKAGES.md`](../.rhiza/docs/PRIVATE_PACKAGES.md) — Using private Python packages as dependencies
- [GitHub: Creating a personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [GitLab: Personal access tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
- [GitHub: SSH key setup](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitLab: SSH key setup](https://docs.gitlab.com/ee/user/ssh.html)

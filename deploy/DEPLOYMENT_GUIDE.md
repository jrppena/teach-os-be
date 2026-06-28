# Full Stack Deployment Guide

Step-by-step guide for deploying a **FastAPI backend on AWS EC2 (free tier)** and a **Vite + React frontend on Vercel**, sharing a single custom domain — backend at `api.<domain>`, frontend at `www.<domain>`.

## References

| Topic | Link |
|---|---|
| GitHub Actions docs | https://docs.github.com/en/actions |
| GitHub Container Registry (GHCR) | https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry |
| Docker build-push-action | https://github.com/docker/build-push-action |
| appleboy/ssh-action | https://github.com/appleboy/ssh-action |
| appleboy/scp-action | https://github.com/appleboy/scp-action |
| AWS EC2 free tier | https://aws.amazon.com/free/ |
| AWS Elastic IP pricing | https://aws.amazon.com/ec2/pricing/on-demand/#Elastic_IP_Addresses |
| AWS Budgets docs | https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html |
| Nginx reverse proxy guide | https://nginx.org/en/docs/beginners_guide.html |
| Certbot (Let's Encrypt) | https://certbot.eff.org/instructions?os=ubuntufocal&certifiedServer=nginx |
| Alembic migrations | https://alembic.sqlalchemy.org/en/latest/tutorial.html |
| Vercel custom domains | https://vercel.com/docs/projects/domains/add-a-domain |
| Namecheap DNS records guide | https://www.namecheap.com/support/knowledgebase/article.aspx/434/2237/how-do-i-set-up-host-records-for-a-domain/ |
| Docker Compose reference | https://docs.docker.com/compose/compose-file/ |

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11), Uvicorn, Alembic, asyncpg |
| Database | Managed PostgreSQL (Neon/Supabase/Railway) |
| Container | Docker (existing `Dockerfile`) |
| CI/CD | GitHub Actions → GHCR → EC2 via SSH |
| Server | AWS EC2 t3.micro (free tier), Ubuntu 24.04 |
| Reverse proxy | Nginx + Let's Encrypt (certbot) |
| Frontend | Vite + React on Vercel |
| Domain | Namecheap (any registrar works) |

---

## Architecture

```
GitHub push (master)
  └─ Actions: build Dockerfile ──► GHCR (ghcr.io/<owner>/<repo>:latest, :sha)
       └─ Actions: SSH to EC2 ──► write .env (from secret) ─► docker compose pull
                                  └─► alembic upgrade head ─► docker compose up -d

EC2 (Ubuntu, t3.micro, Elastic IP)
  Internet ──443/80──► Nginx (host) ──► 127.0.0.1:8000 ──► app container (uvicorn)
                                                              │
                                                              └──► managed Postgres (external, SSL)

Domain split:
  api.<domain>        → EC2 (A record → Elastic IP)
  www.<domain>        → Vercel (CNAME)
  <domain>            → Vercel (A record → 76.76.21.21, redirects to www)
```

The Docker image is built in CI (not on the server) to avoid taxing the 1 GB instance RAM. The
container binds only to `127.0.0.1:8000` — Nginx is the only public entry point (ports 80/443).
Port 8000 is never opened in the security group.

---

## Part 1 — Repo Files

Add these files to your backend repo before anything else.

### 1.1 `.github/workflows/production.yaml`

The workflow has two jobs that run in sequence: **build** (compiles the Docker image and pushes it
to GHCR) and **deploy** (SSHes into the EC2 instance and releases the new image).

```yaml
name: Deploy to Production

on:
  push:
    branches: [master]      # auto-deploy on every push to master
  workflow_dispatch:        # also allow manual trigger from the Actions tab

# Prevents two deploys from running simultaneously. If a new push comes in
# while a deploy is in progress, it waits — it does NOT cancel the current one.
concurrency:
  group: production-deploy
  cancel-in-progress: false

env:
  # github.repository is automatically "<owner>/<repo>", already lowercase — safe for GHCR.
  IMAGE: ghcr.io/${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write       # required to push images to GHCR with GITHUB_TOKEN
    steps:
      # Check out the repo so the Dockerfile and source code are available to the runner.
      - uses: actions/checkout@v4

      # Enable Docker BuildKit (faster builds, layer caching, multi-platform support).
      - uses: docker/setup-buildx-action@v3

      # Authenticate to GHCR using the auto-generated GITHUB_TOKEN (no PAT needed for push).
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # Build the image from the existing Dockerfile and push two tags:
      #   :latest   — always points to the most recent successful build
      #   :<sha>    — immutable tag tied to the exact commit, useful for rollbacks
      # cache-from/to uses GitHub Actions cache to speed up repeated builds by
      # reusing unchanged layers (e.g. the pip install layer when only src/ changes).
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: |
            ${{ env.IMAGE }}:latest
            ${{ env.IMAGE }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build            # only runs if the build job succeeds
    runs-on: ubuntu-latest
    steps:
      # Check out the repo so we can SCP the compose file to the server.
      - uses: actions/checkout@v4

      # Copy deploy/docker-compose.prod.yml to /opt/<your-app-name>/ on the EC2 instance.
      # strip_components: 1 drops the "deploy/" prefix so the file lands at the target root.
      # This keeps the compose file in sync with the repo on every deploy.
      - uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          source: deploy/docker-compose.prod.yml
          target: /opt/<your-app-name>
          strip_components: 1

      # SSH into the instance and execute the release steps in order.
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            # Exit immediately on any error, treat unset variables as errors,
            # and propagate pipe failures (e.g. if base64 fails, don't silently continue).
            set -euo pipefail

            cd /opt/<your-app-name>

            # Decode the base64-encoded production .env from the GitHub Secret and write
            # it to disk. Base64 encoding avoids shell quoting issues with multiline values
            # (e.g. the Firebase private key RSA block).
            echo "${{ secrets.PROD_ENV_B64 }}" | base64 -d > .env

            # Authenticate to GHCR on the server side so docker can pull the private image.
            # GHCR_PAT is a classic PAT with read:packages scope — separate from GITHUB_TOKEN
            # which only works for push, not pull from a remote host.
            echo "${{ secrets.GHCR_PAT }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin

            # Pull the latest image from GHCR to the instance before stopping the old container.
            # This minimises downtime — the pull happens while the old version is still running.
            docker compose -f docker-compose.prod.yml pull

            # Run database migrations in a one-off container before swapping the app.
            # --rm removes the container after it exits so it doesn't accumulate.
            # The image already contains alembic.ini + migrations/ (via COPY . . in Dockerfile).
            docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

            # Start (or restart) the container using the newly pulled image.
            # -d runs it in the background (detached mode).
            docker compose -f docker-compose.prod.yml up -d

            # Remove dangling images (old layers no longer referenced by any tag) to free disk space.
            docker image prune -f
```

> **Reference:** [GitHub Actions workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) · [appleboy/ssh-action](https://github.com/appleboy/ssh-action) · [appleboy/scp-action](https://github.com/appleboy/scp-action)

---

### 1.2 `deploy/docker-compose.prod.yml`

Defines the runtime container on the EC2 instance. Only used on the server — not in local dev.

```yaml
services:
  api:
    # Pull the image built by the CI workflow from GHCR.
    image: ghcr.io/<github-owner>/<repo-name>:latest

    # Always restart the container if it crashes or the server reboots.
    restart: always

    # Load all environment variables from the .env file written by the deploy workflow.
    # This keeps secrets off the command line and out of the compose file itself.
    env_file: .env

    ports:
      # Bind only to localhost — Nginx (running on the host) is the only process that
      # needs to reach the container. Port 8000 is never exposed to the public internet.
      - "127.0.0.1:8000:8000"

    healthcheck:
      # Use Python's built-in urllib instead of curl/wget — both are absent in python:slim.
      # Exits 0 (healthy) if /health returns HTTP 200, exits 1 (unhealthy) otherwise.
      test:
        [
          "CMD", "python", "-c",
          "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health').status==200 else sys.exit(1)",
        ]
      interval: 30s   # check every 30 seconds
      timeout: 5s     # fail the check if it takes longer than 5 seconds
      retries: 3      # mark unhealthy after 3 consecutive failures
```

> **Important:** The service name **must stay `api`** — the deploy script runs
> `docker compose run --rm api alembic upgrade head` to target it by name.
>
> **Reference:** [Docker Compose healthcheck](https://docs.docker.com/compose/compose-file/05-services/#healthcheck) · [Docker Compose ports](https://docs.docker.com/compose/compose-file/05-services/#ports)

---

### 1.3 `deploy/nginx/<your-app>.conf`

Nginx acts as a reverse proxy — it receives public HTTPS traffic and forwards it to the app
container on localhost. Certbot will rewrite this file to add the TLS (port 443) server block
and an automatic HTTP → HTTPS redirect when you run it in Part 6.

```nginx
server {
    listen 80;
    # Replace with your real API subdomain before installing on the server.
    server_name api.<your-domain>;

    location / {
        # Forward all requests to the Uvicorn app container on localhost.
        proxy_pass http://127.0.0.1:8000;

        # Pass the original Host header so the app knows which domain was requested.
        proxy_set_header Host              $host;

        # Pass the real client IP to the app (otherwise all requests appear to come from 127.0.0.1).
        proxy_set_header X-Real-IP         $remote_addr;

        # Append the client IP to the X-Forwarded-For chain (standard proxy header).
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;

        # Tell the app whether the original request was HTTP or HTTPS.
        # The app uses this to build correct redirect URLs.
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> **Reference:** [Nginx reverse proxy docs](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) · [Understanding proxy_set_header](https://nginx.org/en/docs/http/ngx_http_core_module.html#server)

---

### 1.4 `.gitignore` additions

```
# SSH private key — never commit; anyone with it can log into your server
*.pem

# Production env file — contains real secrets; encode into PROD_ENV_B64 instead
.env.production
```

---

### 1.5 `Dockerfile`

The CI workflow builds from this file unchanged. It lives at the repo root.

```dockerfile
# Use the official slim Python 3.11 image as the base.
# "slim" strips development tools and docs — smaller image, faster pulls.
FROM python:3.11-slim

WORKDIR /app

# PYTHONDONTWRITEBYTECODE: prevents Python from writing .pyc bytecode files to disk.
# PYTHONUNBUFFERED: forces stdout/stderr to be unbuffered so logs appear in real time
#                   in `docker logs` without being held in a buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# gcc is needed to compile C extensions (e.g. asyncpg's PostgreSQL driver).
# libpq-dev provides the PostgreSQL client headers that asyncpg links against.
# The apt cache is removed afterwards to keep the layer small.
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency manifest first, before any source code.
# Docker caches each RUN layer — if pyproject.toml hasn't changed, the pip install
# layer is reused on the next build even if src/ has changed, saving significant time.
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy the rest of the application (src/, migrations/, alembic.ini, etc.).
# Comes after pip install so code changes don't invalidate the dependency cache layer.
COPY . .

# Create a non-root user and transfer ownership of /app to it.
# Running as root inside a container is a security risk — if the container is
# compromised, the attacker has root inside it. A dedicated user limits the blast radius.
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Document that the app listens on port 8000 (informational only — does not publish the port).
EXPOSE 8000

# Start Uvicorn (ASGI server) binding to all interfaces inside the container.
# ${PORT:-8000} defaults to 8000 but allows the port to be overridden via an env var,
# which is useful on platforms like Railway that assign a dynamic port.
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**`.dockerignore`** — prevents these files from being sent to the Docker build context, keeping
the image lean and avoiding accidental inclusion of secrets:

```
.git               # git history is not needed in the image
.gitignore
.env               # local secrets — never bake into the image
.venv              # local virtual environment — dependencies are installed fresh in the image
__pycache__        # compiled bytecode from local dev — regenerated inside the image
*.pyc
*.pyo
*.pyd
.pytest_cache
.ruff_cache
*.egg-info
dist
build
README.md          # docs are not needed at runtime
AGENTS.md
CLAUDE.md
```

> **Reference:** [Docker best practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/) · [.dockerignore syntax](https://docs.docker.com/engine/reference/builder/#dockerignore-file) · [python Docker Hub](https://hub.docker.com/_/python)

Commit and push all of the above to `master` before proceeding.

---

## Part 2 — AWS EC2 Setup

> **Reference:** [AWS EC2 getting started](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html) · [EC2 free tier eligibility](https://aws.amazon.com/free/)

### 2.1 Launch the instance

1. AWS Console → **EC2 → Launch Instance**
2. **Name:** anything (e.g. `my-project`)
3. **AMI:** Ubuntu Server 24.04 LTS
   - *Why Ubuntu?* Well-documented, large community, and snap (used for certbot) works out of the box.
4. **Instance type:** `t3.micro` (free tier — 750 hrs/mo for 12 months)
   - *Why not t2.micro?* t3 has burstable CPU credits and is available in newer regions. Use t2.micro if t3 isn't free-tier eligible in your region.
5. **Key pair:** click **Create new key pair**
   - Name: `<your-app>-admin`
   - Type: RSA, Format: `.pem`
   - Download and store it securely — AWS will never let you download it again.
   - *Why a key pair?* EC2 disables password SSH by default. The key pair is the only way to log in.
6. **Network settings (Security Group):**
   - ✅ Allow SSH (port 22) — restrict to your IP if possible for security
   - ✅ Allow HTTPS (port 443) — required for the TLS endpoint Nginx serves
   - ✅ Allow HTTP (port 80) — required for certbot's domain ownership challenge
   - ❌ Do NOT open port 8000 — the container binds to localhost only; Nginx is the public gatekeeper
7. **Storage:** change `8` GiB → `20` GiB
   - *Why 20 GB?* Free tier allows up to 30 GB. The default 8 GB fills quickly with Ubuntu, Docker layers, and the 2 GB swap file.
8. **Advanced details:** skip entirely — user data scripts, IAM roles, and spot options are not needed here.
9. Click **Launch instance**

### 2.2 Allocate an Elastic IP

By default, EC2 assigns a new public IP every time the instance starts. An Elastic IP is a **static
public IP** that stays the same across reboots — DNS records and GitHub Secrets point at it permanently.

1. EC2 left sidebar → **Network & Security → Elastic IPs**
2. Click **Allocate Elastic IP address** → leave defaults → **Allocate**
3. Select the new IP → **Actions → Associate Elastic IP address**
4. **Instance:** select your instance → **Associate**

> **Cost note:** Elastic IPs are free while associated with a running instance. If you stop the
> instance, you'll be charged ~$0.005/hr for the unattached IP. Either release it or keep the
> instance running. [AWS Elastic IP pricing](https://aws.amazon.com/ec2/pricing/on-demand/#Elastic_IP_Addresses)

Note your Elastic IP — you'll use it in DNS, GitHub Secrets, and SSH commands.

---

## Part 3 — DNS Setup (Namecheap)

> **Reference:** [Namecheap host records guide](https://www.namecheap.com/support/knowledgebase/article.aspx/434/2237/how-do-i-set-up-host-records-for-a-domain/)

DNS records map human-readable domain names to IP addresses. You need three records total — one
for the backend, two for the frontend.

Go to **Namecheap → Domain List → Manage → Advanced DNS**.

1. **Delete** all default Namecheap parking records (`www` CNAME → parkingpage, `@` URL Redirect).
   *They conflict with real records and will prevent Vercel verification.*

2. Add these records:

| Type | Host | Value | Why |
|---|---|---|---|
| A Record | `api` | `<Elastic IP>` | Points `api.<domain>` directly at your EC2 server |
| A Record | `@` | `76.76.21.21` | Points the apex domain at Vercel's IP for the frontend |
| CNAME Record | `www` | `<provided by Vercel>` | Points `www.<domain>` at Vercel via an alias |

> **A Record vs CNAME:** An A record maps a name to an IP address. A CNAME maps a name to another
> name (an alias). Apex domains (`@`) cannot use CNAMEs per DNS spec — they must use A records.
> Namecheap enforces this.

> Add the `api` A record now. Add `@` and `www` after configuring Vercel (Part 9) — Vercel shows
> the exact CNAME value when you add your domain there.

Verify propagation before running certbot (DNS must resolve first or certbot will fail):
```bash
# Queries the DNS system for the IP address of api.<your-domain>.
# Should return your Elastic IP within 5–15 minutes of adding the record.
dig +short api.<your-domain>
```

---

## Part 4 — EC2 Bootstrap

SSH into the instance using the admin key pair you downloaded in Part 2:

```bash
# chmod 400 restricts the key to owner-read-only.
# SSH rejects keys with open permissions (e.g. 644) as a security measure.
chmod 400 /path/to/<your-app>-admin.pem

# -i specifies the identity (private key) file to use for authentication.
# ubuntu is the default user on Ubuntu AMIs.
ssh -i /path/to/<your-app>-admin.pem ubuntu@<Elastic IP>
```

Type `yes` when prompted about the host fingerprint — this confirms you're connecting to the right
server and saves the fingerprint to `~/.ssh/known_hosts` so you're not asked again.

---

**Step 1 — Install Docker**

```bash
# Refresh the apt package index so it knows about the latest available versions.
sudo apt-get update

# Download and run Docker's official install script. This adds Docker's apt repo,
# installs the Docker Engine and the Compose plugin (docker compose), and starts the daemon.
# Using the official script is recommended over the Ubuntu default repo (older version).
curl -fsSL https://get.docker.com | sudo sh

# Add the ubuntu user to the docker group so it can run docker commands without sudo.
# Without this, every docker command requires sudo.
sudo usermod -aG docker ubuntu
```

> **Reference:** [Docker install on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

---

**Step 2 — Re-login** (required for the docker group change to take effect)

```bash
# End the current SSH session. The group membership change from usermod only takes
# effect in new sessions — the current shell still has the old group list.
exit

# Open a new SSH session. The ubuntu user now has docker group permissions.
ssh -i /path/to/<your-app>-admin.pem ubuntu@<Elastic IP>
```

---

**Step 3 — Install Nginx, certbot, swap, and create the app directory**

```bash
# Install Nginx web server from Ubuntu's default apt repository.
sudo apt-get install -y nginx

# Install certbot (Let's Encrypt client) via snap — the snap version is always up to date.
# --classic allows certbot to access the system outside the snap sandbox (needed for Nginx config).
sudo snap install --classic certbot

# Create a symlink so `certbot` is available as a system command (in /usr/bin/).
sudo ln -sf /snap/bin/certbot /usr/bin/certbot

# Create a 2 GB swap file. A t3.micro has 1 GB RAM — swap prevents OOM kills during
# Docker image pulls and container restarts which can briefly spike memory usage.
sudo fallocate -l 2G /swapfile

# Restrict the swap file to root-only read/write (required by Linux for security).
sudo chmod 600 /swapfile

# Format the file as swap space.
sudo mkswap /swapfile

# Activate the swap file for the current session.
sudo swapon /swapfile

# Add the swap entry to /etc/fstab so it is automatically activated on every reboot.
# tee -a appends to the file (equivalent to >> but works with sudo).
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Create the directory where the app files (compose file, .env) will live.
sudo mkdir -p /opt/<your-app-name>

# Transfer ownership to the ubuntu user so the deploy workflow (which SSH's in as ubuntu)
# can write files there without needing sudo.
sudo chown ubuntu:ubuntu /opt/<your-app-name>
```

> **Reference:** [Linux swap space](https://www.digitalocean.com/community/tutorials/how-to-add-swap-space-on-ubuntu-22-04) · [Certbot on Ubuntu](https://certbot.eff.org/instructions?os=ubuntufocal&certifiedServer=nginx)

---

**Step 4 — Verify everything installed correctly**

```bash
# Run all four checks in one line. If any command fails, the chain stops (due to &&).
# Expected output: Docker 29+, nginx 1.24+, certbot 2+, 2.0Gi swap in the free -h table.
docker --version && nginx -v && certbot --version && free -h
```

---

## Part 5 — Deploy SSH Key (for GitHub Actions)

GitHub Actions needs its own SSH key to log into the EC2 instance during deploys. This is separate
from your admin key — it can be revoked independently without affecting your own access.

Run this **on your local machine** (not on the EC2):

```bash
# Generate a new ed25519 key pair. ed25519 is faster and more secure than RSA.
# -f specifies the output file path (creates deploy_key and deploy_key.pub).
# -N "" sets an empty passphrase — required for automated (non-interactive) use.
ssh-keygen -t ed25519 -f /path/to/deploy_key -N ""

# Print the public key — copy this entire line.
cat /path/to/deploy_key.pub
```

Copy the public key output, then **on the EC2 instance**:

```bash
# Append the public key to the authorized_keys file.
# SSH allows login to this account for anyone who holds the matching private key.
# >> appends rather than overwrites, preserving your existing admin key.
echo "<paste public key here>" >> ~/.ssh/authorized_keys

# Confirm the key was added correctly — should print back the line you just added.
tail -1 ~/.ssh/authorized_keys
```

The **private** key (`deploy_key`) goes into the `EC2_SSH_KEY` GitHub Secret in Part 7.

> **Reference:** [SSH key-based authentication](https://www.digitalocean.com/community/tutorials/how-to-configure-ssh-key-based-authentication-on-a-linux-server) · [GitHub Actions SSH deploy pattern](https://github.com/appleboy/ssh-action#usage)

---

## Part 6 — Nginx + HTTPS

> **Reference:** [Nginx beginner's guide](https://nginx.org/en/docs/beginners_guide.html) · [Certbot Nginx on Ubuntu](https://certbot.eff.org/instructions?os=ubuntufocal&certifiedServer=nginx)

Still on the EC2 instance. Open a new Nginx server block config file:

```bash
# nano is a simple terminal text editor. Create the config file at the standard
# sites-available location (Nginx's convention for available — but not yet active — configs).
sudo nano /etc/nginx/sites-available/<your-app>
```

Paste the nginx config from Part 1.3 with your real domain substituted, then save (`Ctrl+O` → Enter → `Ctrl+X`).

```bash
# Create a symlink from sites-enabled to sites-available to activate the config.
# Nginx reads from sites-enabled — this is the standard enable/disable pattern.
sudo ln -sf /etc/nginx/sites-available/<your-app> /etc/nginx/sites-enabled/

# Remove the default Nginx placeholder site so it doesn't conflict.
sudo rm -f /etc/nginx/sites-enabled/default

# Test the Nginx configuration for syntax errors before reloading.
# Always run this — a bad config will prevent Nginx from restarting.
sudo nginx -t

# Reload Nginx to apply the new config without dropping existing connections (graceful reload).
# restart would briefly drop connections; reload does not.
sudo systemctl reload nginx
```

Issue the TLS certificate (DNS from Part 3 must have propagated first):

```bash
# --nginx: automatically edits your Nginx config to add the 443 server block
#           and set up HTTP → HTTPS redirect.
# -d: the domain to issue a certificate for (must resolve to this server's IP).
# Certbot also installs a systemd timer for automatic certificate renewal every 60 days.
sudo certbot --nginx -d api.<your-domain>
```

Enter your email when prompted (used for expiry notifications), agree to the terms.
Certbot rewrites the Nginx config, reloads Nginx, and sets up auto-renewal.

---

## Part 7 — GitHub Secrets

> **Reference:** [GitHub encrypted secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

Secrets are encrypted at rest by GitHub and injected as environment variables into workflow runs.
They are never exposed in logs.

Go to **GitHub → your repo → Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Value | Why it's needed |
|---|---|---|
| `EC2_HOST` | Your Elastic IP | SSH/SCP destination for the deploy job |
| `EC2_USER` | `ubuntu` | SSH login user (default on Ubuntu AMIs) |
| `EC2_SSH_KEY` | Contents of `deploy_key` (full private key PEM) | Authenticates GitHub Actions to the EC2 instance |
| `GHCR_PAT` | Classic PAT with `read:packages` scope | Lets the EC2 server pull the private image from GHCR |
| `PROD_ENV_B64` | base64-encoded production `.env` | Delivers all app config to the server without shell quoting issues |

**Getting `EC2_SSH_KEY`:**
```bash
# Print the full private key — copy everything including the BEGIN/END lines.
cat /path/to/deploy_key
```

**Getting `GHCR_PAT`:**
GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)** →
Generate new token → scope: `read:packages` only → generate and copy immediately.

> Use classic tokens, not fine-grained — fine-grained tokens don't support `read:packages` for GHCR.

---

### Building `PROD_ENV_B64`

Create a production `.env` file locally (never commit this file):

```bash
# Copy your local .env as a starting point, then edit the values that differ in production.
cp .env .env.production
nano .env.production
```

Minimum production `.env` contents:

```
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>/<db>?sslmode=require
APP_ENVIRONMENT=production
APP_CORS_ORIGINS=https://<your-domain>,https://www.<your-domain>
APP_SECRET_KEY=<random 32+ char string>
PROVIDER_KEY_ENCRYPTION_KEY=<fernet key>
FIREBASE_PROJECT_ID=...
FIREBASE_PRIVATE_KEY_ID=...
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=...
FIREBASE_CLIENT_ID=...
FIREBASE_CLIENT_X509_CERT_URL=...
# add all other required env vars
```

Important notes:
- `DATABASE_URL` scheme must be `postgresql+asyncpg://` (not `postgresql://`) — the asyncpg driver requires it.
- `FIREBASE_PRIVATE_KEY` must stay on **one line** with literal `\n` characters — the app calls `.replace("\\n", "\n")` at startup to restore the real newlines.
- `APP_ENVIRONMENT=production` causes the app to hide `/docs` and `/redoc` from the public.
- `APP_CORS_ORIGINS` must list the exact origins the browser frontend is served from — missing an origin causes all API calls to be rejected by the browser.

Encode the file into a single base64 string:

```bash
# -w0 disables line wrapping (outputs one long line with no newlines).
# Without -w0, the default 76-char wrapping causes "base64: invalid input" when the
# workflow tries to decode it on the server (shell interpolation breaks multiline values).
base64 -w0 .env.production    # Linux / WSL

# macOS outputs without -w0 flag (it wraps by default but base64 -d handles it fine on mac).
base64 .env.production        # macOS
```

Paste the single-line output into the `PROD_ENV_B64` secret. **Never share or log this value.**

---

## Part 8 — First Deploy

```bash
cd /path/to/your-backend-repo

# Stage the new CI/CD files. Be specific rather than using git add .
# to avoid accidentally committing .env.production or *.pem files.
git add .github deploy .gitignore

git commit -m "Add GitHub Actions production deploy workflow"

# Push to master to trigger the workflow automatically (on.push.branches: [master]).
git push origin master
```

Go to **GitHub → Actions** and watch the two-job workflow:
1. **build** — compiles the Docker image and pushes to GHCR (~2–4 min, faster on subsequent runs due to layer caching)
2. **deploy** — SSHes to EC2, writes `.env`, runs migrations, restarts the container (~1 min)

Verify the deploy succeeded:

```bash
# On the EC2 instance — check container status. "healthy" means the healthcheck passed.
docker compose -f /opt/<your-app>/docker-compose.prod.yml ps

# Hit the health endpoint directly on the container (bypasses Nginx).
curl -s localhost:8000/health
# Expected: {"status":"ok"}
```

From your local machine or browser:

```bash
# Hit the health endpoint through Nginx + TLS. Confirms the full stack is working:
# DNS → Nginx → container → FastAPI.
curl -s https://api.<your-domain>/health
# Expected: {"status":"ok"}
```

---

## Part 9 — Vercel Frontend Domain

> **Reference:** [Vercel custom domains](https://vercel.com/docs/projects/domains/add-a-domain) · [Vercel DNS records](https://vercel.com/docs/projects/domains/dns-records)

1. **Vercel → your project → Settings → Domains → Add**
2. Type `<your-domain>` (the apex, without `www`) → **Connect to environment: Production**
3. Check **"Redirect apex domains to www (recommended)"** — Vercel handles the redirect automatically.
4. Click **Add Domains**
5. Vercel shows a required CNAME record under the **DNS Records** tab, e.g.:
   `www` → `f6792c48e5cc51d3.vercel-dns-017.com.`
   *Use the exact value Vercel shows you — it is unique to your project.*
6. Go back to **Namecheap → Advanced DNS** and add:
   - `A Record` · `@` · `76.76.21.21` (Vercel's apex IP for the HTTP → HTTPS redirect)
   - `CNAME Record` · `www` · `<value from Vercel>`
   > If a conflicting `@` record already exists (e.g. Namecheap's URL Redirect), delete it first — two records for the same host conflict.
7. Back in Vercel, click **Refresh** — domains turn green once DNS propagates (5–15 min).

### Frontend environment variables

In **Vercel → your project → Settings → Environment Variables** (select **Production** environment):

```
# The base URL your frontend uses to call the backend API.
VITE_API_BASE_URL=https://api.<your-domain>/api/v1

# The public URL of the frontend app itself (used for redirects, canonical links, etc.).
VITE_APP_URL=https://www.<your-domain>
```

Trigger a new Vercel deployment after adding these so the build picks them up.

---

## Part 10 — AWS Budget + Auto-Stop

> **Reference:** [AWS Budgets docs](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) · [AWS Budget Actions](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-controls.html)

Set a hard cost ceiling so an unexpected spike (e.g. accidental data transfer) doesn't run up a bill.

1. AWS Console → **Billing → Budgets → Create budget**
2. Choose **Customize** (not a template — templates create daily budgets which don't support auto-stop actions)
3. **Period:** Monthly · **Budget type:** Cost · **Amount:** `$1`
   - *Why $1?* The t3.micro + 20 GB EBS is free tier eligible for 12 months. A $1 alert catches anything unexpected (runaway data transfer, second instance, etc.) before it compounds.
4. **Alert:** Threshold `100%` of budgeted amount · Trigger `Actual` · add your email
   - *Actual vs Forecasted:* Actual triggers when you've already spent $1. Forecasted would trigger if AWS projects you'll spend $1 by month end — useful for early warning but can be noisy.
5. **Add action → Automate instances to stop for EC2 or RDS**
   - Select your EC2 region
   - Select your instance
   - AWS auto-creates the required IAM role with EC2 stop permissions
6. Click **Create budget**

> **Free tier reminder:** Your t3.micro is free for 750 hrs/mo (enough for 24/7 for one instance)
> for the first 12 months. Main costs after the free tier or outside it:
> - EC2 compute: ~$0.0104/hr (t3.micro, us-east-1)
> - EBS storage: ~$0.08/GB/month (20 GB = ~$1.60/mo)
> - Data transfer: first 100 GB/month outbound is free; $0.09/GB after
> - Elastic IP: free when associated with a running instance; ~$0.005/hr when not

---

## Part 11 — Verification Checklist

Work through these in order — each one builds on the previous.

- [ ] `dig +short api.<your-domain>` returns your Elastic IP (DNS propagated)
- [ ] `curl -s https://api.<your-domain>/health` → `{"status":"ok"}` (Nginx + TLS + app running)
- [ ] Unauthenticated API call → `401` (auth middleware is active)
- [ ] Authenticated API call from the frontend → `200` (Firebase init + DB + CORS all working)
- [ ] `https://www.<your-domain>` → frontend loads correctly
- [ ] `https://<your-domain>` → redirects to `www` (Vercel apex redirect working)
- [ ] Push a trivial code change → GitHub Actions runs both jobs → new image deployed automatically
- [ ] `docker compose -f docker-compose.prod.yml ps` on EC2 shows container as `healthy`
- [ ] AWS Budget confirmation email received

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ssh: no key found` in Actions | `EC2_SSH_KEY` secret has the wrong value | Re-paste the **private** key — it starts with `-----BEGIN OPENSSH PRIVATE KEY-----`. Don't paste the `.pub` file. |
| `base64: invalid input` in Actions | `PROD_ENV_B64` contains line breaks | Re-encode with `base64 -w0 .env.production` on Linux. The output must be one continuous line. |
| Certbot fails with DNS error | `api.<domain>` hasn't propagated yet | Run `dig +short api.<your-domain>` — if it doesn't return your IP, wait 5–15 min and retry. |
| Container shows `unhealthy` | App crashed on startup (bad env var, DB unreachable) | Run `docker compose logs api` on EC2 to see the traceback. |
| CORS error in browser | `APP_CORS_ORIGINS` missing the FE origin | Update `PROD_ENV_B64` with the correct origins and redeploy. |
| Vercel domain "Invalid Configuration" | DNS records not added or not propagated | Add the `@` A record and `www` CNAME in Namecheap. Wait 5–15 min, then click Refresh in Vercel. |
| Namecheap A record (`@`) fails to save | A conflicting `@` record already exists | Delete the existing `@` URL Redirect record first, then re-add the A record. |
| `docker compose pull` fails in deploy | GHCR_PAT expired or wrong scope | Regenerate the PAT with `read:packages` scope and update the GitHub secret. |
| Migrations fail during deploy | DB unreachable from EC2 or wrong `DATABASE_URL` | Check that `DATABASE_URL` uses `postgresql+asyncpg://` and the managed DB allows connections from the EC2 IP. |

# Implementation Plan: Unified VCOO Installer Endpoint

## Objective
Provide a single public endpoint (via the onboarding backend) that:
1. Validates a provision token (from control‑plane).
2. Retrieves a versioned tarball of the VCOO template from a private GitHub repository (using a GitHub token stored in the backend).
3. Extracts the tarball, applies V‑S‑specific customizations (skills, config overlays).
4. Installs Hermes Agent non‑interactively.
5. Registers the agent with the control‑plane (if not already done) and ensures the VCOO instance is ready to receive commands.

## Assumptions
- The onboarding backend is a FastAPI service running on a server with access to:
  - A GitHub personal‑access‑token (PAT) with `repo` scope for the private repo.
  - Environment variables: `GITHUB_TOKEN`, `CONTROL_PLANE_URL`, `CONTROL_PLANE_TOKEN`.
- The private repo follows the structure:
  ```
  vcoo-template/
    install-vcoo.sh          # entrypoint (will be replaced by our logic)
    scripts/hermes-bootstrap.sh
    skills/...               # VCOO skills
    cron-jobs/...
    config.yaml.template
    SOUL.md
    ...
  ```
- The tarball will be created as a GitHub Release asset named `vcoo-template-v<semver>.tar.gz`.
- The provision token is a JWT (or opaque string) that the backend can verify against the control‑plane `/validate-token` endpoint.
- Hermes Agent supports a non‑interactive mode via env var `HERMES_NONINTERACTIVE=1` or CLI flag `--no-prompt`.

## High‑Level Steps
1. **Control‑plane pre‑check** (done by the client before calling the endpoint):
   - Client obtains a provision token from the control‑plane (via `/provision`).
   - Client sends that token to the endpoint as a Bearer token or header.
2. **Endpoint `/vcoo/install`** (POST) receives:
   - `Authorization: Bearer <provision_token>`
   - Optional JSON body with client‑specific overrides (e.g., Discord token, Telegram bot token, selected modules).
3. **Backend logic**:
   a. Validate provision token via call to control‑plane.
   b. Determine latest release asset (or accept a version query param `?version=v1.2.3`).
   c. Download tarball from GitHub releases using the stored GITHUB_TOKEN.
   d. Extract to a temporary directory.
   e. Apply overlays:
      - Replace placeholder values in `config.yaml.template` with client‑provided data → `config.yaml`.
      - Copy/merge custom skills (if any) from a `custom/` directory supplied in the request (optional).
      - Ensure `SOUL.md` is populated with client name.
   f. Run `hermes-bootstrap.sh` (installs uv, creates venv, installs hermes‑agent, creates symlink).
   g. Run the equivalent of `install-vcoo.sh` steps inside the temp dir:
      - Copy skills to `~/.hermes/skills/versus‑multiagent‑orchestration/`.
      - Copy scripts to `~/.hermes/scripts/vcoo/` (rewrite shebang to venv python).
      - Install cron jobs (copy to `~/.hermes/cron/job-definitions/` and activate via `hermes cron create …`).
   h. Optionally register with control‑plane (if not already done) by sending a POST to `/agents/register` with agent info.
   i. Clean up temporary files.
4. **Response**:
   - `200 OK` with JSON `{ status: "ready", message: "VCOO instance installed and configured", hermes_version: "<version>" }`.
   - On error, appropriate HTTP status and error detail.

## Detailed Tasks

### 1. CI – Generate tarball
- **Workflow**: `.github/workflows/release.yml`
  - Trigger on push to `main` with tag `v*`.
  - Steps:
    1. Checkout repository.
    2. Set up Python (if needed for any pre‑processing).
    3. Create tarball: `tar -czvf vcoo-template-${{ github.ref_name }}.tar.gz --exclude='.git' --exclude='.github' .`
    4. Create GitHub Release (if not exists) using `gh release create`.
    5. Upload tarball as asset.

### 2. Backend – New endpoint
- File: `vcoo-onboarding/backend/routes/vcoo_install.py`
- Dependencies: `requests`, `python‑multipart`, `fastapi`.
- Pseudocode:
  ```python
  @router.post("/vcoo/install")
  async def install_vcoo(
      request: Request,
      authorization: Optional[str] = Header(None),
      version: Optional[str] = Query(None),
      body: Dict = Body(None)
  ):
      # 1. Extract token
      if not authorization or not authorization.startswith("Bearer "):
          raise HTTPException(401, "Missing or invalid Authorization header")
      token = authorization.split()[1]
      # 2. Validate with control‑plane
      async with httpx.AsyncClient() as client:
          resp = await client.post(
              f"{CONTROL_PLANE_URL}/validate-token",
              json={"token": token},
              headers={"Authorization": f"Bearer {CONTROL_PLANE_TOKEN}"}
          )
          if resp.status_code != 200:
              raise HTTPException(401, "Invalid provision token")
      # 3. Determine version
      if version is None:
          # fetch latest release
          async with httpx.AsyncClient() as gh:
              gh_resp = await gh.get(
                  "https://api.github.com/repos/<org>/<private-repo>/releases/latest",
                  headers={"Authorization": f"token {GITHUB_TOKEN}"}
              )
              release = gh_resp.json()
              tarball_url = next(a["browser_download_url"] for a in release["assets"] if a["name"].endswith(".tar.gz"))
              version = release["tag_name"]
      else:
          tarball_url = f"https://github.com/<org>/<private-repo>/releases/download/{version}/vcoo-template-{version}.tar.gz"
      # 4. Download tarball
      async with httpx.AsyncClient() as client:
          tar_resp = await client.get(tarball_url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
          tar_resp.raise_for_status()
          tarball_data = tar_resp.content
      # 5. Extract to temp dir
      with tempfile.TemporaryDirectory() as tmpdir:
          tar_path = os.path.join(tmpdir, "bundle.tar.gz")
          with open(tar_path, "wb") as f:
              f.write(tarball_data)
          subprocess.run(["tar", "-xzf", tar_path], cwd=tmpdir, check=True)
          extracted = os.path.join(tmpdir, "vcoo-template")  # adjust based on actual root dir inside tarball
          # 6. Apply overlays
          config_template = os.path.join(extracted, "config.yaml.template")
          config_dest = os.path.join(extracted, "config.yaml")
          # render template with body or env vars
          render_template(config_template, config_dest, body or {})
          # copy SOUL.md with client name if provided
          # copy custom skills if body contains "custom_skills": [...]
          # 7. Run hermes-bootstrap
          bootstrap_src = os.path.join(extracted, "scripts", "hermes-bootstrap.sh")
          subprocess.run(["bash", bootstrap_src], check=True)
          # 8. Install skills & scripts
          skills_dest = os.path.expanduser("~/.hermes/skills/versus-multiagent-orchestration")
          os.makedirs(skills_dest, exist_ok=True)
          shutil.copytree(os.path.join(extracted, "skills"), skills_dest, dirs_exist_ok=True)
          scripts_dest = os.path.expanduser("~/.hermes/scripts/vcoo")
          os.makedirs(scripts_dest, exist_ok=True)
          for script in Path(extracted).rglob("*.sh"):
              # rewrite shebang to point to venv python
              rewrite_shebang(script, scripts_dest / script.name, venv_python_path)
              shutil.copy2(script, scripts_dest / script.name)
              os.chmod(scripts_dest / script.name, 0o755)
          # 9. Install cron jobs
          cron_src = os.path.join(extracted, "cron-jobs")
          if os.path.isdir(cron_src):
              for job in Path(cron_src).glob("*.json"):
                  shutil.copy2(job, os.path.expanduser("~/.hermes/cron/job-definitions/"))
                  # activate via hermes cli
                  subprocess.run([
                      os.path.expanduser("~/.local/bin/hermes"),
                      "cron", "create",
                      f"--schedule={json.load(open(job))['schedule']}",
                      f"--name={job.stem}",
                      f"--prompt={json.load(open(job))['prompt']}"
                  ], check=True)
          # 10. Register with control‑plane (optional)
          # 11. Cleanup happens automatically with TemporaryDirectory
      return JSONResponse({"status":"ready","message":"VCOO installed","hermes_version": get_hermes_version()})
  ```

### 3. Helper: hermes-bootstrap.sh
- Place in `vcoo-template/scripts/hermes-bootstrap.sh`.
- Content:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  VENV_PATH="${HOME}/.hermes/scripts/vcoo/.venv"
  HERMES_BIN="${HOME}/.local/bin/hermes"
  if ! command -v uv &>/dev/null; then
      curl -LsSf https://astral.sh/uv/install.sh | sh
      export PATH="${HOME}/.local/bin:$PATH"
  fi
  if [[ ! -d "${VENV_PATH}" ]]; then
      uv venv --python python3.11 "${VENV_PATH}"
  fi
  source "${VENV_PATH}/bin/activate"
  uv pip install hermes-agent \
      google-api-python-client google-auth-httplib2 google-auth-oauthlib \
      reportlab weasyprint httpx pyyaml
  ln -sf "${VENV_PATH}/bin/hermes" "${HERMES_BIN}"
  echo "Hermes installed at ${HERMES_BIN}"
  ```

### 4. Overlay / templating
- Use `jinja2` or simple `envsubst` to replace placeholders in `config.yaml.template`:
  ```
  discord_token: {{ discord_token }}
  telegram_bot_token: {{ telegram_bot_token }}
  modules:
    - office: {{ enable_office | lower }}
    - mail: {{ enable_mail | lower }}
    # etc.
  ```
- Provide a small Python function `render_template(template_path, output_path, context)`.

### 5. Non‑interactive Hermes install
- Ensure the `hermes-bootstrap.sh` installs Hermes without prompting. The official Hermes installer already supports non‑interactive mode via env var `HERMES_NONINTERACTIVE=1`. We'll set that before invoking any Hermes CLI that might ask for input (e.g., `hermes config edit` should be avoided; we only use `hermes cron create` which is non‑interactive).

### 6. Integration with Control‑Plane (pre‑step)
- The client must first call the control‑plane `/provision` endpoint to get a token.
- That step is **outside** this endpoint but we document it as a prerequisite.
- The endpoint only validates the token; it does not generate a new one.

### 7. Testing Strategy
- **Unit tests** for the endpoint (using `pytest` and `httpx.AsyncClient` mocking GitHub and control‑plane calls).
- **Integration test** using a temporary GitHub repository (or a mock server) to verify tarball download and extraction.
- **End‑to‑end test** using the existing `run_vcoo_test.sh` adapted to:
  1. Spin up a disposable Ubuntu VM (Multipass or Docker).
  2. Obtain a fake provision token from a mock control‑plane.
  3. Call the endpoint with that token.
  4. Verify that `hermes --version` works, that skills are present, that cron jobs are installed, and that the config reflects the supplied overrides.
- Add a GitHub Actions workflow that runs the test on push/pull‑request.

### 8. Rollback / Cleanup
- Since the installation writes to user‑home directories (`~/.hermes`, `~/.local/bin`), we consider the operation idempotent: running it again will overwrite files with the same version.
- If a halfway failure occurs, we leave the temporary directory (auto‑cleaned) and no partial writes should have been committed (we perform all writes after extraction and validation). In case of failure after writing, we could log which step failed and leave a partial state; the user can re‑run.

### 9. Security Considerations
- The GitHub token must be stored as a secret in the backend environment (never logged).
- The provision token is validated via the control‑plane; we do not trust the client‑provided token directly.
- All network calls to GitHub and control‑plane use HTTPS with certificate verification.
- The temporary directory is created with `tempfile.TemporaryDirectory` (secure, auto‑removed).
- File permissions: extracted files are readable only by the user running the service (typically root or a dedicated service user). The final `hermes` symlink is placed in `~/.local/bin` owned by the user.

### 10. Documentation
- Update `README.md` in `vcoo-onboarding/backend` to describe the new endpoint, required headers, and example curl:
  ```bash
  curl -X POST https://onboarding.vcoo.dev/vcoo/install \
       -H "Authorization: Bearer <provision_token>" \
       -H "Content-Type: application/json" \
       -d '{"discord_token":"xoxb-...","telegram_bot_token":"123456:ABC...","enable_office":true,"enable_mail":false}'
  ```
- Provide a section in the operator manual explaining the prerequisite of obtaining a provision token from the control‑plane.

## Success Criteria
- [ ] CI workflow successfully creates a versioned tarball release.
- [ ] Backend endpoint returns `200 OK` and correctly installs Hermes with the specified version.
- [ ] After execution, `hermes --version` matches the version from the tarball.
- [ ] Custom skills and configs are present under `~/.hermes/...`.
- [ ] Cron jobs are active (`hermes cron list` shows entries).
- [ ] Invalid or missing provision token results in `401 Unauthorized`.
- [ ] The endpoint works non‑interactively (no prompts for input).
- [ ] Automated tests (unit + integration) pass in CI.

---
*End of Plan*
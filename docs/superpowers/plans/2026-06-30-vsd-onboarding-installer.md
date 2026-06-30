# Deployment Plan: Versusd Onboarding Installer

**Goal:** Verify that the public one‑liner installer (`install_vsd.sh`) correctly installs only the `versusd` watchdog, stores the provision token, enables the `versusd-onboarding.service`, and that the onboarding script (`onboard.sh`) securely retrieves the VCOO installation script from the backend using the stored token.

## Prerequisites
- Access to the `vcoo-onboarding` repository (local clone).
- A clean test environment (e.g., a temporary directory or VM) to simulate installation.
- `bash` and standard Unix utilities (`sed`, `mkdir`, `chmod`, `chown`, `systemctl` – mocked if necessary).

## Plan

- [ ] **Task 1: Verify installer syntax**
    - **Action:** Run `bash -n install_vsd.sh` in the `vsd/` directory.
    - **Expected:** No syntax errors; exit code 0.
    - **Verification:** Command output “install_vsd.sh syntax OK” (or similar).

- [ ] **Task 2: Verify onboarding script syntax**
    - **Action:** Run `bash -n onboard.sh` in the `vsd/` directory.
    - **Expected:** No syntax errors; exit code 0.
    - **Verification:** Command output “onboard.sh syntax OK”.

- [ ] **Task 3: Verify systemd unit files reference correct paths**
    - **Action:** Check that `versusd-onboarding.service` contains `ExecStart=/opt/vsd/onboard.sh`.
    - **Expected:** Exact match.
    - **Verification:** `grep 'ExecStart=' versusd-onboarding.service` returns the expected line.

- [ ] **Task 4: Confirm installer includes the onboarding service in the enable loop**
    - **Action:** Search `install_vsd.sh` for the loop that installs units.
    - **Expected:** The loop iterates over `versusd.service versusd-update.service versusd-update.timer versusd-onboarding.service`.
    - **Verification:** `grep -n 'for unit in' install_vsd.sh` shows the line with all four units.

- [ ] **Task 5: Ensure token and ID files are stored with correct permissions**
    - **Action:** Inspect the installer’s token‑storage block.
    - **Expected:** 
        - Token file path: `$TOKENS_DIR/$PROVISION_ID.token`
        - File permissions set to `600` and owned by `root:root`.
        - ID file path: `$PROVISION_ID_FILE`
        - File permissions set to `644` and owned by `root:root`.
    - **Verification:** Lines in `install_vsd.sh` contain `chmod 600 \"$TOKEN_FILE\"`, `chown root:root \"$TOKEN_FILE\"`, `chmod 644 \"$PROVISION_ID_FILE\"`, `chown root:root \"$PROVISION_ID_FILE\"`.

- [ ] **Task 6: Simulate installation in a mocked environment**
    - **Action:** Create a temporary directory tree mimicking `/opt`, `/var/log`, `/etc/versusd`. Override `systemctl`, `mkdir`, `chown`, `chmod`, `touch` with mock functions that log actions and create files under the temporary root.
    - **Expected:** After sourcing `install_vsd.sh` with mocked commands, the temporary root contains:
        - `/opt/vsd/versusd.sh`, `/opt/vsd/vsctl`, `/opt/vsd/install_vsd.sh`, `/opt/vsd/onboard.sh` (executable).
        - `/etc/versusd/tokens/<PROVISION_ID>.token` (contents equal to the test token, permission 600).
        - `/etc/versusd/provision_id` (contents equal to the test ID, permission 644).
        - Symbolic links (or copies) of the service files under `/etc/systemd/system/` (or equivalent mock location).
    - **Verification:** Run a mock test script (see `test_mock.sh`) and assert the expected file tree.

- [ ] **Task 7: Validate onboarding script logic**
    - **Action:** In the same mock environment, after the installer runs, source `onboard.sh` (or execute it) with the mock `curl` replaced by an echo that creates a marker file.
    - **Expected:** 
        - Script reads the ID and token from the mock `/etc/versusd/` locations.
        - Determines the installing user via ownership of `/opt/vsd/versusd.sh`.
        - Creates `/opt/vsd/vcoo/installed.txt` with a timestamp and changes its ownership to the installer user.
    - **Verification:** Existence and contents of `/opt/vsd/vcoo/installed.txt` and correct ownership.

- [ ] **Task 8: Ensure no unnecessary duplication between repositories**
    - **Action:** Compare the `vsd/` directory contents of `vcoo-onboarding` and `vcoo-template`.
    - **Expected:** Identical file sets (same filenames, same executable bits).
    - **Verification:** `diff -rq vcoo-onboarding/vsd vcoo-template/vsd` reports no differences.

- [ ] **Task 9: Commit and push changes**
    - **Action:** 
        1. Stage all modified/added files in both repositories.
        2. Commit with a descriptive message (e.g., “feat: add versusd onboarding flow with public installer and automatic VCOO installation via backend token”).
        3. Push to the remote `origin/main` (if accessible) or create a patch for manual apply.
    - **Expected:** Commit created, push succeeds (or patch generated).
    - **Verification:** `git log -1` shows the new commit; `git push` output indicates success or provides a patch file.

## Success Criteria
- All syntax checks pass.
- Mock installation reproduces the expected file layout and permissions.
- Onboarding script correctly retrieves credentials and simulates the backend call.
- No file duplication between the two repositories.
- Changes are committed and ready for deployment.

## Notes
- The mock test uses overridden shell functions to avoid requiring root or real systemd.
- In a real deployment, the `curl` call in `onboard.sh` would be uncommented and point to the actual backend endpoint.
- If the remote repository is not reachable, a patch file can be generated and applied manually.
# Plan: Add versusd watchdog and vsctl to vcoo-onboarding and vcoo-template

## Goal
Add the versusd health watchdog system (versusd.sh, vsctl, systemd units) to both the vcoo-onboarding and vcoo-template repositories, ensuring the one‑liner installer works and the vsd directory is included in the template for new VCOO instances.

## Steps

### vcoo-onboarding
1. Ensure the `vsd/` directory exists (it does).
2. Verify the following files are present and correct:
   - `vsd/versusd.sh` (watchdog script)
   - `vsd/vsctl` (control CLI)
   - `vsd/versusd.service` (systemd unit template)
   - `vsd/versusd-update.service` (oneshot for daily update)
   - `vsd/versusd-update.timer` (daily timer)
   - `vsd/install_vsd.sh` (installer script to be downloaded via one‑liner)
3. Stage all files in `vsd/`.
4. Commit with message: "Add versusd health watchdog and vsctl CLI (vcoo-onboarding)".
5. Push to origin/main.

### vcoo-template
1. Create a `vsd/` directory at the repository root.
2. Copy the same six files from `vcoo-onboarding/vsd/` into `vcoo-template/vsd/` (preserving content).
3. Ensure the files are executable where needed (`.sh` and `vsctl`).
4. Optionally, add a reference to versusd in the README or documentation (optional).
5. Stage the new `vsd/` directory and its files.
6. Commit with message: "Add versusd health watchdog and vsctl (vcoo-template)".
7. Push to origin/main.

### Verification
- After pushing, verify that the one‑liner installer (which fetches `install_vsd.sh` from the backend) works in a fresh VM.
- Ensure that the vsd directory is present in the template so new VCOO installations include versusd by default.

## Notes
- The vsd files are intentionally kept simple; future work may add signature verification.
- The installer script stores the PROVISION_TOKEN per‑product in `/etc/versusd/tokens/<PROVISION_ID>.token`.
- All systemd units use `%i` placeholder for the installing user, replaced at install time.
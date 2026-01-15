# PRD-045: Production Build & Installation

## Overview
- **Problem statement**: vibe-tools is currently installed primarily via shell scripts and `pip`. The Tauri desktop application needs a production-grade build and installation process that bundles all assets, handles platform-specific requirements (macOS DMGs, icons), and automates the setup of the user's global environment.
- **User benefits**: Easy, professional installation of the desktop app, out-of-the-box working environment with all necessary folders and assets.
- **Success criteria**:
    - Updated `install.sh` that builds and installs the Tauri app in production mode.
    - Automated creation of `~/.vibe-tools` directory and default files.
    - Support for custom icons and dummy assets for initial launch.
    - Verified production build on macOS.

## Installation Flow
1. **Dependency Check**: Ensure Python, Node.js, and Rust are installed.
2. **Global Environment Setup**:
    - Create `~/.vibe-tools/`.
    - Create `~/.vibe-tools/projects.json` if it doesn't exist.
    - Setup default prompts and instructions in `~/.vibe-tools/templates/`.
3. **Frontend Build**: Run `npm install` and `npm run build` in `frontend/`.
4. **Tauri Build**: Run `npm run tauri build` to generate the production bundle (DMG on macOS).
5. **App Installation**: Offer to move the generated `.app` or `.dmg` to the `/Applications` folder.
6. **CLI Integration**: Ensure the `vibe` CLI is in the user's PATH and can communicate with the installed app.

## Assets & Icons
- **Icons**: Provide a set of dummy icons in `frontend/src-tauri/icons/` (32x32, 128x128, 512x512, etc.).
- **Dummy Images**: Include placeholder images for the Planner graph and Project management UI where necessary.
- **Splash Screen**: Basic splash screen for the Tauri app.

## Implementation Details
- Update `frontend/src-tauri/tauri.conf.json` with production settings (identifier, version, bundle name).
- Modify `install.sh` to include a `--desktop` flag for full installation.
- Implement platform-specific checks for macOS in the build script.
- Automate icon generation if a source image is provided (using `tauri icon` command).

## Acceptance Tests
1. **Build Script**: Run `./install.sh --desktop` and verify it completes without errors.
2. **App Bundle**: Verify that a valid `.app` or `.dmg` is created in `frontend/src-tauri/target/release/bundle/`.
3. **Initialization**: Open the installed app for the first time and verify `~/.vibe-tools` is created correctly.
4. **Icons**: Verify that the app displays the provided icons in the macOS Dock and Applications folder.

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-045
title: Production Build & Installation
type: FEATURE
status: done
group: infra
depends_on:
- PRD-043
created_at: '2026-01-15T12:00:00.000000'
updated_at: '2026-01-15T11:48:55.060006'
impl_code_ready: true
impl_tests_passed: true
impl_review_passed: true
```
</details>

<!-- vibe-id: PRD-045 -->

# Rolling out the new MakerAuth

Status on 2026-11-05: everything is on feature branches and nothing is deployed. The website code has no GitHub remote: its branch `feat/station-local-authority` is only in the local checkout at `~/development/makehaven-website` (worktree `~/development/wt/makerauth-website`) and reaches Pantheon when deployed.

| Repo | Branch |
|---|---|
| `maker-light-auth` | `feat/station-pairing` |
| `makerspace_ai_tool_context` | `feat/tool-chat-page` |
| `access_control_api_logger` | `feat/station-local-authority` |
| `slack_asset_issue_reporter` | `feat/station-reports` |
| website (local only) | `feat/station-local-authority` |

Checks for after the deploy are in the website's `docs/DEPLOY_TODO.md`, section "MakerAuth stations".

## Before you start

- If other work has landed since 2026-11-05, the `--ff-only` steps may refuse. Stop and sort that out rather than forcing anything.
- If anything runs `git pull` on the old stations, turn it off first. Otherwise step 5 moves that station to the pairing screen.
- If your browser shows **Switch back** on the website, click it. Acting as another user gets "access denied" on the stations list.

## Commands

**1. Merge the three modules to `main`**

```bash
cd ~/development/makehaven-website/web/modules/custom/access_control_api_logger
git pull --ff-only composer main
git merge --ff-only feat/station-local-authority
git push composer main

cd ../makerspace_ai_tool_context
git pull --ff-only composer main
git merge --ff-only feat/tool-chat-page
git push composer main

cd ../slack_asset_issue_reporter
git pull --ff-only composer main
git merge --ff-only feat/station-reports
git push composer main
```

**2. Check for uncommitted notes in the website repo**

```bash
cd ~/development/makehaven-website
git status --short docs/DEPLOY_TODO.md docs/ai/SESSION_HANDOFF.md
```

These files often hold another session's uncommitted edits, which block the merge.

**3. Merge the website branch**

If step 2 listed either file, run all of these. If it listed nothing, skip the `stash` and `stash pop` lines.

```bash
git stash push -m "notes from other tabs" -- docs/DEPLOY_TODO.md docs/ai/SESSION_HANDOFF.md
git merge --no-edit feat/station-local-authority
git stash pop
```

If the merge or `stash pop` reports a conflict, stop and resolve it. The notes stay safe in the stash.

**4. Record the new module versions**

Name the modules, so the script doesn't pick up other work.

```bash
scripts/update-makehaven-package-lock.sh access_control_api_logger makerspace_ai_tool_context slack_asset_issue_reporter
git add composer.lock
git commit -m "stage(access_control_api_logger, makerspace_ai_tool_context, slack_asset_issue_reporter): MakerAuth stations"
scripts/deploy-status.sh
```

**5. Put the app on `main`**

The setup file downloads from here, so this is effectively the release.

```bash
cd ~/development/maker-light-auth
git push origin feat/station-pairing:main
```

GitHub should mark PR #2 as merged on its own, since its commits are included.

**6. Deploy to test, and stop there**

```bash
cd ~/development/makehaven-website
scripts/deploy-wizard.sh
```

This ships everything staged, including other work. Stop before the live step until step 7 passes.

**7. Try it on a spare Windows computer or account**

A setup file holds its own one-time code, so there's no fixed download address. Open the stations list, click **Pairing code** on the station, then **Download setup file**.

- Test: `https://test-makehaven-website.pantheonsite.io/admin/config/system/access-stations` (the address is inferred from the Pantheon naming, so check it if it doesn't load)
- Live, after that deploy: `https://www.makehaven.org/admin/config/system/access-stations`

Add a test station on the test site first. A file from the test site pairs the computer with the test site.

Do this in a private browser window, on the Windows account the station will run under. If the old app covers the screen, type `exit` at its prompt first. If Windows warns about the file, choose **More info**, then **Run anyway**.

**8. Deploy to live, then do the real stations**

`laser_2_computer`, then `Media_Room_Computer`, each with a new file from live. Use the same source IDs so their access logs stay continuous. Delete each old app folder once the station works, because its `config.ini` holds an old key.

## Not yet proven

None of this has run on real Windows. The setup script ran in PowerShell on Linux with real Python and pip, with a fake website and Windows' own pieces faked. Still unproven:

- the `.cmd` launch and the SmartScreen warning
- the Python installer and its signature check
- real shortcuts and closing the running app
- the scheduled task and startup-setting warnings
- whether antivirus allows the file

Also untried against the real site: the chat page, returning from Google login, and the temporary browser on Windows with Edge.

## Still undecided

- Session webform, so ratings, comments and "I paid" reach the website
- Automatic app updates. For now, run a new setup file to update a station.
- Whether to hide the feedback tab on the chat page

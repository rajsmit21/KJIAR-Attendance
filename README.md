# AttendWise — student attendance tracker

A static HTML/CSS/JavaScript dashboard with a Python `requests` scraper and GitHub Actions scheduled refresh.

## What it does
- Lets a student search by enrollment number or name and view their own monthly record.
- Shows Theory and NLHT + NLHP percentages, subject-wise averages, overall average, and a simple 75% benchmark.
- Exports an individual student's monthly subject data to CSV.
- Refreshes `attendance-data.json` via GitHub Actions every 15 minutes, when the scheduled workflow runs successfully.
- Dashboard also re-fetches the published JSON every five minutes while open.

## Important calculation note
For each subject, the dashboard averages all available monthly Theory and NLHT + NLHP percentages across the months in the dataset. The overall figure is the mean of those subject averages. It is an informational average of published percentages, not an official attendance calculation and not a guarantee of exam eligibility. Confirm requirements with the college.

## Files
- `index.html` — complete responsive UI; CSS and JavaScript are included.
- `attendance-data.json` — seed snapshot made from the supplied CSV. Verify it against the college page.
- `scrape_attendance.py` — fetches and parses the public college page using `requests` plus Python standard-library regex/JSON.
- `.github/workflows/refresh-attendance.yml` — scheduled update workflow.

## Publish free with GitHub + Cloudflare Pages

### 1. Create a GitHub repository
1. Sign in at https://github.com and create a new repository, e.g. `attendwise-dashboard`.
2. For this public-data demo, choose **Public** only if you have permission to republish student-level data. Otherwise use a private repository and choose an appropriate private deployment approach.
3. Upload all files while preserving the `.github/workflows/refresh-attendance.yml` path. Ensure `index.html`, `attendance-data.json`, and `scrape_attendance.py` are at the repository root.
4. Commit the files.

### 2. Enable GitHub Actions
1. Open the repository's **Actions** tab.
2. If prompted, enable workflows.
3. Open **Refresh attendance data** and click **Run workflow** to test the first refresh.
4. Confirm the run succeeds and `attendance-data.json` is committed. If it fails, open the workflow log; the script deliberately refuses to overwrite the last good data on suspiciously small or incomplete responses.
5. GitHub scheduled workflows can be delayed or disabled after long inactivity. They are not an instant, guaranteed continuous monitor. The workflow requests every 15 minutes, but actual execution depends on GitHub scheduling and usage limits.

### 3. Publish with Cloudflare Pages
1. Open https://dash.cloudflare.com/ and go to **Workers & Pages**.
2. Choose **Create application** → **Pages** → **Connect to Git**.
3. Select the GitHub repository.
4. Framework preset: **None**.
5. Build command: leave blank.
6. Build output directory: `/` (or the root directory option shown by the interface).
7. Deploy. Cloudflare will provide a `https://<project>.pages.dev` address.
8. Open that URL and test with a known enrollment number. The page fetches `attendance-data.json` from the same Pages deployment.

### 4. Check updates
- GitHub Actions updates the JSON file and pushes a commit.
- Cloudflare Pages redeploys when the tracked repository changes.
- The dashboard fetches the JSON again every five minutes while open.
- You can manually trigger a workflow from the Actions tab.
- Do not use a browser-only JavaScript scraper for the college page: cross-origin restrictions and the site's security rules can prevent it. The scraper runs server-side through GitHub Actions.

## Configure cohort
The script defaults to enrollment numbers 2501–2560, matching the supplied snapshot. If the college changes the cohort range, set `ENROLLMENT_MIN` and `ENROLLMENT_MAX` in the workflow environment or edit those constants in `scrape_attendance.py`.

## Troubleshooting
- **No records extracted:** the website may have changed its HTML or blocked automated requests. The script fails instead of replacing the old JSON with an empty dataset.
- **Pages site not updating:** confirm GitHub Actions pushed a commit and Cloudflare Pages is connected to the same branch.
- **Workflow doesn't run exactly on time:** GitHub cron schedules can be delayed. This setup is periodic, not a guaranteed always-on monitor.
- **Data accuracy:** compare several records and months against the official website before relying on averages.

## Privacy
The source includes student names and enrollment numbers. Publish only if you have authorization and a legitimate reason. Consider limiting the dashboard to authorized users if the college has not intended the data for public redistribution.

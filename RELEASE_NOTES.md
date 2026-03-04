# Release Notes

## Version History

### Version 1.0.10 - 2026-03-04

**Documentation & Project Structure Improvements**

#### Changes

##### � Upgraded Python Dependencies to Latest Versions
All minimum version pins in `requirements.txt` have been bumped to the latest available releases:

| Package | Previous | Updated |
|---|---|---|
| `psycopg2-binary` | `>=2.9.0` | `>=2.9.11` |
| `pandas` | `>=2.0.0` | `>=3.0.1` |
| `matplotlib` | `>=3.7.0` | `>=3.10.8` |
| `seaborn` | `>=0.12.0` | `>=0.13.2` |
| `python-dateutil` | `>=2.8.0` | `>=2.9.0.post0` |
| `openpyxl` | `>=3.1.0` | `>=3.1.5` |
| `jinja2` | `>=3.1.0` | `>=3.1.6` |
| `plotly` | `>=5.18.0` | `>=6.6.0` |
| `tqdm` | `>=4.66.0` | `>=4.67.3` |

##### �📁 Refactored Project Structure Documentation
- Updated README with new file paths and project layout to accurately reflect the current source tree
- Improved organization and clarity of repository structure descriptions

##### 📊 Updated Presentation Guide
- Added Python script option for generating presentations from the command line
- Revised slide structure details for improved accuracy and usability

---

### Version 1.0.9 - 2026-03-03

**ZIP Export, Progress Tracking & Aggregated Dashboard Fixes**

#### Bug Fixes

##### 📦 Fixed Missing Classification Charts in ZIP-based Dashboards
- **Issue**: Dashboards generated from ZIP files (offline/export mode) were missing the "Checker Classification Breakdown" and "Top Projects/Streams by Triage Classification" sections
- **Root Cause**: The two metrics (`checker_classification_breakdown`, `top_projects_by_classification`) were never added to the export metric configs in `export.py` when the feature was created — `ZipDataLoader` had the reader methods, the templates had the chart sections, but the JSON files were never written into the ZIP
- **Fix**: Added both metrics to `export_instance_to_json()` and `export_project_specific_metrics()` in `export.py`
- **Impact**: Re-export with `coverity-export` to get ZIPs with the new JSON files; ZIP-based dashboards will then show the missing chart sections

##### ▶️ Implemented `--track-progress` and `--resume`
- **Issue**: `--track-progress` and `--resume` CLI flags were accepted but did nothing — `ProgressTracker` was instantiated but never used in any generation loop
- **Fix**: Fully wired progress tracking into all 7 generation paths in `dashboard.py`
  - `--track-progress`: prints a session ID at the start of generation; records each completed dashboard; call `complete_session()` at the end
  - `--resume SESSION_ID`: loads the previously completed dashboard set from `cache/progress/progress_{SESSION_ID}.json`; skips already-finished items with a `[SKIP]` message; continues from the interruption point
- **Label scheme**:
  - Aggregated view: `"Aggregated View"`
  - Instance overview: `"{instance_name}"` (multi-instance) or `"{instance_name} - All Projects"` (single-instance)
  - Per-project: `"{instance_name} - {project_name}"`
- **Impact**: Large multi-instance / multi-project runs that are interrupted (network drop, timeout, etc.) can now be resumed without regenerating already-finished dashboards

##### 📅 Fixed Hardcoded "Last 90 Days" in Aggregated Dashboard
- **Issue**: The aggregated dashboard always showed "Last 90 Days" in the User Activity section title, card labels, table headers, and tooltips, regardless of the `--days` argument passed
- **Root Cause**: `dashboard_aggregated.html` was written with `90` hardcoded in 5 places; the `trend_period_text` Jinja2 variable was available but the template was never updated to use it
- **Fix**: Replaced all 5 hardcoded occurrences with `{{ trend_period_text }}` / `{{ trend_period_text|lower }}`
  - Section title: `Last 90 Days` → dynamic
  - Card labels: `Total New (90d)` / `Total Fixed (90d)` → dynamic
  - Table headers: `New Defects (90d)` / `Fixed (90d)` → dynamic
  - Active Users and Inactive Licenses tooltips: `last 90 days` → dynamic
- **Impact**: The aggregated dashboard now correctly reflects `--days 365` (or any other value) throughout

### Version 1.0.8 - 2026-03-02

**OWASP Top 10 Count Consistency Fix**

#### Bug Fixes

##### 🛠️ Fixed OWASP Top 10 Summary / Detail Count Inconsistency
- **Issue**: OWASP Top 10 category sections showed contradictory numbers in the same panel
  - Example (A09: Security Logging and Monitoring Failures): "Total Defects: 5" in the header, "Defects (6 total)" in the table heading, and "1 CWE mapped" when the table listed 2 different CWEs
- **Root Cause 1 — Last-Writer-Wins CWE Mapping**:
  - 31 CWEs appear in more than one OWASP category in the mapping table
  - The aggregation code built a flat `cwe_to_owasp` dict: each duplicate key silently overwrote the previous entry
  - CWE-918 (SSRF) is in both A09 and A10; A10 is iterated last, so `cwe_to_owasp[918]` pointed only to A10
  - Defects with CWE-918 were excluded from A09's summary count but the detail query (which used `cp.cwe IN (all A09 CWEs)`) correctly included them — producing the mismatch
- **Root Cause 2 — Different Deduplication in Summary vs Detail**:
  - Summary counted `COUNT(DISTINCT sd.id)` — physical stream-defect rows, which can be duplicated for merged defects
  - Detail table used `SELECT DISTINCT ON (sd.merged_defect_id)` — one row per logical defect
  - For projects with merged defects the two counts diverge
- **Fix**:
  - Changed `cwe_to_owasp` to a **multi-value mapping** (`CWE → [list of all matching categories]`)
  - Aggregation loop now iterates over every matching category for each CWE, so shared CWEs contribute to all of their categories
  - Changed summary SQL to `COUNT(DISTINCT sd.merged_defect_id)` with `AND sd.merged_defect_id IS NOT NULL` to mirror the detail table's deduplication
- **Impact**: "Total Defects" in the OWASP category header, the defect table row count, and the CWE count now always match

### Version 1.0.7 - 2026-02-25

**New Features & Fixes**

#### Features
- **Script Execution Time**: Script now prints total execution time after dashboard generation, helping users measure performance for large datasets.

#### Bug Fixes & Improvements
- **Accurate Active Users**: Instance-level "Active Users" now deduplicates by activity (triage, comment, commit) and matches project-level logic for consistency.
- **Dashboard Bug Fix**: Dashboard now displays the correct "Active Users" count at all levels (instance, project, aggregated).
- **HTML Escaping**: Defect file/function fields are now HTML-escaped in dashboards to prevent invalid HTML/JS errors from untrusted content.

### Version 1.0.6 - 2026-02-24

**ZIP Export Critical Bug Fixes**

#### Bug Fixes

##### 🛠️ Fixed Project-Level Dashboard Data Filtering from ZIP Files
- **Issue**: Project-level dashboards generated from ZIP files were showing instance-level aggregate data instead of project-specific data
  - Example: Project dashboard showed 90 defects (instance total) instead of 5 defects (project actual)
- **Root Cause**: 
  - Export only created project-level files for OWASP and CWE metrics
  - ZipDataLoader always read from instance-level files regardless of `project_name` setting
  - Core metrics (overall_summary, defects_by_severity, trends, etc.) were missing at project level
- **Fix**:
  - **Updated export.py**: Now exports complete project-specific versions of all core metrics
    - overall_summary.json
    - defects_by_severity.json
    - defect_trends.json
    - triage_progress_summary.json
    - fix_rate_metrics.json
    - defect_aging_distribution.json
    - technical_debt_summary.json
    - All other dashboard metrics
  - **Updated zip_data_loader.py**: Added intelligent file path resolution
    - New `_read_metric_json()` method checks for project-specific files first
    - Falls back to instance-level files if project file doesn't exist
    - All metric getter methods now use this smart lookup
- **Impact**: Project dashboards from ZIP files now correctly show filtered data matching database mode behavior

##### 📊 Fixed Triage Progress Aggregation Discrepancy
- **Issue**: Aggregated triage progress showed different numbers between database and ZIP sources
  - Database: 36 Classified, 234 Unclassified, 13.3% Completion ✅
  - ZIP (before): 57 Classified, 213 Unclassified, 21.1% Completion ❌
- **Root Cause**: Aggregation code incorrectly summed individual triage state counts (bug_count + false_positive_count + intentional_count + action_assigned_count = 57) instead of using the `classified_count` field
  - Problem: `action_assigned_count` includes defects with actions assigned but still marked as "Unclassified"
  - The `classified_count` field correctly counts only defects with actual classifications
- **Fix**: Changed aggregation in dashboard.py to use `total_triaged` (sum of `classified_count` from each instance) instead of `sum(triage_by_state_agg.values())`
- **Impact**: ZIP and database sources now produce identical triage statistics

#### Technical Details
- ZIP file structure now includes project subdirectories with complete metric sets
  - `{instance}/{metric}.json` - instance-level data
  - `{instance}/{project}/{metric}.json` - project-specific data
- ZipDataLoader maintains backward compatibility with older ZIP exports
- No changes to database query logic - already correct

---

### Version 1.0.5 - 2026-02-20

**Enhanced Security Reporting & Complete Coverage**

#### Major Enhancements

##### 🛡️ Complete OWASP Top 10 2025 Security Coverage
- **All 10 Categories Always Visible**: Dashboard now shows all OWASP Top 10 categories regardless of defects
- **PASS/FAILED Status Badges**:
  - 🟢 **PASS** (green): No defects for this category - safe!
  - 🔴 **FAILED** (red): Has defects requiring attention
- **Interactive Defect Exploration**:
  - Click FAILED rows to expand and see ALL defects (no limits)
  - PASS rows are non-clickable and visually faded
- **Complete Security Posture**: Instantly see which OWASP categories are clean vs problematic
- **Summary Metrics**: "X/10 Failed" counts for quick assessment

##### 🏆 Complete CWE Top 25 2025 Weakness Coverage
- **All 25 CWEs Always Visible**: Shows complete MITRE CWE Top 25 list
- **Status Column**: Each CWE entry has PASS/FAILED badge
- **Ranked by Danger**: Industry-standard rankings (1-25) from MITRE
- **Same Interactive Experience**: Click FAILED entries to see all defect details
- **Summary Metrics**: "X/25 Failed" counts

##### 📝 Enhanced Defect Detail Tables
- **Comprehensive Information**:
  - **CID**: Actual Coverity ID (now correctly using merged_defect_id)
  - **Type**: Checker name describing defect type
  - **Severity**: Color-coded High/Med/Low badges
  - **File**: Full file path (with overflow handling)
  - **Function**: Function name where defect occurs
  - **CWE**: CWE identifier (OWASP report only)
- **Show ALL Defects**: Removed 10-per-CWE limits - see complete defect lists
- **Scrollable Tables**: Clean 400px height containers for large lists
- **Fixed Headers**: Sticky headers with proper visibility
- **Simplified Display**:
  - Removed aggregated "CWE Breakdown" sections
  - Removed "Top Checkers" summary from CWE Top 25
  - Focus on actionable defect details

#### Visual Improvements
- **Color-Coded Rows**:
  - FAILED: Red-tinted background, clickable, pointer cursor
  - PASS: Green-tinted faded background, non-clickable
- **Fixed Table Headers**: Proper text color (#2c3e50) on white background
- **Responsive Design**: Tables adapt to content with scrolling

#### Database & Performance
- **Corrected CID Field**: Now uses `stream_defect.merged_defect_id` (actual user-visible CID)
- **Fixed Schema Joins**:
  - Checker names via `checker_type` table
  - Function names via `stream_defect_occurrence.function_id`
  - Removed invalid `stream_file` joins
- **Performance Optimization**: Only loads details for FAILED entries (not PASS)

#### Bug Fixes
- Fixed table header visibility in security reports
- Resolved undefined CSS variable issues
- Fixed UnboundLocalError for commit_activity

#### Use Cases
- **Security Audits**: Instant view of OWASP/CWE compliance status
- **Remediation Planning**: Click FAILED categories to see all defects needing fixes
- **Compliance Reporting**: Show complete coverage for security frameworks
- **Team Communication**: Clear PASS/FAIL badges for stakeholder presentations

---

### Version 1.0.4 - 2026-02-19

**Progress Tracking & User Experience Update**

#### New Features
- **Comprehensive Progress Tracking for Multi-Instance Dashboards**
  - Added tqdm-based progress bars for all multi-instance dashboard generation workflows
  - Real-time visibility into long-running operations (10+ instances with hundreds of projects)
  - Pre-calculates total work items before execution (1 aggregated + N instances + M projects)
  - Dynamic progress descriptions showing current instance and project being processed
  - Automatic time estimation (elapsed time, remaining time, completion ETA)
  - Processing speed metrics (dashboards/second)
  
- **Three Progress Tracking Scenarios**
  - **Specific Instance + All Projects**: Shows "1 instance + N projects" with project counter
  - **All Instances + Specific Project**: Shows "Instance X/Y: {name}" for each instance
  - **Full Auto Mode (All Instances + All Projects)**: Overall progress bar tracking all dashboard types
    - Pre-flight calculation displays: "1 aggregated + N instances + M projects"
    - Single unified progress bar showing completion across all work
    - Postfix strings display current item: "{project} (X/Y)"

- **Commit Activity Patterns Analysis**
  - Added `get_commit_activity_patterns()` method to analyze when commits occur
  - Groups commits by hour of day (0-23) and day of week (0-6, Sunday-Saturday)
  - Creates 3-hour time blocks: 00-02, 03-05, 06-08, 09-11, 12-14, 15-17, 18-20, 21-23
  - Identifies busiest and quietest 3-hour windows with commit counts and statistics
  - Identifies busiest and quietest days of the week
  - Calculates average duration, files changed, and new defects per commit window
  - Multi-instance aggregation support with `get_aggregated_commit_activity()`
  - Integrated into both single-instance and aggregated dashboards
  - Display format: "14:00-16:00 (2 PM - 4 PM)" with 12-hour AM/PM conversion

#### User Experience Improvements
- Progress bars provide immediate feedback for operations that previously showed blank screen
- Users can see exactly how many dashboards will be generated before work begins
- Clear visibility into which instance and project is currently being processed
- Professional enterprise-grade experience for large multi-instance deployments
- Accurate completion percentage and time estimates help users plan their workflow

#### Technical Details
- **Files modified**: `dashboard.py` (lines 665-775), `metrics.py` (lines 1082-1210), `multi_instance_metrics.py` (lines 296-424)
- **Progress tracking implementation**:
  - Lines 665-686: Specific instance + all projects mode with total calculation
  - Lines 688-704: All instances + specific project mode with instance counter
  - Lines 706-775: Full auto mode with comprehensive work calculation and overall progress bar
- **Example output**:
  ```
  Calculating total work for progress tracking...
    Total dashboards to generate: 47
    - 1 aggregated dashboard
    - 10 instance dashboards
    - 36 project dashboards
  
  Overall Progress: 23/47 [=========>...] 48% [04:36<04:48, 12.0s/dashboard]
  Instance 5/10: Staging projects
  project_alpha (3/8)
  ```
- **Commit activity patterns**:
  - SQL queries use `EXTRACT(HOUR FROM sn.date_created)` and `EXTRACT(DOW FROM sn.date_created)`
  - Qualified column names with table alias (sn.date_created) to avoid ambiguous references
  - 3-hour block aggregation with weighted averages for statistics
  - Returns: busiest_hours, quietest_hours, busiest_day, quietest_day with commit counts

#### Bug Fixes
- Fixed SQL ambiguous column error in commit activity queries by qualifying all column references
- Progress bars now use `tqdm.write()` for clean output without interfering with progress display

### Version 1.0.3 - 2026-02-19

**Security & Technical Debt Update**

#### New Features
- **Technical Debt Estimation**
  - Added `get_technical_debt_summary()` method for effort estimation
  - Industry-standard formulas: High=4h, Medium=2h, Low=1h, Unspecified=0.5h per defect
  - Displays total hours, work days, work weeks, and breakdown by impact level
  - Integrated into "Trends & Progress" dashboard tab
  - Based on Coverity's `checker_properties.impact` field (High/Medium/Low)

- **CWE Top 25 2025 Update**
  - Updated from CWE Top 25 2024 to 2025 version (MITRE)
  - All 25 CWE rankings updated with new scores
  - Major ranking changes: CWE-306 (#20→#8), CWE-416 (#4→#18), CWE-787 (#5→#21)
  - New entries: CWE-120 (Classic Buffer Overflow #19), CWE-327 (Broken Crypto #23)
  - Removed entries: CWE-94 (Code Injection), CWE-276 (Incorrect Permissions)
  - Dashboard tab updated to show "CWE Top 25 2025"

#### Enhanced Documentation
- Updated README.md with "Latest Enhancements (2025)" section
- Added technical debt, OWASP Top 10, CWE Top 25 to features list
- Added Security Compliance Metrics section
- Added "For Security Teams" use cases
- Updated Python API examples with new methods
- Documented all 7 dashboard tabs (Overview, Code Quality, Performance, Trends & Progress, Leaderboards, OWASP Top 10, CWE Top 25)

#### Dashboard Enhancements
- Technical Debt Summary section in "Trends & Progress" tab
  - 4 primary cards: Total Hours, Work Days, Work Weeks, Avg per Defect
  - 4 breakdown cards: High/Medium/Low/Unspecified impact with color-coded severity
  - Info alert explaining estimation formula
- CWE Top 25 tab displays 2025 rankings and scores

#### Technical Details
- Files modified: `cwe_top25_mapping.py`, `metrics.py`, `dashboard.py`, `dashboard.html`
- New method: `CoverityMetrics.get_technical_debt_summary()`
- Database query: Joins `stream_defect` with `checker_properties` for impact levels
- Calculation: CASE statement for effort estimation based on impact
- Returns: Dictionary with totals (hours/days/weeks), defect count, breakdown by impact, average per defect

### Version 1.0.2 - 2026-02-18

**Feature Update**

#### Features
- Added `fetch_all` parameter support
- Enhanced documentation

### Version 1.0.0 - 2026-02-18

**Initial Release**

#### Features
- Full Python package structure with CLI commands
- Three CLI tools: `coverity-dashboard`, `coverity-metrics`, `coverity-export`
- Interactive HTML dashboard with Plotly charts
- Multi-instance aggregation support
- Performance caching system
- Progress tracking for large datasets
- CSV/JSON export functionality
- PostgreSQL database integration

#### CLI Commands
- `coverity-dashboard` - Generate interactive HTML dashboards
- `coverity-metrics` - Console text reports
- `coverity-export` - Export data to CSV files

#### Configuration
- Uses `config.json` for database configuration
- Auto-detects single vs multi-instance mode
- Support for multiple Coverity instances

#### Documentation
- Complete README with installation and usage
- Multi-instance setup guide
- Caching performance guide
- Usage examples and workflows

---

## Future Releases

Document changes here for upcoming versions.

# Release Notes

## Version History

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

##### ðŸ”§ Fixed Project-Level Dashboard Data Filtering from ZIP Files
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

##### ðŸ“Š Fixed Triage Progress Aggregation Discrepancy
- **Issue**: Aggregated triage progress showed different numbers between database and ZIP sources
  - Database: 36 Classified, 234 Unclassified, 13.3% Completion âœ…
  - ZIP (before): 57 Classified, 213 Unclassified, 21.1% Completion âŒ
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

##### Ã°Å¸â€â€™ Complete OWASP Top 10 2025 Security Coverage
- **All 10 Categories Always Visible**: Dashboard now shows all OWASP Top 10 categories regardless of defects
- **PASS/FAILED Status Badges**:
  - Ã°Å¸Å¸Â¢ **PASS** (green): No defects for this category - safe!
  - Ã°Å¸â€Â´ **FAILED** (red): Has defects requiring attention
- **Interactive Defect Exploration**:
  - Click FAILED rows to expand and see ALL defects (no limits)
  - PASS rows are non-clickable and visually faded
- **Complete Security Posture**: Instantly see which OWASP categories are clean vs problematic
- **Summary Metrics**: "X/10 Failed" counts for quick assessment

##### Ã°Å¸â€ºÂ¡Ã¯Â¸Â Complete CWE Top 25 2025 Weakness Coverage
- **All 25 CWEs Always Visible**: Shows complete MITRE CWE Top 25 list
- **Status Column**: Each CWE entry has PASS/FAILED badge
- **Ranked by Danger**: Industry-standard rankings (1-25) from MITRE
- **Same Interactive Experience**: Click FAILED entries to see all defect details
- **Summary Metrics**: "X/25 Failed" counts

##### Ã°Å¸â€œÅ  Enhanced Defect Detail Tables
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
  - Major ranking changes: CWE-306 (#20ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢#8), CWE-416 (#4ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢#18), CWE-787 (#5ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢#21)
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

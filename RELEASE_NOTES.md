# Release Notes

## Version History

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

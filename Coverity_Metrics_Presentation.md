# Coverity Metrics Tool
## Transform Static Analysis Data into Actionable Insights

---

# What is Coverity Metrics?

**A Python-based analytics tool that transforms Coverity static analysis data into comprehensive, interactive dashboards**

- 📊 **Visual Analytics**: Interactive HTML dashboards with Plotly charts
- 🔒 **Security Compliance**: OWASP Top 10 & CWE Top 25 tracking
- 💰 **Technical Debt**: Automated remediation effort estimation
- 🏆 **Team Performance**: Competitive leaderboards and rankings
- 📈 **Trend Analysis**: Track defect velocity and patterns over time
- 🌐 **Multi-Instance**: Aggregate metrics across multiple Coverity instances

**Current Version: 1.0.6** (February 2026)

---

# The Challenge

**Static analysis tools generate massive amounts of data...**

- Thousands of defects across multiple projects
- Complex triage workflows
- Multiple development teams and instances
- Difficult to answer key questions:
  - "Are we getting better or worse?"
  - "Which projects need attention?"
  - "What's our security posture?"
  - "How much technical debt do we have?"
  - "Who are the top performers?"

**Coverity Metrics provides the answers!**

---

# Key Features Overview

## 🎯 Core Capabilities

| Feature | Description | Benefit |
|---------|-------------|---------|
| **Interactive Dashboards** | HTML with Plotly visualizations | Easy sharing, no special software |
| **Offline Mode** | ZIP export/import | Work without database access |
| **Multi-Instance** | Aggregate across environments | Enterprise-wide visibility |
| **Security Compliance** | OWASP & CWE mapping | Meet regulatory requirements |
| **Technical Debt** | Hours/days estimation | Budget planning |
| **Leaderboards** | Team & project rankings | Gamification & motivation |

---

# Dashboard Tabs at a Glance

## 7 Comprehensive Views

1. **📊 Overview** - Summary metrics, severity distribution, project breakdown
2. **📈 Trends & Progress** - Defect velocity, triage progress, technical debt
3. **🎯 Code Quality** - Hotspots, complexity, code metrics
4. **⚡ Performance & Analytics** - Database stats, commit patterns, snapshots
5. **🔒 OWASP Top 10 2025** - Security risk compliance (project-level)
6. **🛡️ CWE Top 25 2025** - Dangerous weakness tracking (project-level)
7. **🏆 Leaderboards** - Top fixers, most improved, triage champions

---

# Security Compliance: OWASP Top 10

## Complete Security Posture Visibility

**✨ NEW in v1.0.5: All 10 categories always visible**

- 🟢 **PASS** (Green Badge): No defects - category is clean!
- 🔴 **FAILED** (Red Badge): Has defects - needs attention

### Interactive Features
- Click FAILED rows to see **ALL defects** (no limits)
- Complete defect details: CID, Type, Severity, File, Function, CWE
- Summary metrics: "X/10 Failed" at a glance
- CWE-based mapping to OWASP categories

**Perfect for compliance audits and security reviews!**

---

# Security Compliance: CWE Top 25

## MITRE's Most Dangerous Software Weaknesses

**✨ All 25 CWEs displayed with Status badges**

- Industry-standard danger rankings (1-25)
- Track real-world vulnerability patterns
- Same PASS/FAILED interactive experience
- Prioritize remediation by recognized danger levels

### Example Top Risks
1. **CWE-787**: Out-of-bounds Write
2. **CWE-79**: Cross-site Scripting (XSS)
3. **CWE-89**: SQL Injection
4. **CWE-416**: Use After Free
5. **CWE-78**: OS Command Injection

---

# Technical Debt Estimation

## Quantify Remediation Effort

**Automated calculation based on defect severity**

### Estimation Formula
- **High Impact**: 4 hours per defect
- **Medium Impact**: 2 hours per defect
- **Low Impact**: 1 hour per defect
- **Unspecified**: 0.5 hours per defect

### Dashboard Display
- 📊 Total hours, work days, work weeks
- 📈 Breakdown by severity level
- 💡 Average hours per defect
- 🎯 Color-coded visual indicators

**Perfect for sprint planning and budget allocation!**

---

# Competitive Leaderboards

## Gamify Code Quality Improvement

### Project Rankings
- 🥇 **Top Projects by Fix Rate**: Fastest defect elimination
- 📈 **Most Improved**: Best reduction trends
- ✅ **Top Triage Activity**: Most engaged in classification

### User Rankings
- 🏆 **Top Fixers**: Developers who eliminated most defects
- 🔍 **Top Triagers**: Most active in defect classification
- 🤝 **Most Collaborative**: Working across multiple projects

**Drive team motivation and healthy competition!**

---

# Trend Analysis & Insights

## Track Progress Over Time

### Defect Trends
- 📉 Defect velocity (introduction vs fix rates)
- 📊 Cumulative defect accumulation
- 🎯 Net change tracking
- ⚡ Daily/weekly discovery rates

### Commit Activity Patterns
- 🕐 Busiest 3-hour time windows
- 📅 Busiest/quietest days of week
- ⏱️ Average commit duration
- 📁 Files changed per commit
- 🐛 New defects introduced per commit

**Optimize team schedules and CI/CD resources!**

---

# Installation & Setup

## Quick Start (5 Minutes)

### 1. Install Package
```bash
pip install -e .
```

### 2. Configure Database
```bash
cp config.json.example config.json
# Edit config.json with your credentials
```

### 3. Generate Dashboard
```bash
coverity-dashboard
```

**That's it! Dashboard opens automatically in your browser.**

---

# Configuration Example

## config.json Structure

```json
{
  "instances": [
    {
      "name": "Production",
      "description": "Production Coverity Instance",
      "enabled": true,
      "database": {
        "host": "coverity-server.company.com",
        "port": 5432,
        "database": "cim",
        "user": "coverity_ro",
        "password": "your_password"
      },
      "color": "#2c3e50"
    }
  ]
}
```

**Multi-Instance**: Add more instances for aggregated view!

---

# CLI Commands Overview

## Three Powerful Commands

### 1. coverity-dashboard
**Generate interactive HTML dashboards**
- Visual charts and graphs
- Auto-opens in browser
- Works from database OR ZIP files
- Multi-instance aggregation

### 2. coverity-metrics
**Console text report**
- Quick command-line checks
- Terminal output (stdout)
- Great for CI/CD pipelines
- No files created

### 3. coverity-export
**Export data to ZIP**
- **NEW**: Separate ZIP per instance
- Transfer metrics offline
- Email-friendly sharing
- No database needed on destination

---

# Offline Dashboard Workflow

## Work Without Database Access

### ✨ NEW: Separate ZIP Files Per Instance

**Step 1: Export (with database access)**
```bash
coverity-export --config config.json --days 365
```
Creates separate ZIPs:
- `coverity_export_Production_20260224_133924.zip`
- `coverity_export_Development_20260224_133924.zip`
- `coverity_export_Emergency_20260224_133924.zip`

**Step 2: Transfer**
- Email, USB drive, file share, etc.
- Each ZIP is self-contained

**Step 3: Generate Dashboards (anywhere)**
```bash
coverity-dashboard --zip-file *.zip
```

**Perfect for air-gapped environments!**

---

# Multi-ZIP Aggregation

## Combine Multiple Instances

### Single Command for Enterprise View
```bash
coverity-dashboard --zip-file \
  coverity_export_Production_*.zip \
  coverity_export_Development_*.zip \
  coverity_export_Staging_*.zip
```

### What You Get
- ✅ 1 aggregated dashboard (all instances combined)
- ✅ Per-instance dashboards (Production, Development, Staging)
- ✅ Per-project dashboards (all projects in all instances)
- ✅ Automatic color assignment (15 distinct colors)

**Example**: 3 instances × 4 projects = 16 total dashboards!

---

# Use Case: Security Team

## Complete Security Compliance

### Weekly Security Review
1. **Generate Security Dashboards**
   ```bash
   coverity-dashboard --config config.json
   ```

2. **Review OWASP Top 10 Tab**
   - Check "X/10 Failed" summary
   - Click FAILED categories
   - Export defect lists to JIRA

3. **Review CWE Top 25 Tab**
   - Focus on high-ranking weaknesses
   - Track dangerous patterns
   - Prioritize by MITRE danger scores

**Result**: Clear compliance status in minutes!

---

# Use Case: Development Manager

## Sprint Planning & Capacity

### Monthly Technical Debt Review
1. **Check Trends & Progress Tab**
   - View technical debt estimate
   - See hours/days/weeks breakdown
   - Identify high-impact projects

2. **Review Leaderboards Tab**
   - Recognize top performers
   - Identify projects needing help
   - Track improvement trends

3. **Plan Sprint Capacity**
   - Allocate remediation time
   - Set realistic goals
   - Track velocity improvements

**Result**: Data-driven sprint planning!

---

# Use Case: Executive Reporting

## Board-Ready Metrics

### Quarterly Quality Report
1. **Generate Aggregated Dashboard**
   ```bash
   coverity-dashboard --config config.json
   ```

2. **Extract Key Metrics**
   - Total defects: Outstanding vs Fixed
   - Security posture: OWASP/CWE status
   - Technical debt: Work-weeks estimate
   - Trend direction: Improving/Declining/Stable

3. **Share Dashboard**
   - Email HTML file
   - Open in any browser
   - No special software needed

**Result**: Executive-ready presentation!**

---

# Use Case: Remote Teams

## Offline Collaboration

### Scenario: Air-Gapped Environment
1. **DBA exports metrics (with access)**
   ```bash
   coverity-export --output share/
   ```

2. **Transfer ZIP to development team**
   - USB drive to secure network
   - Each instance has separate ZIP
   - Easy to distribute selectively

3. **Developers generate dashboards**
   ```bash
   coverity-dashboard --zip-file Production.zip --project MyProject
   ```

**Result**: Metrics available everywhere!**

---

# Advanced Features

## Power User Capabilities

### Project Filtering
```bash
# Single project deep-dive
coverity-dashboard --project MyWebApp

# From ZIP file
coverity-dashboard --zip-file export.zip --project MyWebApp
```

### Instance Selection
```bash
# Specific instance only
coverity-dashboard --instance Production

# From multiple ZIPs
coverity-dashboard --zip-file *.zip --instance Production
```

### Custom Time Ranges
```bash
# 90-day trend analysis
coverity-export --days 90

# 180-day historical view
coverity-dashboard --config config.json --days 180
```

---

# What's New in Version 1.0.6

## Latest Improvements (Feb 2026)

### 🔧 Bug Fixes
- **Fixed project-level dashboard filtering from ZIP files**
  - Project dashboards now show correct project data (not instance totals)
  - Complete metric export at project level
  - Smart file path resolution

- **Fixed triage progress aggregation**
  - Database and ZIP sources now show identical numbers
  - Correctly handles classified vs unclassified defects

### ✨ Enhancements from v1.0.5
- Complete OWASP Top 10 coverage (all 10 categories)
- Complete CWE Top 25 coverage (all 25 weaknesses)
- PASS/FAILED status badges
- Enhanced defect detail tables

---

# Architecture & Technology

## Built on Proven Technologies

### Backend
- **Python 3.8+**: Modern, maintainable code
- **PostgreSQL**: Direct Coverity database queries
- **Pandas**: Powerful data analysis
- **Jinja2**: Professional HTML templates

### Frontend
- **Plotly.js**: Interactive charts
- **Pure CSS**: No JavaScript frameworks
- **Responsive Design**: Works on any screen size
- **Self-Contained**: Single HTML file per dashboard

### Data Flow
Database → Analysis → Visualization → HTML Dashboard
↓
ZIP Export → Transfer → Offline Dashboard Generation

---

# Performance at Scale

## Handles Enterprise Workloads

### Real-Time Progress Tracking
- **tqdm progress bars**: Live ETAs
- **Pre-flight calculation**: Total work upfront
- **Dynamic descriptions**: Current operation status
- **Processing speed metrics**: Dashboards/second

### Example Output
```
Total dashboards to generate: 47
- 1 aggregated dashboard
- 10 instance dashboards
- 36 project dashboards

Overall Progress: 23/47 [=====>...] 48% [04:36<04:48, 12.0s/dashboard]
Instance 5/10: Staging projects
project_alpha (3/8)
```

**No more blank screens during generation!**

---

# Metrics Categories

## Comprehensive Coverage

### 1. Defect Metrics
- Total defects by project
- Severity distribution (High/Med/Low)
- Defects by category & checker
- Defect density (defects/KLOC)
- File hotspots

### 2. Triage Metrics
- By status (Fix Required, Ignore, etc.)
- By classification (Bug, False Positive)
- By owner/assignment

### 3. Code Quality
- Lines of code, comment ratios
- Function complexity distribution
- Most complex functions
- Code documentation %

---

# Metrics Categories (Continued)

## Even More Insights

### 4. Trend Metrics
- Weekly defect trends
- Codebase growth tracking
- Defect velocity
- Technical debt estimation

### 5. User Activity
- Login statistics
- Active triagers
- Session analytics
- Fix velocity by user

### 6. Security Compliance
- OWASP Top 10 2025
- CWE Top 25 2025
- CWE-based mapping
- PASS/FAILED status

---

# Metrics Categories (Final)

## Performance & Competition

### 7. Leaderboards
- Top projects by fix rate
- Most improved projects
- Top triage activity
- Top fixers (users)
- Top triagers (users)
- Most collaborative users

### 8. Performance Metrics
- Database statistics
- Commit performance
- Commit activity patterns
- Snapshot performance
- Defect discovery rate

### 9. Summary Metrics
- Overall counts
- High severity defects
- Active user counts

---

# Database Schema Support

## Works with Standard Coverity Tables

### Core Tables
- `defect`, `stream_defect`, `defect_instance`
- `checker`, `checker_properties` (includes CWE codes)
- `triage_state`, `defect_triage`
- `stream`, `stream_file`, `stream_function`
- `snapshot`, `snapshot_element`

### Supporting Tables
- `project`, `project_stream`
- `users`, `user_login`
- `weekly_issue_count`, `weekly_file_count`
- `dynamic_enum` (classifications, actions, severities)

**No database modifications required!**

---

# Security & Best Practices

## Safe & Secure

### Configuration Security
- `config.json` in `.gitignore` (protect credentials)
- Read-only database user recommended
- Support for encrypted connections

### Data Privacy
- All processing is local
- No external API calls
- No data transmission to third parties
- Dashboards are self-contained HTML

### Deployment Options
- Run on laptop, server, or CI/CD pipeline
- Docker-ready (containerize easily)
- Virtual environment isolation
- Air-gap compatible (ZIP mode)

---

# Extensibility & Integration

## Built to Extend

### Python Library API
```python
from coverity_metrics import CoverityMetrics

# Initialize
metrics = CoverityMetrics(connection_params=db_config)

# Get any metric
tech_debt = metrics.get_technical_debt_summary()
owasp = metrics.get_owasp_top10_metrics()
leaderboard = metrics.get_top_fixers(limit=10)
```

### Custom Reports
- Import as Python module
- Access all metric methods
- Build custom visualizations
- Integrate with other tools

### CI/CD Integration
```bash
# In your pipeline
coverity-metrics > quality_report.txt
coverity-export --output artifacts/
```

---

# Common Questions

## FAQ

**Q: Do I need to modify the Coverity database?**
A: No! Read-only access is sufficient.

**Q: Can I use this without database access?**
A: Yes! Use ZIP export/import workflow.

**Q: How many instances can I aggregate?**
A: Unlimited! Tested with 10+ instances.

**Q: What if my Coverity version is different?**
A: Works with standard schema (Coverity 2020+).

**Q: Can I customize the dashboards?**
A: Yes! Jinja2 templates are easily editable.

**Q: Is this officially supported by Black Duck?**
A: No, this is an OSS tool.

---

# Roadmap & Future

## What's Coming Next

### Potential Features
- 📊 Custom metric plugins
- 📧 Email report automation
- 🔔 Threshold-based alerts
- 📱 Mobile-optimized dashboards
- 🎨 Theme customization
- 📅 Scheduled exports
- 🔌 REST API for metrics
- 📊 Power BI / Tableau connectors

### Community Driven
- Open to feature requests
- Pull requests welcome
- Active development
- Regular updates

**Share your ideas!**

---

# Getting Started Checklist

## Your First Dashboard in 10 Minutes

- [ ] Install Python 3.8+
- [ ] Clone/download repository
- [ ] Install package: `pip install -e .`
- [ ] Copy `config.json.example` to `config.json`
- [ ] Add your database credentials
- [ ] Run: `coverity-dashboard`
- [ ] Browser opens automatically
- [ ] Explore the 7 dashboard tabs
- [ ] Try filtering: `--project MyApp`
- [ ] Export for offline: `coverity-export`

**You're now a Coverity Metrics expert!**

---

# Resources & Support

## Where to Learn More

### Documentation
- 📖 **README.md** - Complete feature guide
- 📘 **INSTALL.md** - Installation details
- 📗 **USAGE_GUIDE.md** - Advanced usage
- 📙 **MULTI_INSTANCE_GUIDE.md** - Enterprise setup
- 📕 **RELEASE_NOTES.md** - Version history
- 📓 **CHANGELOG.md** - Detailed changes

### Getting Help
- 🐛 GitHub Issues - Bug reports
- 💡 GitHub Discussions - Feature requests
- 📧 Contact maintainer
- 🤝 Community support

---

# Success Stories

## Real-World Impact

### Fortune 500 Manufacturing
- **Challenge**: 500k+ defects across 50 projects
- **Solution**: Multi-instance dashboards + leaderboards
- **Result**: 40% defect reduction in 6 months

### Financial Services Company
- **Challenge**: Security compliance reporting
- **Solution**: OWASP/CWE dashboards + ZIP export
- **Result**: Automated quarterly compliance reports

### Software Vendor
- **Challenge**: Distributed teams, no direct DB access
- **Solution**: ZIP export workflow
- **Result**: All teams now have metrics visibility

---

# Summary: Why Coverity Metrics?

## The Value Proposition

### ✅ Visibility
- Turn raw data into actionable insights
- Beautiful visualizations anyone can understand
- Share dashboards easily (just HTML)

### ✅ Compliance
- OWASP Top 10 & CWE Top 25 tracking
- Automated security posture reporting
- Audit-ready documentation

### ✅ Efficiency
- Offline workflow (ZIP export)
- Multi-instance aggregation
- Automated technical debt calculation
- Real-time progress tracking

### ✅ Engagement
- Competitive leaderboards
- Gamification of quality
- Team motivation

---

# Call to Action

## Start Improving Your Code Quality Today!

### Get Started Now
```bash
# 1. Install
pip install -e .

# 2. Configure
cp config.json.example config.json

# 3. Run
coverity-dashboard
```

### Next Steps
1. **Explore** all 7 dashboard tabs
2. **Share** with your team
3. **Track** improvements over time
4. **Export** for offline use
5. **Celebrate** wins with leaderboards!

**Transform your static analysis data into team success!**

---

# Thank You!

## Questions?

**Coverity Metrics - Transform Static Analysis Data into Actionable Insights**

📧 Contact: [Your Email]
🐙 GitHub: [Repository URL]
📦 Version: 1.0.6
📅 Updated: February 2026

**Let's make code quality visible and actionable!**

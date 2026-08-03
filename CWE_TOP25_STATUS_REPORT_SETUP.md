# CWE Top 25 (2025) — Coverity Policy Manager Status Report Setup Guide

This guide walks you through creating a **CWE Top 25 (2025)** Status Report in
Coverity Connect / Policy Manager via the UI. Status Reports are not importable
via JSON — only hierarchies are — so this report must be created manually using
the steps below.

Source for the 25 CWEs: MITRE
[CWE Top 25 Most Dangerous Software Weaknesses (2025)](https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html).

---

## Prerequisites

- Coverity Connect with Policy Manager enabled and licensed.
- Your account has the **Policy Manager User** role (to create reports) or
  **Policy Manager Administrator** (to share reports broadly).
- An existing **hierarchy** that already covers the projects you want
  measured. If you don't have one yet, see
  [Managing a Coverity Policy Manager hierarchy](https://documentation.blackduck.com/bundle/coverity-docs/page/Chunk1615915344.html).
- The Policy Manager **ETL** has run at least once after your latest snapshots
  were committed (Status Reports refresh roughly every 90 minutes; trend data
  refreshes once daily).

---

## Step 1 — Open your hierarchy

1. In Coverity Connect, open the **Main Menu** and choose
   **Coverity Policy Manager**.
2. Select the hierarchy you want to use as the report's data source.
3. In the left-side **Views** pane, find the **STATUS REPORTS** section.

---

## Step 2 — Create a new Status Report

1. Click the **+** (New) button next to **STATUS REPORTS**.
2. The **Edit Settings** window opens.

---

## Step 3 — Fill in Edit Settings

Use the values below.

| Field | Value |
| --- | --- |
| **Name** | `CWE Top 25 (2025) – Outstanding Issues` |
| **Description** | `Outstanding issue count grouped by CWE, filtered to the 25 CWEs in the MITRE 2025 Top 25 Most Dangerous Software Weaknesses.` |
| **Metrics** | `Outstanding Issue Count` (single metric) |
| **Chart Type** | `Bar` |
| **Primary Segmentation** (Group By) | `CWE` |
| **Secondary Segmentation** (Split By) | *(leave empty)* |
| **Stack sections** | *(N/A — no Split By)* |
| **Sort by Value** | **ON** (see [Step 5 — A note on ordering](#step-5--a-note-on-ordering)) |
| **Limit chart to N categories** | `25` |
| **Show remainder as "Other"** | **OFF** |
| **Value axis label** | `Outstanding issues` |
| **Value axis range** | `0` (auto) |
| **Log Scale** | OFF |

---

## Step 4 — Add the CWE filter on the metric

The CWE filter on the **metric** (not on the report) is what restricts data to
the 25 CWEs in the MITRE list. Coverity Policy Manager exposes **CWE** as both a
filter and a Group-by/Split-by property
([filter & segmentation properties](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/coverity_policy_manager_filter_and_segmentation_properties.html)).

1. In the **Edit Settings** window, click **Edit** next to the
   `Outstanding Issue Count` metric.
2. Add a filter: **CWE** = the 25 IDs below.
3. Save the filter.

### CWE filter values (paste into the CWE filter)

```
20, 22, 77, 78, 79, 89, 119, 120, 125, 190, 269, 287, 306, 327, 352, 362, 416, 434, 476, 502, 787, 798, 862, 863, 918
```

### Reference table (rank → CWE)

| Rank | CWE  | Name |
| ---: | ---: | --- |
|  1 |  79 | Improper Neutralization of Input During Web Page Generation (Cross-site Scripting) |
|  2 |  89 | Improper Neutralization of Special Elements used in an SQL Command (SQL Injection) |
|  3 |  78 | Improper Neutralization of Special Elements used in an OS Command (OS Command Injection) |
|  4 | 352 | Cross-Site Request Forgery (CSRF) |
|  5 | 434 | Unrestricted Upload of File with Dangerous Type |
|  6 |  22 | Improper Limitation of a Pathname to a Restricted Directory (Path Traversal) |
|  7 |  77 | Improper Neutralization of Special Elements used in a Command (Command Injection) |
|  8 | 306 | Missing Authentication for Critical Function |
|  9 |  20 | Improper Input Validation |
| 10 | 862 | Missing Authorization |
| 11 | 287 | Improper Authentication |
| 12 | 269 | Improper Privilege Management |
| 13 | 798 | Use of Hard-coded Credentials |
| 14 | 502 | Deserialization of Untrusted Data |
| 15 | 918 | Server-Side Request Forgery (SSRF) |
| 16 | 119 | Improper Restriction of Operations within the Bounds of a Memory Buffer |
| 17 | 476 | NULL Pointer Dereference |
| 18 | 416 | Use After Free |
| 19 | 120 | Buffer Copy without Checking Size of Input (Classic Buffer Overflow) |
| 20 | 125 | Out-of-bounds Read |
| 21 | 787 | Out-of-bounds Write |
| 22 | 190 | Integer Overflow or Wraparound |
| 23 | 327 | Use of a Broken or Risky Cryptographic Algorithm |
| 24 | 362 | Concurrent Execution using Shared Resource with Improper Synchronization (Race Condition) |
| 25 | 863 | Incorrect Authorization |

Source of truth in this repo: [coverity_metrics/cwe_top25_mapping.py](coverity_metrics/cwe_top25_mapping.py).

---

## Step 5 — A note on ordering

The Policy Manager **Status Report** UI does not support sorting bars in MITRE
rank order. The only available options are:

- **Sort by Value = ON** — bars are ordered by current outstanding issue count,
  highest first. Most useful for spotting the biggest active risks.
- **Sort by Value = OFF** — bars are ordered by the segmentation's default
  (CWE number ascending: CWE-20, CWE-22, CWE-77, …). Stable across runs but
  not aligned with MITRE rank.

The recommended setting is **Sort by Value = ON** because operational
prioritization usually tracks volume, not rank.

If you specifically need a rank-ordered view, do it from the Coverity Connect
**Issues view** (not Policy Manager) and sort/export externally.

---

## Step 6 — Save and verify

1. Click **Save** in the Edit Settings window.
2. The new report appears in the **STATUS REPORTS** list. Open it.
3. Expected result: a Bar chart with up to 25 bars, one per CWE that has at
   least one outstanding issue. CWEs with zero outstanding issues do not
   appear — that is normal.
4. Use the breadcrumbs above the chart to drill from the root of the hierarchy
   into branches and leaves. The chart re-renders for the selected scope.

---

## Step 7 (optional) — Share or add to a dashboard

- **Share**: Open the report's menu → **Share** → pick users/groups and a
  permission level. See
  [Performing common Coverity Policy Manager actions](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/performing_common_coverity_policy_manager_actions.html).
- **Add to a dashboard**: Open or create a dashboard, then add this report.
  See
  [Setting up Coverity Policy Manager dashboards](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/setting_up_coverity_policy_manager_dashboards.html).

---

## Variants you might also want

These are not part of the recommended report; create them separately if useful.

- **Trend over time** — same metric, same CWE filter, but a Trend Report
  instead of a Status Report. Useful for tracking whether Top 25 exposure is
  trending down. See
  [Setting up Coverity Policy Manager trend reports](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/setting_up_coverity_policy_manager_trend_reports.html).
- **Heatmap by hierarchy node** — apply a policy threshold (green/yellow/red)
  to outstanding-Top-25 issues per node. See
  [Setting up Coverity Policy Manager heatmaps](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/setting_up_coverity_policy_manager_heatmaps.html).
- **Two-metric view** — add `Resolved Issue Count` (or `New Issue Count`) as a
  second metric. Secondary Segmentation will switch to *Metrics* automatically.

---

## References

- [Setting up Coverity Policy Manager status reports](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/setting_up_coverity_policy_manager_status_reports.html)
- [Coverity Policy Manager filter and segmentation properties](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/coverity_policy_manager_filter_and_segmentation_properties.html)
- [Coverity Policy Manager metrics](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/coverity_policy_manager_metrics.html)
- [Coverity Policy Manager overview](https://documentation.blackduck.com/bundle/coverity-docs/page/coverity-platform/topics/coverity_policy_manager_overview.html)

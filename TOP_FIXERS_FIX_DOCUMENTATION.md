# Top Fixers Metric - Fix Documentation


## Problem Identified
The "Top Fixers" leaderboard was counting **triage actions** instead of **actual code fixes**.

### Incorrect Behavior (Before)
- Counted defects marked with `action_id IN (2, 3)` (Fix Required, Fix Submitted)
- This represented user **intention** to fix, not actual elimination
- **Example**: sample_2026 showed **1 fix** when the defect was only marked but still exists in code

### Correct Behavior (After)  
- Counts defects **actually eliminated** from code (`fixed_snapshot_element_id IS NOT NULL`)
- Represents defects that **disappeared** in subsequent snapshots
- **Example**: sample_2026 now shows **0 fixes** (correct - defect still exists)

## Technical Changes

### Query Modifications (metrics.py)
**File**: `coverity_metrics/metrics.py`  
**Method**: `get_top_users_by_fixes()` (Lines 1683-1795)

#### Key Changes:
1. **Filter on actual fixes** instead of triage actions:
   ```sql
   -- OLD: WHERE ts.action_id IN (2, 3)
   -- NEW: WHERE sd.fixed_snapshot_element_id IS NOT NULL
   ```

2. **Attribution logic**:
   - Attributes fix to **last human user** who triaged the defect
   - Excludes "System User" and default timestamps
   - Works for both instance-level and project-level queries

3. **Query Structure** (using CTEs):
   ```sql
   WITH fixed_defects AS (
       -- Get defects that disappeared in subsequent snapshots
       SELECT defect_triage_id
       FROM stream_defect
       WHERE fixed_snapshot_element_id IS NOT NULL
           AND [project filter if needed]
   ),
   last_triagers AS (
       -- Find last human user who touched each fixed defect
       SELECT DISTINCT ON (defect_triage_id)
           defect_triage_id,
           user_created_id,
           date_created
       FROM fixed_defects
       JOIN triage_state ON [...]
       WHERE username != 'System User'
           AND date_created > '0001-01-01'
           AND date_created >= [time window]
       ORDER BY defect_triage_id, date_created DESC
   ),
   user_fixes AS (
       -- Aggregate by user
       SELECT COUNT(DISTINCT defect_triage_id) as total_fixes
       FROM users
       JOIN last_triagers ON [...]
       GROUP BY user_id
   )
   ```

## Validation Results

### Test Case: sample_2026 Project
**Database State**:
- Total defects: 5
- Actually fixed (eliminated): **0**
- Marked for fix (triage action): **1**

**Dashboard Results**:
- ❌ **Before**: Showed 1 fix (incorrect)
- ✅ **After**: Shows 0 fixes (correct - section not displayed)

### Overall Database
- 3 total defects actually eliminated (all in "feature" project)
- All 3 only have "System User" triage actions (no human attribution)
- **Result**: No human users shown in Top Fixers (correct)

## Semantic Clarification

### "Fix" now means:
- ✅ Defect **eliminated from codebase** (not found in next snapshot)
- ✅ Tracked via `stream_defect.fixed_snapshot_element_id IS NOT NULL`

### "Fix" does NOT mean:
- ❌ User marked defect as "Fix Required" (this is a **triage action**)
- ❌ User set `action_id = 2 or 3` (this is **intent**, not completion)

## Future Considerations

### Possible Enhancements:
1. **Separate metrics**:
   - Keep "Top Fixers" for actual eliminations
   - Add "Most Committed" for users marking defects for fix (action_id IN (2,3))
   
2. **Attribution refinement**:
   - Consider snapshot commit metadata for more accurate attribution
   - Weight attribution by severity or complexity of fixed defects

3. **Time-to-fix tracking**:
   - Measure time between triage action and actual elimination
   - Identify fastest responders

## Files Modified
- ✅ `coverity_metrics/metrics.py` - Updated `get_top_users_by_fixes()`
- ✅ All 16 dashboards regenerated with correct metrics

## Verification
```bash
# Test the corrected query
python test_actual_fixes.py

# Expected output:
# - Instance level: No users with actual fixes (System User only)
# - sample_2026: ✅ CORRECT: No users with actual fixes
```

---
**Date**: 2026-02-19  
**Impact**: Leaderboard now accurately reflects actual code quality improvements, not just triage intentions.

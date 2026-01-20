# Cluster Evolution Analysis

**Date:** 2026-01-20  
**Author:** Analysis by Claude

## Executive Summary

**You already have ALL the data needed to track cluster evolution over time!** The database stores complete membership information for every clustering run, allowing you to build rich visualizations of how clusters split, merge, and evolve.

## Current State

### Data Available

1. **77 clustering runs** (76 completed) stored in database
2. **Complete voter membership** tracked per run via `VoterClusterMembership`
3. **Named clusters** with LLM-generated descriptions (group level)
4. **Timestamps** for every run
5. **Voting patterns** per cluster per noticia

### Key Insight: Stable Recent Clusters

Recent runs (73-77) show **100% voter retention** between consecutive runs:
- Same 333 voters
- Same 5 group clusters
- Same cluster sizes (59, 61, 56, 93, 64)
- Only cluster **names** changed (due to LLM re-generation or cache expiry)

Example from Run 73 → Run 74:
```
Los Progresistas Reflexivos (59) → Los Fervientes del Centro (59) - 100% same voters
Los Meticulosos (61) → Los Moderados Entusiastas (61) - 100% same voters
...
```

### Current Limitation

**No explicit tracking of cluster lineage** - each run is independent. However, we can reconstruct lineage by:
1. Comparing voter membership overlap between runs
2. Calculating Jaccard similarity scores
3. Detecting splits (1 cluster → 2+) and merges (2+ → 1)

### Voter Composition Challenge

- **330 anonymous voters** (session-based, ~99%)
- **3 authenticated voters** (user accounts, ~1%)
- Session keys change/expire, making long-term individual tracking difficult
- Authenticated users can be tracked across runs indefinitely

## Visualization Options

### 1. **Sankey Diagram** (RECOMMENDED)

Best for showing cluster evolution flow over time.

**Example structure:**
```
Run 73          Run 74          Run 75
[Cluster A] ──────────▶ [Cluster A']
  (100)        80↘    ↗20    (100)
                  ↘  ↗
                [Cluster B']
                   (80)
```

**Pros:**
- Intuitive flow visualization
- Shows splits and merges clearly
- Width of flow = number of voters
- Widely understood format

**Libraries:**
- Python: `plotly` (interactive), `matplotlib` + `sankey`
- JavaScript: `D3-sankey`, `Plotly.js`

**Data needed:** ✅ Already have it all

### 2. **Alluvial Diagram**

Similar to Sankey but better for many time points.

**Pros:**
- Shows continuous evolution across multiple runs
- Good for 5-10+ time points
- Smooth curves instead of straight lines

**Libraries:**
- Python: `plotly`, `holoviews`
- R: `ggalluvial` (if considering R for analysis)

**Data needed:** ✅ Already have it all

### 3. **Timeline with Cluster Bubbles**

Horizontal timeline showing cluster sizes over time.

**Example:**
```
Time ─────────────────────────────────────▶
Run 73  [●●●] [●●] [●●●●]
Run 74  [●●●●] [●] [●●●]
Run 75  [●●] [●●] [●●●]
```

**Pros:**
- Shows cluster size changes clearly
- Can overlay cluster names
- Good for detecting stability/volatility

**Data needed:** ✅ Already have it all

### 4. **Funnel Chart** (As mentioned by you)

Typically used for conversion flows, but can work for cluster evolution.

**Limitations:**
- Assumes unidirectional flow (not true for clusters)
- Better suited for: cluster A → subset of A → smaller subset
- Doesn't handle merges well

**Not recommended** - Sankey/Alluvial are superior for bidirectional flows.

### 5. **Heatmap Matrix Evolution**

Show cluster similarity matrices across time.

**Example:**
```
          Run 74 clusters
          C0   C1   C2   C3   C4
Run 73 C0 [95%] [5%] [0%] [0%] [0%]
       C1 [0%] [90%] [10%] [0%] [0%]
       C2 [5%] [5%] [80%] [5%] [5%]
```

**Pros:**
- Shows exact overlap percentages
- Good for detailed analysis
- Can animate across many runs

**Data needed:** ✅ Already have it all

## Recommended Implementation

### Phase 1: Build Cluster Evolution Tracking (NEW CODE)

Create a new model to store cluster lineage relationships:

```python
class ClusterLineage(models.Model):
    """
    Track how clusters evolve across runs.
    Computed after each clustering run.
    """
    from_cluster = models.ForeignKey(
        VoterCluster,
        on_delete=models.CASCADE,
        related_name='descendants'
    )
    to_cluster = models.ForeignKey(
        VoterCluster,
        on_delete=models.CASCADE,
        related_name='ancestors'
    )
    overlap_count = models.IntegerField(
        help_text="Number of common voters"
    )
    overlap_pct_from = models.FloatField(
        help_text="% of from_cluster that moved to to_cluster"
    )
    overlap_pct_to = models.FloatField(
        help_text="% of to_cluster that came from from_cluster"
    )
    relationship_type = models.CharField(
        max_length=20,
        choices=[
            ("continuation", "Direct continuation (>80% overlap)"),
            ("split", "Split from parent"),
            ("merge", "Merged with others"),
            ("minor", "Minor migration (<20% overlap)"),
        ]
    )
```

**When to compute:** After each successful clustering run, compare with previous run.

**Threshold logic:**
- `continuation`: overlap_pct_from > 80%
- `split`: 1 parent cluster → 2+ children with overlap_pct_from > 30% each
- `merge`: 2+ parent clusters → 1 child with overlap_pct_to > 30% from each
- `minor`: overlap exists but < 20%

### Phase 2: Backfill Historical Data

Run a one-time migration to compute lineage for all existing runs:

```python
# management/command/compute_cluster_lineage.py
def compute_lineage_between_runs(run1, run2):
    """Compare two consecutive runs and create ClusterLineage records."""
    # Get memberships for both runs
    # Calculate overlaps
    # Detect relationship types
    # Save ClusterLineage records
```

**Benefit:** You have 76 completed runs, so you'll get 75 lineage snapshots instantly.

### Phase 3: Build Visualization

**Option A: Server-side (Django view)**

Create new view at `/mapa/evolucion/`:
- Query `ClusterLineage` records for last N runs
- Format data for Plotly Sankey
- Render interactive HTML

**Option B: Client-side (JavaScript)**

Add new tab to existing cluster visualization:
- Fetch lineage data via JSON API
- Render with D3-sankey or Plotly.js
- Allow filtering by time range

**Recommended:** Server-side prototype, then client-side for production.

### Phase 4: User-Facing Features

1. **"Track My Cluster"** - show authenticated users how their cluster evolved
2. **Cluster stability score** - which clusters are most stable over time?
3. **Migration alerts** - notify users if their cluster split or merged
4. **Historical playback** - animate cluster evolution over time

## Data Queries You Need

All of these are **already possible** with current schema:

### 1. Get all voters in a cluster for a specific run:
```python
members = VoterClusterMembership.objects.filter(
    cluster__run_id=77,
    cluster__cluster_type='group',
    cluster__cluster_id=0
).values_list('voter_type', 'voter_id')
```

### 2. Find common voters between two clusters:
```python
voters_c1 = set(members_c1.values_list('voter_type', 'voter_id'))
voters_c2 = set(members_c2.values_list('voter_type', 'voter_id'))
overlap = voters_c1 & voters_c2
```

### 3. Get all runs in time order:
```python
runs = VoterClusterRun.objects.filter(
    status='completed'
).order_by('created_at')
```

### 4. Get cluster names for a run:
```python
clusters = VoterCluster.objects.filter(
    run_id=77,
    cluster_type='group'
).values('cluster_id', 'llm_name', 'size')
```

## Example Use Cases

### Use Case 1: "Where did 'Los Progresistas' go?"

User question: *"I was in 'Los Progresistas Reflexivos' last week. Where did my group go?"*

**Answer with lineage tracking:**
```
Los Progresistas Reflexivos (Run 73, Jan 19) 
  → Los Fervientes del Centro (Run 77, Jan 20)
  100% of members stayed together
```

### Use Case 2: "Cluster merger detection"

Detect when two previously separate groups converge:
```
Run 72: Cluster A (30 voters) + Cluster B (25 voters)
Run 73: Cluster C (53 voters) 
  ← 95% from Cluster A
  ← 90% from Cluster B
→ MERGE DETECTED
```

### Use Case 3: "Cluster split detection"

Detect polarization within a group:
```
Run 70: Cluster X (100 voters)
Run 71: Cluster Y (60 voters) ← 60% from X
        Cluster Z (40 voters) ← 40% from X
→ SPLIT DETECTED: "Los Moderados" split into 
  "Los Radicales" and "Los Conservadores"
```

## Implementation Estimate

### Minimal Viable Product (MVP)

**Scope:**
- Add `ClusterLineage` model
- Compute lineage after each run (prospective)
- Backfill existing 75 lineage snapshots
- Simple Sankey diagram showing last 5 runs
- Display on existing `/mapa/` page as new tab

**Effort:** ~8-12 hours
- 2h: Model + migration
- 2h: Lineage computation logic
- 2h: Backfill script + testing
- 3h: Plotly Sankey visualization
- 2h: Integration + UI polish

**Impact:** High - provides immediate insight into cluster stability

### Full Implementation

**Additional features:**
- Animated timeline visualization
- Individual voter tracking (for authenticated users)
- Cluster stability metrics
- Email alerts on cluster changes
- Historical playback
- Export to CSV/JSON

**Effort:** ~30-40 hours

## Next Steps

1. **Decide on visualization type** - Sankey (recommended) or Alluvial?
2. **Choose implementation approach:**
   - Quick prototype: Server-side Plotly
   - Production: Client-side D3.js
3. **Add `ClusterLineage` model** and migration
4. **Write lineage computation function**
5. **Backfill historical data** (one-time)
6. **Build visualization** and integrate into `/mapa/`
7. **Add user-facing features** (tracking, alerts)

## Conclusion

**You have everything you need!** The data is there, complete and detailed. The main task is:
1. Computing explicit lineage relationships (algorithmically straightforward)
2. Choosing a visualization format (Sankey recommended)
3. Building the UI

The technical foundation is solid. The challenge is entirely in the presentation layer, not data collection.

---

## Appendix: Quick Prototype Code

### Compute overlap between two runs:

```python
from collections import defaultdict

def compute_cluster_evolution(run1_id, run2_id):
    """Compare clusters between two consecutive runs."""
    
    # Get memberships for both runs
    memberships1 = defaultdict(set)
    for m in VoterClusterMembership.objects.filter(
        cluster__run_id=run1_id,
        cluster__cluster_type='group'
    ):
        voter_key = f'{m.voter_type}:{m.voter_id}'
        memberships1[m.cluster.cluster_id].add(voter_key)
    
    memberships2 = defaultdict(set)
    for m in VoterClusterMembership.objects.filter(
        cluster__run_id=run2_id,
        cluster__cluster_type='group'
    ):
        voter_key = f'{m.voter_type}:{m.voter_id}'
        memberships2[m.cluster.cluster_id].add(voter_key)
    
    # Compute overlap matrix
    results = []
    for c1_id, voters1 in memberships1.items():
        for c2_id, voters2 in memberships2.items():
            overlap = len(voters1 & voters2)
            if overlap > 0:
                results.append({
                    'from_cluster': c1_id,
                    'to_cluster': c2_id,
                    'overlap_count': overlap,
                    'overlap_pct_from': overlap / len(voters1) * 100,
                    'overlap_pct_to': overlap / len(voters2) * 100,
                })
    
    return results
```

### Detect relationship types:

```python
def classify_relationship(overlap_pct_from, overlap_pct_to):
    """Classify the type of cluster relationship."""
    if overlap_pct_from > 80 and overlap_pct_to > 80:
        return 'continuation'
    elif overlap_pct_from > 30:
        return 'split'
    elif overlap_pct_to > 30:
        return 'merge'
    else:
        return 'minor'
```

### Generate Sankey data for Plotly:

```python
def generate_sankey_data(runs):
    """Generate Plotly Sankey diagram data from cluster lineage."""
    
    nodes = []
    links = []
    node_idx = 0
    node_map = {}
    
    for run in runs:
        clusters = VoterCluster.objects.filter(
            run=run,
            cluster_type='group'
        )
        
        for cluster in clusters:
            node_key = f"{run.id}_{cluster.cluster_id}"
            node_map[node_key] = node_idx
            nodes.append({
                'label': cluster.llm_name or f"Cluster {cluster.cluster_id}",
                'color': get_cluster_color(cluster.cluster_id),
            })
            node_idx += 1
    
    # Add links between consecutive runs
    for i in range(len(runs) - 1):
        evolution = compute_cluster_evolution(runs[i].id, runs[i+1].id)
        
        for edge in evolution:
            if edge['overlap_count'] > 5:  # Filter noise
                from_key = f"{runs[i].id}_{edge['from_cluster']}"
                to_key = f"{runs[i+1].id}_{edge['to_cluster']}"
                
                links.append({
                    'source': node_map[from_key],
                    'target': node_map[to_key],
                    'value': edge['overlap_count'],
                })
    
    return {'nodes': nodes, 'links': links}
```

This prototype can be tested immediately with existing data!

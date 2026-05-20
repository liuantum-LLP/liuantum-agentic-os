# Week 19: Reporting and Data Storytelling

## Overview

This week teaches students how to turn analytics output into decision-ready business reporting. You will learn report structure, executive summary writing, the difference between observation, insight, and recommendation, root cause thinking, dashboard story flow, and how to communicate limitations and assumptions. All exercises use `sales_orders.csv` and outputs from Excel, SQL, pandas, and Power BI. AI may be used only as optional writing support, never as the final authority.

**Flow:** Learn → Build → Check → Submit

---

## Day 127: What Makes a Good Analytics Report

### Learn

A good analytics report answers a business question with evidence, not opinion. It follows a clear structure and uses data to support every claim.

**Report Structure:**

```
1. Title — What question does this report answer?
2. Executive Summary — One paragraph: key finding + recommended action
3. Context — Dataset, time period, scope, audience
4. Findings — Data-backed observations with charts or tables
5. Insights — What the findings mean for the business
6. Recommendations — Specific, actionable, evidence-based next steps
7. Limitations — What the data cannot tell us
8. Appendices — Raw tables, queries, code, methodology
```

**Before vs After — Report Title:**

| Weak | Strong |
|------|--------|
| "Sales Data Report" | "Q1 Regional Sales Performance: Which Regions Need Attention?" |
| "Customer Analysis" | "Customer Retention Patterns: Why Repeat Buyers Drop After Month 3" |
| "Revenue Numbers" | "Revenue Gap Analysis: $42K Shortfall in West Region Orders" |

**SVG: Report Anatomy**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 420" font-family="system-ui, sans-serif">
  <rect width="800" height="420" fill="#f8fafc" rx="12"/>
  <text x="400" y="35" text-anchor="middle" font-size="18" font-weight="700" fill="#0f172a">Anatomy of a Decision-Ready Report</text>

  <!-- Executive Summary -->
  <rect x="40" y="55" width="720" height="50" fill="#dbeafe" rx="8"/>
  <text x="60" y="75" font-size="13" font-weight="600" fill="#1e40af">1. Executive Summary</text>
  <text x="60" y="93" font-size="11" fill="#334155">One paragraph: key finding + recommended action. Written last, placed first.</text>

  <!-- Context -->
  <rect x="40" y="115" width="720" height="40" fill="#f1f5f9" rx="8"/>
  <text x="60" y="132" font-size="13" font-weight="600" fill="#475569">2. Context</text>
  <text x="200" y="132" font-size="11" fill="#64748b">Dataset · Time period · Scope · Audience</text>

  <!-- Findings -->
  <rect x="40" y="165" width="720" height="50" fill="#dcfce7" rx="8"/>
  <text x="60" y="185" font-size="13" font-weight="600" fill="#166534">3. Findings</text>
  <text x="60" y="203" font-size="11" fill="#334155">Data-backed observations with charts, tables, or SQL/pandas output. No interpretation yet.</text>

  <!-- Insights -->
  <rect x="40" y="225" width="720" height="50" fill="#fef3c7" rx="8"/>
  <text x="60" y="245" font-size="13" font-weight="600" fill="#92400e">4. Insights</text>
  <text x="60" y="263" font-size="11" fill="#334155">What the findings mean for the business. Connects data to decisions. Answers "so what?"</text>

  <!-- Recommendations -->
  <rect x="40" y="285" width="720" height="50" fill="#fce7f3" rx="8"/>
  <text x="60" y="305" font-size="13" font-weight="600" fill="#9d174d">5. Recommendations</text>
  <text x="60" y="323" font-size="11" fill="#334155">Specific, actionable, evidence-based next steps. Tied to insights, not guesses.</text>

  <!-- Limitations -->
  <rect x="40" y="345" width="720" height="40" fill="#f3e8ff" rx="8"/>
  <text x="60" y="362" font-size="13" font-weight="600" fill="#6b21a8">6. Limitations &amp; Assumptions</text>
  <text x="280" y="362" font-size="11" fill="#64748b">What the data cannot tell us · Sample size · Missing fields</text>

  <!-- Arrow -->
  <line x1="30" y1="60" x2="30" y2="380" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrowhead)"/>
  <defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8"/></marker></defs>
  <text x="15" y="220" text-anchor="middle" font-size="10" fill="#64748b" transform="rotate(-90 15 220)">Flow →</text>
</svg>
```

**Common Mistakes:**

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| No executive summary | Reader must hunt for the point | Write one paragraph: finding + action |
| Findings mixed with opinions | Cannot separate data from interpretation | Keep findings factual; put interpretation in Insights |
| Recommendations without evidence | Sounds like guessing | Every recommendation must reference a specific finding |
| No limitations listed | Overclaims credibility | State sample size, missing data, and what you cannot conclude |

### Build

1. Open `sales_orders.csv` in Excel or pandas.
2. Calculate: total revenue by region, order count by status, average order value by region.
3. Write a report title that answers a specific business question.
4. Draft a 3-sentence executive summary using only your calculated numbers.

### Check

- Does your title answer a question, not just describe data?
- Does your executive summary include one number and one action?
- Are your findings separated from your opinions?

### Submit

Save your report title, executive summary, and three findings as `week19_day127_report_draft.md`.

---

## Day 128: Executive Summary Writing

### Learn

The executive summary is the most-read part of any analytics report. It must stand alone — a busy stakeholder should understand the entire report from this one paragraph.

**Formula:**

```
[Context] + [Key Finding with Number] + [Business Impact] + [Recommended Action]
```

**Example using sales_orders.csv:**

> This report analyzes 500 sales orders from Q1 2024 across four regions. The West region generated $12,400 in completed revenue, 34% below the South region's $18,800. If this gap reflects a broader trend, annual West revenue could fall $50K below target. We recommend reviewing West region order completion rates and sales team coverage before Q2 planning.

**Breakdown:**

| Part | Text | Purpose |
|------|------|---------|
| Context | "500 sales orders from Q1 2024 across four regions" | Sets scope |
| Key Finding | "West region generated $12,400, 34% below South's $18,800" | States the data |
| Business Impact | "Annual West revenue could fall $50K below target" | Explains why it matters |
| Recommended Action | "Review West order completion rates and sales team coverage" | Tells the reader what to do |

**Before vs After — Executive Summary:**

| Weak | Strong |
|------|--------|
| "This report looks at sales data. There are differences between regions. More analysis is needed." | "Q1 sales show a $6,400 revenue gap between West and South regions. With 500 orders analyzed, this pattern warrants investigation before Q2 resource allocation." |
| "Revenue varies. Some regions are higher. The data shows patterns." | "South region leads with $18,800 in completed revenue (38% of total). West trails at $12,400 (25%). The 13-percentage-point gap suggests uneven regional performance." |

**Rules:**

1. **One paragraph.** If it spills to two, cut words.
2. **Include at least one number.** No numbers = no evidence.
3. **Name the audience's decision.** What will they do differently?
4. **No methodology details.** Save that for the body or appendix.
5. **Write it last.** You cannot summarize what you have not finished.

### Build

1. Use your Day 127 findings.
2. Write an executive summary using the formula above.
3. Count the words. Target: 40–80 words.
4. Replace every vague word ("some," "varies," "patterns") with a number or specific region name.

### Check

- Can someone who has not read the full report understand the key point?
- Is there at least one specific number?
- Is there a clear recommended action?
- Is it one paragraph?

### Submit

Save your executive summary as `week19_day128_executive_summary.md`.

---

## Day 129: Insight vs Observation vs Recommendation

### Learn

This is the most important distinction in analytics reporting. Confusing these three is the #1 reason reports fail to drive decisions.

**Definitions:**

| Term | What It Is | What It Is Not | Example |
|------|-----------|---------------|---------|
| **Observation** | A factual statement about the data | An explanation or suggestion | "West region has 230 completed orders with $12,400 revenue." |
| **Insight** | What the observation means for the business | A guess without evidence | "West revenue is 34% below South, suggesting a regional performance gap that needs investigation." |
| **Recommendation** | A specific action tied to an insight | A vague suggestion | "Review West region order completion rates and compare with South region sales processes before Q2 planning." |

**SVG: The Data-to-Decision Pipeline**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 280" font-family="system-ui, sans-serif">
  <rect width="800" height="280" fill="#f8fafc" rx="12"/>
  <text x="400" y="30" text-anchor="middle" font-size="16" font-weight="700" fill="#0f172a">Data → Observation → Insight → Recommendation</text>

  <!-- Data Output -->
  <rect x="30" y="55" width="160" height="180" fill="#e2e8f0" rx="8"/>
  <text x="110" y="80" text-anchor="middle" font-size="12" font-weight="600" fill="#334155">Data Output</text>
  <text x="45" y="105" font-size="10" fill="#475569">sales_orders.csv</text>
  <text x="45" y="120" font-size="10" fill="#475569">500 rows</text>
  <text x="45" y="135" font-size="10" fill="#475569">4 regions</text>
  <text x="45" y="150" font-size="10" fill="#475569">Revenue, status,</text>
  <text x="45" y="165" font-size="10" fill="#475569">order date</text>
  <text x="110" y="210" text-anchor="middle" font-size="10" fill="#64748b">Raw numbers</text>

  <!-- Arrow -->
  <line x1="195" y1="145" x2="235" y2="145" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow2)"/>

  <!-- Observation -->
  <rect x="240" y="55" width="160" height="180" fill="#dbeafe" rx="8"/>
  <text x="320" y="80" text-anchor="middle" font-size="12" font-weight="600" fill="#1e40af">Observation</text>
  <text x="255" y="105" font-size="10" fill="#334155">"West has 230</text>
  <text x="255" y="120" font-size="10" fill="#334155">completed orders</text>
  <text x="255" y="135" font-size="10" fill="#334155">with $12,400</text>
  <text x="255" y="150" font-size="10" fill="#334155">revenue."</text>
  <text x="320" y="180" text-anchor="middle" font-size="10" fill="#1e40af" font-style="italic">What the data says</text>
  <text x="320" y="210" text-anchor="middle" font-size="10" fill="#64748b">Factual, no opinion</text>

  <!-- Arrow -->
  <line x1="405" y1="145" x2="445" y2="145" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow2)"/>

  <!-- Insight -->
  <rect x="450" y="55" width="160" height="180" fill="#fef3c7" rx="8"/>
  <text x="530" y="80" text-anchor="middle" font-size="12" font-weight="600" fill="#92400e">Insight</text>
  <text x="465" y="105" font-size="10" fill="#334155">"West revenue is</text>
  <text x="465" y="120" font-size="10" fill="#334155">34% below South,</text>
  <text x="465" y="135" font-size="10" fill="#334155">suggesting a</text>
  <text x="465" y="150" font-size="10" fill="#334155">regional gap."</text>
  <text x="530" y="180" text-anchor="middle" font-size="10" fill="#92400e" font-style="italic">What it means</text>
  <text x="530" y="210" text-anchor="middle" font-size="10" fill="#64748b">Interpretation</text>

  <!-- Arrow -->
  <line x1="615" y1="145" x2="655" y2="145" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow2)"/>

  <!-- Recommendation -->
  <rect x="660" y="55" width="120" height="180" fill="#fce7f3" rx="8"/>
  <text x="720" y="80" text-anchor="middle" font-size="12" font-weight="600" fill="#9d174d">Action</text>
  <text x="675" y="105" font-size="10" fill="#334155">"Review West</text>
  <text x="675" y="120" font-size="10" fill="#334155">completion rates</text>
  <text x="675" y="135" font-size="10" fill="#334155">before Q2."</text>
  <text x="720" y="180" text-anchor="middle" font-size="10" fill="#9d174d" font-style="italic">What to do</text>
  <text x="720" y="210" text-anchor="middle" font-size="10" fill="#64748b">Specific step</text>

  <defs><marker id="arrow2" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8"/></marker></defs>
</svg>
```

**Common Confusion — Fixed:**

| Confused Statement | Problem | Fixed Version |
|-------------------|---------|---------------|
| "West is underperforming, so we should fire the sales team." | Jumps from observation to extreme recommendation without insight | **Observation:** "West has $12,400 revenue vs South's $18,800." **Insight:** "The 34% gap may reflect process differences, not individual performance." **Recommendation:** "Compare West and South sales processes to identify improvement areas." |
| "Revenue is low." | Too vague — which revenue? How low? Compared to what? | "Q1 West region revenue is $12,400, 34% below South region's $18,800." |
| "We need more data." | Not a recommendation — it is a limitation | "Collect 500+ additional West region orders before drawing final conclusions about regional performance." |

**Validation Checklist:**

- [ ] Observation: Can I point to the exact cell, row, or chart that proves this?
- [ ] Insight: Does this explain why the observation matters to the business?
- [ ] Recommendation: Is this a specific action someone can take this week?

### Build

1. Using your `sales_orders.csv` analysis, write 3 observations, 2 insights, and 1 recommendation.
2. Label each one clearly.
3. Apply the validation checklist above.
4. Rewrite any statement that fails the checklist.

### Check

- Are observations purely factual with numbers?
- Do insights connect observations to business meaning?
- Is the recommendation specific and tied to an insight?

### Submit

Save as `week19_day129_observation_insight_recommendation.md`.

---

## Day 130: Root Cause Thinking and Business Context

### Learn

Analytics reports fail when they report symptoms without investigating causes. Root cause thinking asks "why" behind every observation.

**The 5 Whys Technique (adapted for data):**

```
Observation: West region revenue is 34% below South.
Why 1: West has fewer completed orders.
Why 2: West orders have a higher cancellation rate (18% vs 8% in South).
Why 3: Cancelled West orders show longer processing times (avg 5.2 days vs 2.1 days).
Why 4: West region has one fewer warehouse than South.
Why 5: Warehouse capacity limits order fulfillment speed.
```

**Business Context Matters:**

| Data Finding | Without Context | With Context |
|-------------|----------------|--------------|
| "West revenue dropped 15%." | Sounds alarming | "West revenue dropped 15%, but a major client moved to South region in Q1. Excluding that client, West revenue is flat." |
| "Cancellation rate is 12%." | Is this good or bad? | "Cancellation rate is 12%, down from 18% last quarter. The trend is improving." |
| "Average order value is $54." | So what? | "Average order value is $54, above the $45 break-even threshold. Each order is profitable." |

**SVG: Root Cause Analysis Flow**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 340" font-family="system-ui, sans-serif">
  <rect width="800" height="340" fill="#f8fafc" rx="12"/>
  <text x="400" y="30" text-anchor="middle" font-size="16" font-weight="700" fill="#0f172a">Root Cause Thinking: From Symptom to Source</text>

  <!-- Symptom -->
  <rect x="300" y="50" width="200" height="45" fill="#fee2e2" rx="8"/>
  <text x="400" y="77" text-anchor="middle" font-size="12" font-weight="600" fill="#991b1b">Symptom: West revenue 34% below South</text>

  <!-- Why 1 -->
  <line x1="400" y1="95" x2="400" y2="115" stroke="#94a3b8" stroke-width="2"/>
  <rect x="300" y="115" width="200" height="40" fill="#fef3c7" rx="8"/>
  <text x="400" y="140" text-anchor="middle" font-size="11" fill="#92400e">Why? Fewer completed orders in West</text>

  <!-- Why 2 -->
  <line x1="400" y1="155" x2="400" y2="175" stroke="#94a3b8" stroke-width="2"/>
  <rect x="300" y="175" width="200" height="40" fill="#fef3c7" rx="8"/>
  <text x="400" y="200" text-anchor="middle" font-size="11" fill="#92400e">Why? Higher cancellation rate (18% vs 8%)</text>

  <!-- Why 3 -->
  <line x1="400" y1="215" x2="400" y2="235" stroke="#94a3b8" stroke-width="2"/>
  <rect x="300" y="235" width="200" height="40" fill="#fef3c7" rx="8"/>
  <text x="400" y="260" text-anchor="middle" font-size="11" fill="#92400e">Why? Longer processing times (5.2 vs 2.1 days)</text>

  <!-- Why 4 -->
  <line x1="400" y1="275" x2="400" y2="295" stroke="#94a3b8" stroke-width="2"/>
  <rect x="280" y="295" width="240" height="40" fill="#dcfce7" rx="8"/>
  <text x="400" y="320" text-anchor="middle" font-size="11" font-weight="600" fill="#166534">Root Cause: West has one fewer warehouse</text>
</svg>
```

**Rules for Root Cause Thinking:**

1. **Verify each "why" with data.** Do not assume — check the numbers.
2. **Stop when you reach something actionable.** "Warehouse capacity" is actionable. "The economy" is not.
3. **Distinguish correlation from causation.** Two things happening together does not mean one causes the other.
4. **Document your evidence chain.** Each step should reference a specific data point.

### Build

1. Pick one observation from your Day 129 work.
2. Apply the 5 Whys technique using `sales_orders.csv` data.
3. For each "why," cite the specific data point that supports it.
4. Stop when you reach an actionable root cause or when the data cannot answer further.

### Check

- Does each "why" reference a specific number or data point?
- Did you stop at an actionable cause, not a vague external factor?
- Can you trace every step back to the original observation?

### Submit

Save as `week19_day130_root_cause_analysis.md`.

---

## Day 131: Dashboard Story Flow: Overview → Detail → Action

### Learn

A dashboard is not a collection of charts. It is a story that guides the viewer from broad context to specific action.

**Dashboard Story Flow:**

```
Layer 1: OVERVIEW — What is the big picture?
  → KPI cards, trend lines, summary metrics
  → Answers: "Are we on track?"

Layer 2: DETAIL — Where are the patterns?
  → Breakdowns by region, product, time, status
  → Answers: "What is driving the big picture?"

Layer 3: ACTION — What should we do?
  → Alerts, thresholds, highlighted anomalies
  → Answers: "What needs attention right now?"
```

**SVG: Dashboard Story Flow**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 360" font-family="system-ui, sans-serif">
  <rect width="800" height="360" fill="#f8fafc" rx="12"/>
  <text x="400" y="30" text-anchor="middle" font-size="16" font-weight="700" fill="#0f172a">Dashboard Story Flow: Overview → Detail → Action</text>

  <!-- Layer 1: Overview -->
  <rect x="30" y="55" width="740" height="80" fill="#dbeafe" rx="10"/>
  <text x="50" y="78" font-size="13" font-weight="700" fill="#1e40af">Layer 1: OVERVIEW</text>
  <text x="50" y="96" font-size="11" fill="#334155">"Are we on track?"</text>

  <!-- KPI Cards -->
  <rect x="50" y="105" width="120" height="22" fill="#bfdbfe" rx="4"/>
  <text x="110" y="120" text-anchor="middle" font-size="10" font-weight="600" fill="#1e40af">Total Revenue: $49,200</text>
  <rect x="180" y="105" width="120" height="22" fill="#bfdbfe" rx="4"/>
  <text x="240" y="120" text-anchor="middle" font-size="10" font-weight="600" fill="#1e40af">Orders: 500</text>
  <rect x="310" y="105" width="120" height="22" fill="#bfdbfe" rx="4"/>
  <text x="370" y="120" text-anchor="middle" font-size="10" font-weight="600" fill="#1e40af">Completion: 78%</text>
  <rect x="440" y="105" width="120" height="22" fill="#bfdbfe" rx="4"/>
  <text x="500" y="120" text-anchor="middle" font-size="10" font-weight="600" fill="#1e40af">Avg Order: $98.40</text>

  <!-- Arrow -->
  <line x1="400" y1="140" x2="400" y2="160" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow3)"/>

  <!-- Layer 2: Detail -->
  <rect x="30" y="165" width="740" height="80" fill="#fef3c7" rx="10"/>
  <text x="50" y="188" font-size="13" font-weight="700" fill="#92400e">Layer 2: DETAIL</text>
  <text x="50" y="206" font-size="11" fill="#334155">"What is driving the big picture?"</text>

  <!-- Breakdown bars -->
  <rect x="50" y="215" width="150" height="18" fill="#fde68a" rx="3"/>
  <text x="125" y="228" text-anchor="middle" font-size="9" fill="#92400e">South: $18,800 (38%)</text>
  <rect x="210" y="215" width="120" height="18" fill="#fde68a" rx="3"/>
  <text x="270" y="228" text-anchor="middle" font-size="9" fill="#92400e">East: $14,200 (29%)</text>
  <rect x="340" y="215" width="100" height="18" fill="#fde68a" rx="3"/>
  <text x="390" y="228" text-anchor="middle" font-size="9" fill="#92400e">North: $3,800 (8%)</text>
  <rect x="450" y="215" width="90" height="18" fill="#fde68a" rx="3"/>
  <text x="495" y="228" text-anchor="middle" font-size="9" fill="#92400e">West: $12,400 (25%)</text>

  <!-- Arrow -->
  <line x1="400" y1="250" x2="400" y2="270" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow3)"/>

  <!-- Layer 3: Action -->
  <rect x="30" y="275" width="740" height="70" fill="#fce7f3" rx="10"/>
  <text x="50" y="298" font-size="13" font-weight="700" fill="#9d174d">Layer 3: ACTION</text>
  <text x="50" y="316" font-size="11" fill="#334155">"What needs attention right now?"</text>

  <!-- Alerts -->
  <rect x="50" y="322" width="200" height="18" fill="#fecdd3" rx="3"/>
  <text x="150" y="335" text-anchor="middle" font-size="9" font-weight="600" fill="#9d174d">⚠ West cancellation rate 18% (threshold: 10%)</text>
  <rect x="260" y="322" width="200" height="18" fill="#fecdd3" rx="3"/>
  <text x="360" y="335" text-anchor="middle" font-size="9" font-weight="600" fill="#9d174d">⚠ North region only 8% of total revenue</text>

  <defs><marker id="arrow3" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8"/></marker></defs>
</svg>
```

**Design Principles:**

1. **Top layer answers the CEO's question in 5 seconds.** KPIs, trends, status.
2. **Middle layer answers the manager's question in 30 seconds.** Breakdowns, comparisons.
3. **Bottom layer answers the operator's question in 1 minute.** Alerts, thresholds, specific items.
4. **Every chart must serve the story.** Remove charts that do not support overview, detail, or action.
5. **Use color intentionally.** Red for alerts, green for on-target, neutral for context.

**Common Dashboard Mistakes:**

| Mistake | Problem | Fix |
|---------|---------|-----|
| 15 charts on one screen | Viewer does not know where to look | Group into 3 layers, max 5 charts per layer |
| No clear hierarchy | Everything looks equally important | Make KPIs largest, breakdowns medium, alerts highlighted |
| Charts without context | A bar chart with no target or benchmark | Add a reference line, target value, or comparison period |
| Action layer missing | Viewer sees data but does not know what to do | Add alerts, thresholds, or "needs attention" callouts |

### Build

1. Using Power BI, Excel, or pandas output, create a 3-layer dashboard mockup for `sales_orders.csv`.
2. Layer 1: 3–4 KPI cards (total revenue, order count, completion rate, average order value).
3. Layer 2: Revenue breakdown by region (bar chart or table).
4. Layer 3: 2 alerts based on thresholds you define (e.g., cancellation rate > 10%).
5. Write one sentence explaining the story each layer tells.

### Check

- Can someone understand the big picture in 5 seconds from Layer 1?
- Does Layer 2 explain what drives Layer 1?
- Does Layer 3 tell the viewer what to do next?
- Are there any charts that do not serve the story? Remove them.

### Submit

Save your dashboard mockup and story sentences as `week19_day131_dashboard_story.md`.

---

## Day 132: Limitations, Assumptions, and Next Steps

### Learn

Every analytics report has limits. Stating them honestly builds credibility. Hiding them destroys trust when someone discovers the gap.

**Limitations vs Assumptions:**

| Term | Definition | Example |
|------|-----------|---------|
| **Limitation** | Something the data cannot tell you | "This dataset covers Q1 only. We cannot confirm if the West-South gap persists year-round." |
| **Assumption** | Something you are treating as true without proof | "We assume order status 'completed' means payment was received." |
| **Next Step** | What to do to address the limitation or test the assumption | "Collect Q2 data and compare regional trends. Verify 'completed' status definition with the finance team." |

**SVG: Limitations and Assusions Framework**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 300" font-family="system-ui, sans-serif">
  <rect width="800" height="300" fill="#f8fafc" rx="12"/>
  <text x="400" y="30" text-anchor="middle" font-size="16" font-weight="700" fill="#0f172a">Limitations → Assumptions → Next Steps</text>

  <!-- Limitations -->
  <rect x="30" y="55" width="230" height="200" fill="#f3e8ff" rx="10"/>
  <text x="145" y="80" text-anchor="middle" font-size="13" font-weight="700" fill="#6b21a8">Limitations</text>
  <text x="145" y="98" text-anchor="middle" font-size="10" fill="#7c3aed">What the data CANNOT tell us</text>
  <line x1="50" y1="108" x2="240" y2="108" stroke="#c4b5fd" stroke-width="1"/>
  <text x="45" y="125" font-size="10" fill="#4c1d95">• Sample size: 500 orders</text>
  <text x="45" y="142" font-size="10" fill="#4c1d95">• Q1 data only</text>
  <text x="45" y="159" font-size="10" fill="#4c1d95">• No customer demographics</text>
  <text x="45" y="176" font-size="10" fill="#4c1d95">• No competitor pricing data</text>
  <text x="45" y="193" font-size="10" fill="#4c1d95">• "Completed" not verified</text>
  <text x="45" y="210" font-size="10" fill="#4c1d95">• No seasonality context</text>
  <text x="45" y="235" font-size="10" font-style="italic" fill="#7c3aed">Be specific, not vague</text>

  <!-- Arrow -->
  <line x1="265" y1="155" x2="295" y2="155" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow4)"/>

  <!-- Assumptions -->
  <rect x="300" y="55" width="230" height="200" fill="#fef3c7" rx="10"/>
  <text x="415" y="80" text-anchor="middle" font-size="13" font-weight="700" fill="#92400e">Assumptions</text>
  <text x="415" y="98" text-anchor="middle" font-size="10" fill="#b45309">What we treat as TRUE</text>
  <line x1="320" y1="108" x2="510" y2="108" stroke="#fde68a" stroke-width="1"/>
  <text x="315" y="125" font-size="10" fill="#78350f">• "Completed" = paid</text>
  <text x="315" y="142" font-size="10" fill="#78350f">• Q1 represents typical quarter</text>
  <text x="315" y="159" font-size="10" fill="#78350f">• Regions are comparable</text>
  <text x="315" y="176" font-size="10" fill="#78350f">• No major price changes</text>
  <text x="315" y="193" font-size="10" fill="#78350f">• Data entry is accurate</text>
  <text x="315" y="235" font-size="10" font-style="italic" fill="#b45309">State each one clearly</text>

  <!-- Arrow -->
  <line x1="535" y1="155" x2="565" y2="155" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow4)"/>

  <!-- Next Steps -->
  <rect x="570" y="55" width="200" height="200" fill="#dcfce7" rx="10"/>
  <text x="670" y="80" text-anchor="middle" font-size="13" font-weight="700" fill="#166534">Next Steps</text>
  <text x="670" y="98" text-anchor="middle" font-size="10" fill="#15803d">How to address gaps</text>
  <line x1="590" y1="108" x2="750" y2="108" stroke="#86efac" stroke-width="1"/>
  <text x="585" y="125" font-size="10" fill="#14532d">• Collect Q2 data</text>
  <text x="585" y="142" font-size="10" fill="#14532d">• Verify status definitions</text>
  <text x="585" y="159" font-size="10" fill="#14532d">• Add customer data</text>
  <text x="585" y="176" font-size="10" fill="#14532d">• Compare competitor pricing</text>
  <text x="585" y="193" font-size="10" fill="#14532d">• Audit data entry quality</text>
  <text x="585" y="235" font-size="10" font-style="italic" fill="#15803d">Make each step actionable</text>

  <defs><marker id="arrow4" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8"/></marker></defs>
</svg>
```

**How to Write Limitations Without Undermining Your Report:**

| Weak (Undermines) | Strong (Builds Credibility) |
|-------------------|---------------------------|
| "This data is probably wrong." | "This dataset contains 500 orders from Q1 2024. Results may not reflect full-year patterns." |
| "I am not sure about these numbers." | "Order status 'completed' is based on system records and has not been independently verified with finance." |
| "This report might be useless." | "Analysis is limited to the four regions in the dataset. Regions not included may show different patterns." |

**Writing Next Steps That Are Actually Useful:**

| Vague Next Step | Specific Next Step |
|----------------|-------------------|
| "Get more data." | "Collect 500+ additional orders from Q2 2024 and compare regional revenue trends." |
| "Check the data." | "Verify 'completed' order status against finance records for a random sample of 50 orders." |
| "Do more analysis." | "Run the same regional breakdown on Q2 data to confirm whether the West-South gap persists." |

### Build

1. Review your Day 127–131 work.
2. Write 3 limitations of your analysis.
3. Write 2 assumptions you made.
4. Write 3 next steps that address the limitations or test the assumptions.
5. Use the "strong" column examples as your style guide.

### Check

- Are limitations specific (sample size, time period, missing fields)?
- Are assumptions stated clearly, not hidden?
- Are next steps actionable with a specific method and target?

### Submit

Save as `week19_day132_limitations_assumptions_next_steps.md`.

---

## Day 133: Weekly Practical Project — Stakeholder Analytics Report

### Learn

This project combines everything from Days 127–132 into one stakeholder-ready report. You will produce a complete analytics report using `sales_orders.csv` that a business leader could act on.

**Project Requirements:**

Your report must include:

1. **Title** — Answers a specific business question
2. **Executive Summary** — One paragraph: finding + number + action
3. **Context** — Dataset, time period, scope
4. **Findings** — At least 3 data-backed observations with numbers
5. **Insights** — At least 2 insights connecting findings to business meaning
6. **Recommendations** — At least 1 specific, evidence-based recommendation
7. **Limitations** — At least 2 specific limitations
8. **Assumptions** — At least 1 stated assumption
9. **Next Steps** — At least 2 actionable next steps
10. **Visual** — At least one chart, table, or dashboard screenshot from Excel, SQL, pandas, or Power BI

**AI Validation Table (if AI is used for writing support):**

| AI Suggestion | Your Verification | Data Source | Accepted? |
|--------------|------------------|-------------|-----------|
| "West region underperforms" | Checked: West $12,400 vs South $18,800 — confirmed | sales_orders.csv, revenue by region | Yes, with number |
| "Recommend increasing West marketing" | No data supports this — cancellation rate is the issue, not awareness | sales_orders.csv, cancellation analysis | No — rewrote to focus on fulfillment |
| "Sample size is sufficient" | 500 orders is moderate — noted as limitation | Dataset row count | No — added to limitations |

**Report Template:**

```markdown
# [Title: Business Question This Report Answers]

## Executive Summary
[One paragraph: context + key finding with number + business impact + recommended action]

## Context
- Dataset: sales_orders.csv
- Time period: [specify]
- Scope: [specify regions, metrics, filters]
- Audience: [who will read this]

## Findings
1. [Observation with number and data source]
2. [Observation with number and data source]
3. [Observation with number and data source]

## Insights
1. [What Finding 1 means for the business]
2. [What Finding 2 means for the business]

## Recommendations
1. [Specific action tied to Insight 1]
2. [Specific action tied to Insight 2]

## Limitations
1. [Specific limitation with impact]
2. [Specific limitation with impact]

## Assumptions
1. [Stated assumption]

## Next Steps
1. [Actionable step with method]
2. [Actionable step with method]

## Appendix
- [Charts, tables, queries, or methodology notes]
```

**Grading Criteria:**

| Criteria | Weight | What We Look For |
|----------|--------|-----------------|
| Executive Summary | 20% | One paragraph, includes number and action |
| Findings | 20% | At least 3, all data-backed with numbers |
| Insights | 15% | Connect findings to business meaning |
| Recommendations | 15% | Specific, actionable, tied to insights |
| Limitations & Assumptions | 10% | Honest, specific, not vague |
| Next Steps | 10% | Actionable with method |
| Visual Evidence | 10% | At least one chart or table from analysis tools |

### Build

1. Complete your full stakeholder analytics report using the template above.
2. Include at least one visual from Excel, SQL, pandas, or Power BI.
3. If you used AI for any writing, complete the AI Validation Table.
4. Review against the grading criteria.

### Check

- Does the executive summary stand alone?
- Are all findings backed by numbers from `sales_orders.csv`?
- Are insights distinct from observations?
- Are recommendations specific and tied to insights?
- Are limitations honest and specific?
- Is there at least one visual?

### Submit

Save your complete report as `week19_day133_stakeholder_report.md`. Include your AI Validation Table if applicable.

---

## Week 19 Summary

This week taught you how to turn analytics output into decision-ready business reporting. You learned:

- **Report structure** — Title, executive summary, context, findings, insights, recommendations, limitations, next steps
- **Executive summary writing** — One paragraph with context, number, impact, and action
- **Observation vs Insight vs Recommendation** — The three distinct layers of analytical thinking
- **Root cause thinking** — Asking "why" behind every observation, verified with data
- **Dashboard story flow** — Overview → Detail → Action, designed for different audience levels
- **Limitations and assumptions** — Stating what the data cannot tell you builds credibility
- **Stakeholder-ready language** — Cautious, evidence-based, specific, and actionable

You now have the skills to produce reports that business leaders can act on, not just read.

**Next Week:** Week 20 will cover [topic to be announced].

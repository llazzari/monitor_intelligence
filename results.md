# Checkout Behavior Analysis — Methodology and Insights

## 1. Introduction

This notebook aims to analyze **checkout behavior over time** and detect potential **anomalies** that may indicate operational issues, user behavior changes, or data collection problems. The approach is **comparative**: actual checkouts on the current day are compared against historical baselines (weekly and monthly averages, as well as yesterday and the same day last week).

The rationale behind this analysis is that anomalies rarely appear in isolation. They become evident when the actual behavior **deviates significantly** from what is historically expected. By incorporating multiple baselines (short-, medium-, and long-term), the notebook is able to distinguish between:

* **Random fluctuations** (noise, single-day variation)
* **Short-term operational issues** (e.g., data collection errors or temporary failures)
* **Behavioral shifts** (systematic changes in user activity patterns)

---

## 2. Data

The code first loads the dataset, which contains **timestamps and checkout counts per hour**. The datasets contain:

   * **Hourly timestamp** 
   * **Today's data**  
   * **Last week average** (shorter horizon, sensitive to recent shifts).
   * **Last month average** (longer horizon, smoother seasonal effects).
   * **Yesterday’s data** (immediate context, helps confirm anomalies).
   * **Same day last week** (seasonal day-of-week effect).


This structure allows us to check whether today’s values are **significantly above or below expected levels**.

---

## 3. Anomaly Detection Rationale

The notebook does not rely on a single statistical threshold. Instead, it applies **contextual anomaly detection**:

* **Step 1: Compare actual counts vs weekly/monthly averages.**

  * If today’s value is **> 100% higher** or **< 50% lower**, it is flagged as a potential anomaly.

* **Step 2: Validate with yesterday and the same day last week.**

  * If the deviation is also present yesterday or last week, it may not be an anomaly but rather a **behavioral shift**.
  * If the deviation is unique to today (but not seen historically), it strengthens the anomaly hypothesis.

* **Step 3: Categorize anomalies.**

  * **Critical anomaly:** Large deviation with no historical precedent.
  * **Moderate anomaly:** Noticeable deviation, but partially aligned with history.
  * **Seasonal / baseline shift:** Consistent with recent days → not an anomaly, but a change in trend.

This layered approach prevents false alarms while still capturing unusual events.

---

## 4. Visualization

The notebook produces line charts to visually compare **today vs historical baselines**. This visual inspection helps confirm the findings flagged by the anomaly rules.

The **main rationale** here is that anomalies should be **visible and interpretable**, not just numerical. For example:

* A sudden drop in morning checkouts may indicate a **system outage**.
* A sharp spike at unusual hours may indicate **bot activity** or a **special campaign**.

---

## 5. Transcribed Analysis Sections

Below are the detailed written analyses directly for each dataset.

---

### Analysis 1

Early Morning (00h – 05h)

* Checkout behavior remained **consistent and stable**. The marks on the graph will be discussed below.
* In the graph, the single checkout at 03h is pointed out as a spike, but this is a consequence of both last week and month averages being too low at these times (< 1). It problably isn't an anomaly.
* At 04h, there was no checkouts, which is expected given the low averages (< 1) at this time.

Morning drop (06h - 09h) - **anomaly candidate**

* Checkouts considerably smaller than what was expected. Specially, at 08h when no checkouts were registered.
* **06h anomaly**:

  * Today: **1 checkout**
  * Expected: 2-3 checkouts (last week/month avgs)
* **07h anomaly**:

  * Today: **1 checkout**
  * Expected: \~5 checkouts (last week/month avgs)
* **08h anomaly**:

  * Today: **0 checkouts**
  * Weekly avg: **8.7**
  * Monthly avg: **10.4**
  * Yesterday: **1 checkout**
* **09h anomaly**:

  * Today: **2 checkouts**
  * Expected: \~20 (last week/month avgs)
* This suggests a **short-term operational issue** (last 2 days), not a long-term trend, since it did not appear last week but was also reflected yesterday, in particular from 06h to 08h.


Peak Build-up (10h – 11h)

* **10h peak (today)**: **55 checkouts**

  * +86.9% vs weekly avg (29.4)
  * +93.9% vs monthly avg (28.3)
  * +7.8% vs yesterday (51)
  * +13% vs the same day last week (45)
* Normally, peak occurs at **11h (avg 33.7)** → today shifted **1h earlier**.

  * In line with yesterday and the same day last week. May suggest a recent behavioral change.


Afternoon (12h – 17h) - **anomaly candidates**

* Consistently **above both averages** across multiple hours:

  * **12h**: 51 checkouts → +85% vs weekly avg (27.6), +100% vs monthly avg (25.4), +31% vs yesterday and the same day last week (39)
  * **15h**: 51 checkouts → +81% vs weekly avg (28.1), +84% vs monthly avg (27.7), +46% vs yesterday (35), +4% vs the same day last week (49)
  * **17h**: 45 checkouts → +120% vs weekly avg (20.4), +102% vs monthly avg (22.3), +50% vs yesterday (30), +55% vs the same day last week
* The 12h peak is well above both averages, **moderate anomaly**
* The 15h peak is aligned with last week's 49 checkouts on the same day -> likely not an anomaly, but a weekly pattern.
* 17h peak well above any other day, **strong anomaly**.


Evening (18h – 22h)

* Checkouts remained **well above historical averages**, but in line with yesterday and the same day last week.
* May indicate a baseline shift.


**Possible Anomalies**

* **Critical**: 06h – 09h drop; 17h spike.
* **Moderate**: 12h.
* **Seasonal** (likely not an anomaly): 15h.

---

### Analysis 2

Early Morning (00h – 06h)

* Checkout behavior remained **consistent and stable**.
* The 3 checkouts at 02h and the 2 at 05h are flagged as spikes, but these likely reflect **low historical baselines** (< 1 checkout) rather than real anomalies.
* At 03h and 04h, no checkouts occurred — which is expected given the historically low averages.


Morning Spikes (07h – 09h) — **Anomaly Candidates**

* Checkouts show a **clear deviation** from expectations.

**07h — Moderate Anomaly**

* Today: **10 checkouts**
* Expected: 3–5 checkouts (weekly/monthly averages)
* Yesterday: 2 checkouts (possibly anomalous baseline)

**08h — Strong Anomaly**

* Today: **25 checkouts**
* Weekly avg: **3.71 checkouts** (+573%)
* Monthly avg: **9.82 checkouts** (+155%)
* Same day last week: **12 checkouts** (+108%)
* Yesterday: **0 checkouts** (anomalous)

**09h — Strong Anomaly**

* Today: **36 checkouts**
* Expected: **10–17 checkouts** (weekly/monthly averages) → > +100% deviation
* Same day last week: **27 checkouts** (+33%)
* Yesterday: **2 checkouts** (anomalous)

Midday Peak (10h – 13h)

* Checkout levels remained **well above weekly/monthly averages**,
* but aligned with yesterday and the same day last week.
* Suggests a **baseline shift** rather than a temporary anomaly.


Afternoon (14h – 18h) — **Anomaly Candidates**

* **14h:** 19 checkouts

  * Slightly below averages (19.5–24.9)
  * Considerably lower than yesterday (32) and last week (35).

* **15h – 17h:** **No checkouts registered → Strong anomaly candidate.**

* **18h:** 13 checkouts, indicating **possible reestablishment of data collection**.


Evening (19h – 23h)

* Checkouts stayed **above historical averages**,
* but consistent with yesterday and the same day last week.
* Likely reflects a **baseline shift**.

**Possible Anomalies**

* **Critical:**

  * 08h–09h spikes
  * 15h–17h drop

* **Moderate:**

  * 07h
  * 14h (beginning of afternoon drop)
  * 18h (recovery after missing data)

---

## 6. Conclusion

The methodology combines **quantitative thresholds** with **contextual validation**, ensuring anomalies are detected in a robust manner. The analyses reveal both **short-term operational issues** (e.g., missing data or sudden drops) and **longer-term behavioral shifts** (consistent increases aligned with yesterday and last week).

This structured approach enables stakeholders to distinguish between:

* **True anomalies** requiring immediate action, and
* **Baseline shifts** signaling evolving user behavior.

---

# Anomaly Detection System
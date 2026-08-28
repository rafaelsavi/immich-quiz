# Scoring System

Immich Quiz awards up to **100 points** for each enabled objective in a round (Location and/or Date). The scoring style depends on the game mode:

- **Pinpoint**: Uses exponential decay—the closer your guess, the more points you get.
- **Album Shuffle**: Uses strict matching—points are split evenly among correctly matched or sequenced photos in the batch.

---

## Pinpoint Game

In Pinpoint mode, you guess where and when an individual photo was taken. Each guess is scored independently from 0 to 100 points based on how close you got.

### 📍 Location Scoring

Points drop off exponentially with distance ($d$) using the Haversine formula (great-circle distance on Earth):

$$\text{Score} = \max\left(0, \text{round}\left(100 \times \exp\left(-\frac{d}{\text{decay\_km}}\right)\right)\right)$$

- **Pool Decay ($\text{decay\_km}$)**: Dynamically calculated based on the geographic diagonal span ($D_{\text{span}}$) of candidate photos in the match pool, using **5th–95th percentile trimming** to filter out isolated airport layovers or GPS glitches:
  $$\text{decay\_km} = \text{clamp}\left(\frac{D_{\text{span}}}{\text{LOCATION\_SPAN\_RATIO}},\; 5.0\text{ km},\; 200.0\text{ km}\right)$$
  *(where $\text{LOCATION\_SPAN\_RATIO} = 10.0$ sets the decay unit to $\frac{1}{10}\text{th}$ of the map diagonal)*
- **How it feels**:
  - **Single City / Walking Tour** ($D_{\text{span}} \le 50\text{ km}$): Decay scales down to the floor of $\approx 5.0\text{ km}$. A $500\text{m}$ error earns $90$ points, while being $10\text{ km}$ away yields $14$ points.
  - **Regional / Country Match** ($D_{\text{span}} \approx 300\text{ km}$): Decay scales to $\approx 30.0\text{ km}$.
  - **Worldwide / Global Match** ($D_{\text{span}} \ge 2000\text{ km}$): Decay reaches the full $200.0\text{ km}$ ceiling.

### 📅 Date Scoring

Because players select a **year and month** rather than a specific calendar day, your guess gives you credit for the entire month!

Error is measured in **days** ($\Delta D$) from the closest boundary of your guessed month:

- **Right on target**: If the photo was taken inside your guessed month, your error is **0 days** $\rightarrow$ **100 points**.
- **Earlier than guess**: Measured in days from the 1st of your guessed month back to the capture date.
- **Later than guess**: Measured in days from the last day of your guessed month to the capture date (accounting for month lengths and leap years).

$$\text{Score} = \max\left(0, \text{round}\left(100 \times \exp\left(-\frac{\Delta D}{\text{decay\_days}}\right)\right)\right)$$

- **Pool Decay ($\text{decay\_days}$)**: Dynamically calculated based on the timespan ($\Delta T_{\text{days}} = p_{95}(\text{dates}) - p_5(\text{dates})$) of candidate photos in the match pool, using **5th–95th percentile trimming** to ignore isolated misdated scans or clock resets:
  $$\text{decay\_days} = \text{clamp}\left(\frac{\Delta T_{\text{days}}}{\text{DATE\_SPAN\_RATIO}},\; 30.0\text{ days},\; 500.0\text{ days}\right)$$
  *(where $\text{DATE\_SPAN\_RATIO} = 6.0$ sets the decay unit to $\frac{1}{6}\text{th}$ of the album timespan)*
- **How it feels**:
  - **Short Vacation / Trip** ($\Delta T \le 180\text{ days}$): Decay scales down to $\approx 30.0\text{ days}$ (~1 month), making month guesses competitive for vacation albums.
  - **Multi-Year Archive** ($\Delta T > 8\text{ years}$): Decay uses the full $500.0\text{ days}$ (~16 months) ceiling.

### 🎯 How `span_ratio` Shapes the Scoring Curve

The `span_ratio` translates the total geographic or temporal scope of an album into the decay parameter, defining what fraction of the map or timeline corresponds to specific score benchmarks:

| Relative Error (% of Album Span) | Location Score (`ratio = 10.0`) | Date Score (`ratio = 6.0`)      | Player Feedback                                  |
|:---------------------------------|:--------------------------------|:--------------------------------|:-------------------------------------------------|
| **$\le 1\%$ of album span**      | **$90\text{--}100\text{ pts}$** | **$94\text{--}100\text{ pts}$** | Bullseye pinpoint accuracy                       |
| **$2.5\%$ of album span**        | **$78\text{ pts}$**             | **$86\text{ pts}$**             | Very close (correct neighborhood / exact season) |
| **$5\%$ of album span**          | **$61\text{ pts}$**             | **$74\text{ pts}$**             | Close (correct metro area / adjacent month)      |
| **$10\%$ ($1/\text{ratio}$)**    | **$37\text{ pts}$** ($1/e$)     | **$55\text{ pts}$**             | General ballpark                                 |
| **$20\%$ of album span**         | **$14\text{ pts}$**             | **$30\text{ pts}$**             | Significantly off                                |
| **$\ge 40\%$ of album span**     | **$\le 2\text{ pts}$**          | **$\le 9\text{ pts}$**          | Missed entirely                                  |

---

## Album Shuffle Game

In **Album Shuffle** mode, 3 photos are presented simultaneously. Each photo is allocated an equal share of the round's maximum score ($\frac{100}{N} \approx 33.33\text{ points}$ per enabled goal). Both map location matching and timeline chronological ordering use **adaptive exponential decay**:

$$\text{Round Score} = \max\left(0, \min\left(100, \text{round}\left(\frac{100}{N} \sum_{i=1}^N \exp\left(-\frac{\text{error}_i}{\text{decay}}\right)\right)\right)\right)$$

### 📍 Location Proximity Scoring

- **Error ($d_i$)**: Physical distance (Haversine in km) between the photo's true location and the assigned map pin's location ($0\text{ km}$ if matched to its exact pin).
- **Batch Spatial Decay ($\text{decay\_km}$)**: Dynamically calculated from the bounding box diagonal span of the active batch's 3 pins via `calculate_location_decay(batch_assets)`, clamped to $[5.0\text{ km},\; 200.0\text{ km}]$.
- **How it feels**:
  - **Exact pin match** ($d = 0\text{ km}$): Earns the full $33.33\text{ pts}$ for that photo.
  - **Local pin swap in a worldwide match** (e.g., swapping two Paris pins $3\text{ km}$ apart when the round includes Paris, Rome, and Tokyo): In a $200\text{ km}$ decay pool, $\exp(-3/200) \approx 0.985 \rightarrow 32.8\text{ pts}$ each ($\approx 99\text{ pts}$ total round score).
  - **Distant pin swap** (e.g., placing Tokyo photo on a Paris pin, $d = 9700\text{ km}$): $\exp(-9700/200) \approx 0 \rightarrow 0\text{ pts}$ for those slots.

### 📅 Date Chronological Scoring

- **Error ($\Delta D_i$)**: Time difference in days between the photo placed in slot $i$ and the true capture date of the photo belonging to that chronological slot:
  $$\Delta D_i = |\text{capture\_date}(\text{placed photo}) - \text{capture\_date}(\text{true photo for slot } i)|$$
- **Batch Temporal Decay ($\text{decay\_days}$)**: Dynamically calculated from the active batch's timespan via `calculate_date_decay(batch_assets)`, clamped to $[30.0\text{ days},\; 500.0\text{ days}]$.
- **How it feels**:
  - **Exact chronological placement** ($\Delta D = [0, 0, 0]$): Earns $100\text{ pts}$ ($33.33\text{ pts} \times 3$).
  - **Flipping same-week photos in a 10-year album**: If you recognize that a 2014 photo is from a decade ago, but accidentally flip two 2024 photos taken 2 days apart ($\Delta D = 2\text{ days}$ in a $500\text{d}$ decay pool), you lose $< 1\text{ pt}$ ($\approx 99.8\text{ pts}$).
  - **Confusing eras**: Placing a 2014 photo in a 2024 slot ($\Delta D = 3650\text{ days} \gg 500\text{d}$) yields $0\text{ pts}$ for those slots, while correctly sequenced photos still earn full credit.

---

## Exponential Decay Quick Reference

Here is how scores translate for common distance/time errors across different decay settings:

| Error (Distance / Time)  | Decay = 100 | Decay = 200 | Decay = 300 | Decay = 500 *(default)* | Decay = 750 | Decay = 1000 |
|:-------------------------|:------------|:------------|:------------|:------------------------|:------------|:-------------|
| **1 (1 km / 1 day)**     | 99          | 100         | 100         | **100**                 | 100         | 100          |
| **5 (5 km / 5 days)**    | 95          | 98          | 98          | **99**                  | 99          | 100          |
| **10 (10 km / 10 days)** | 90          | 95          | 97          | **98**                  | 99          | 99           |
| **100 (~3 months)**      | 37          | 61          | 72          | **82**                  | 88          | 90           |
| **500 (~1.5 years)**     | 1           | 8           | 19          | **37**                  | 51          | 61           |
| **1000 (~3 years)**      | 0           | 1           | 4           | **14**                  | 26          | 37           |

---

## Match Totals & Accuracy

- **Max Possible Score**: Each round contributes up to 100 points per enabled objective (100 if location-only or date-only, 200 if both are enabled).
  $$\text{MaxPossibleScore} = \text{roundsPlayed} \times \left((\text{100 if location\_mode}) + (\text{100 if date\_mode})\right)$$

- **Accuracy (%)**: Your overall performance across the match expressed as a percentage:
  $$\text{Accuracy (\%)} = \text{round}\left(\frac{\text{TotalScore}}{\text{MaxPossibleScore}} \times 100, 1\right)$$

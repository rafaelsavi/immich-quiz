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

| Relative Error (% of Album Span) | Location Score (`ratio = 10.0`) | Date Score (`ratio = 6.0`) | Player Feedback |
|:---|:---|:---|:---|
| **$\le 1\%$ of album span** | **$90\text{--}100\text{ pts}$** | **$94\text{--}100\text{ pts}$** | Bullseye pinpoint accuracy |
| **$2.5\%$ of album span** | **$78\text{ pts}$** | **$86\text{ pts}$** | Very close (correct neighborhood / exact season) |
| **$5\%$ of album span** | **$61\text{ pts}$** | **$74\text{ pts}$** | Close (correct metro area / adjacent month) |
| **$10\%$ ($1/\text{ratio}$)** | **$37\text{ pts}$** ($1/e$) | **$55\text{ pts}$** | General ballpark |
| **$20\%$ of album span** | **$14\text{ pts}$** | **$30\text{ pts}$** | Significantly off |
| **$\ge 40\%$ of album span** | **$\le 2\text{ pts}$** | **$\le 9\text{ pts}$** | Missed entirely |

---

## Album Shuffle Game

In **Album Shuffle** mode, 3 photos are shown simultaneously. Points are divided equally across the batch ($N = 3$).

### 📍 Location Scoring

- Each photo matched to its correct map pin earns a proportional share of the 100 points:

$$\text{Location Score} = \max\left(0, \text{round}\left(\frac{\text{correct\_pins}}{N} \times 100\right)\right)$$

*(e.g., 3/3 = 100 pts, 2/3 = 67 pts, 1/3 = 33 pts, 0/3 = 0 pts)*

### 📅 Date Scoring

- Each photo placed in its correct chronological order on the timeline earns a proportional share of the 100 points:

$$\text{Date Score} = \max\left(0, \text{round}\left(\frac{\text{correct\_ranks}}{N} \times 100\right)\right)$$

---

## Exponential Decay Quick Reference

Here is how scores translate for common distance/time errors across different decay settings:

| Error (Distance / Time) | Decay = 100 | Decay = 200 | Decay = 300 | Decay = 500 *(default)* | Decay = 750 | Decay = 1000 |
|:---|:---|:---|:---|:---|:---|:---|
| **1 (1 km / 1 day)**    | 99          | 100         | 100         | **100**                 | 100         | 100          |
| **5 (5 km / 5 days)**   | 95          | 98          | 98          | **99**                  | 99          | 100          |
| **10 (10 km / 10 days)**| 90          | 95          | 97          | **98**                  | 99          | 99           |
| **100 (~3 months)**     | 37          | 61          | 72          | **82**                  | 88          | 90           |
| **500 (~1.5 years)**    | 1           | 8           | 19          | **37**                  | 51          | 61           |
| **1000 (~3 years)**     | 0           | 1           | 4           | **14**                  | 26          | 37           |

---

## Match Totals & Accuracy

- **Max Possible Score**: Each round contributes up to 100 points per enabled objective (100 if location-only or date-only, 200 if both are enabled).
  $$\text{MaxPossibleScore} = \text{roundsPlayed} \times \left((\text{100 if location\_mode}) + (\text{100 if date\_mode})\right)$$

- **Accuracy (%)**: Your overall performance across the match expressed as a percentage:
  $$\text{Accuracy (\%)} = \text{round}\left(\frac{\text{TotalScore}}{\text{MaxPossibleScore}} \times 100, 1\right)$$

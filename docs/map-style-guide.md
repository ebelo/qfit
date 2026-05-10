# 🎨 qfit Map Visualization Style Guide  
*Strava activities — semantic colors, palette, and adaptive rendering*

---

## 1. Purpose

This document defines how outdoor activities are visualized in qfit maps.

Goals:
- Ensure **instant readability** when many activities are displayed together  
- Maintain **semantic consistency across activity types**  
- Provide a **color-blind-aware palette**  
- Ensure visibility across **different basemaps (Outdoor, Light, Satellite)**  

---

## 2. Core Design Principles

### 2.1 Semantic Color Families (Strict Rule)

Each activity type maps to a **single color family**.

| Semantic meaning                     | Color family |
|-------------------------------------|--------------|
| Effort / cardio (running)           | Red          |
| Speed / motion (cycling)            | Orange       |
| Human-powered low speed (walking)   | Yellow       |
| Winter activities                   | Blue         |
| Water activities                    | Blue / Cyan  |
| Mountain / rock                     | Brown        |
| Indoor / fitness                    | Purple       |
| Machine / virtual                   | Grey         |

👉 **Rule:** One semantic = one color family (no overlap)

---

### 2.2 Seasonal Consistency

- ❌ Yellow MUST NOT be used for winter  
- ❌ Blue MUST NOT be used for walking activities  
- ✅ All winter activities must stay in the **blue family**

---

### 2.3 Color-Blind Awareness

- Avoid red–green conflicts  
- Use clearly separated color families  
- Do not rely on subtle hue differences  
- Combine color with:
  - line width
  - opacity

---

### 2.4 Minimal Cognitive Load

- Keep palette compact  
- Avoid unnecessary variation  
- Users should recognize activities **without reading a legend**

---

## 3. Color Palette (Reference)

| Semantic | Hex |
|----------|-----|
| Red      | `#D62828` |
| Orange   | `#F77F00` |
| Yellow   | `#FFD60A` |
| Blue     | `#0077B6` |
| Cyan     | `#00B4D8` |
| Teal     | `#2A9D8F` |
| Brown    | `#8B5E34` |
| Purple   | `#7B2CBF` |
| Grey     | `#6C757D` |

---

## 4. Strava Activity Mapping

### 🏃 Running (Red)

| Activity   | Hex |
|------------|-----|
| Run        | `#D62828` |
| TrailRun   | `#9D0208` |
| VirtualRun | `#868E96` |

---

### 🚴 Cycling (Orange)

| Activity            | Hex |
|---------------------|-----|
| Ride                | `#F77F00` |
| MountainBikeRide    | `#D95F02` |
| GravelRide          | `#BC6C25` |
| EBikeRide           | `#6C757D` |

---

### 🚶 Walking / Hiking (Yellow)

| Activity     | Hex |
|--------------|-----|
| Walk         | `#FFD60A` |
| Hike         | `#F9C74F` |
| Backpacking  | `#E9C46A` |

---

### ❄️ Winter Sports (Blue ONLY)

| Activity          | Hex |
|-------------------|-----|
| AlpineSki         | `#0077B6` |
| BackcountrySki    | `#023E8A` |
| NordicSki         | `#0096C7` |
| Snowboard         | `#00B4D8` |
| Snowshoe          | `#48CAE4` |

---

### 🌊 Water Sports (Blue / Cyan)

| Activity            | Hex |
|---------------------|-----|
| Swim                | `#0077B6` |
| OpenWaterSwim       | `#023E8A` |
| Kayaking            | `#1B9AAA` |
| Canoeing            | `#2A9D8F` |
| Rowing              | `#264653` |
| StandUpPaddling     | `#48CAE4` |
| Surfing             | `#0096C7` |

---

### 🏔️ Mountain / Climbing

| Activity         | Hex |
|------------------|-----|
| RockClimbing     | `#8B5E34` |
| Mountaineering   | `#6B4423` |
| IceClimbing      | `#90E0EF` |

---

### 🏋️ Indoor / Fitness

| Activity        | Hex |
|-----------------|-----|
| Workout         | `#7B2CBF` |
| Crossfit        | `#5A189A` |
| WeightTraining  | `#3C096C` |
| Yoga            | `#C77DFF` |

---

### ⚫ Machine / Virtual / Other

| Activity     | Hex |
|--------------|-----|
| VirtualRide  | `#6C757D` |
| Commute      | `#495057` |
| Other        | `#9E9E9E` |

---

## 5. Rendering Rules

### 5.1 Base Style

| Property | Value |
|----------|------|
| Width    | 1.5–2.0 px |
| Opacity  | 0.8–0.9 |
| Cap      | Round |
| Join     | Round |

---

### 5.2 Highlighted Activity

- Width: **3 px**  
- White outer glow: **0.5–1 px**

---

### 5.3 Overlapping Tracks

- Use **opacity < 1**  
- Avoid fully opaque lines  
- Prefer thickness over brightness  

---

## 6. Visual Encoding

| Property   | Meaning |
|------------|--------|
| Color      | Activity type |
| Thickness  | Selection / importance |
| Opacity    | Density |

👉 Do not rely on color alone

---

## 7. Basemap Adaptation

### Principle

> **Stable palette + adaptive rendering**

Colors remain unchanged across basemaps.  
Only rendering parameters are adjusted.

---

### 🗺️ Mapbox Outdoor (Reference)

| Property | Value |
|----------|------|
| Width    | 1.5–2.0 px |
| Opacity  | ~0.85 |
| Outline  | Optional |

---

### 🤍 Mapbox Light

| Property | Value |
|----------|------|
| Width    | ≥ 2.0 px |
| Opacity  | ~0.9 |
| Outline  | Yes |

Outline:
- Color: `#333333`
- Width: `0.3–0.5 px`

---

### 🛰️ Satellite

| Property | Value |
|----------|------|
| Width    | 2.0–2.5 px |
| Opacity  | ~0.95 |
| Outline  | Mandatory |

Outline:
- Color: `#FFFFFF`
- Width: `0.8–1.2 px`

---

## 8. Color Adaptation per Basemap

### Principle

> **Stable hue, adaptive luminance**

- Hue = semantic meaning (fixed)  
- Lightness / saturation = adjusted for readability  

---

### Mapbox Outdoor

- Default palette  
- No color changes  

---

### Mapbox Light (Darkened Colors)

| Semantic | Default | Light variant |
|----------|--------|--------------|
| Red      | `#D62828` | `#C1121F` |
| Orange   | `#F77F00` | `#E85D04` |
| Yellow   | `#FFD60A` | `#E0B000` |
| Blue     | `#0077B6` | `#005F99` |

---

### Satellite (Enhanced Colors)

| Semantic | Default | Satellite variant |
|----------|--------|------------------|
| Red      | `#D62828` | `#E63946` |
| Orange   | `#F77F00` | `#FF7F11` |
| Yellow   | `#FFD60A` | `#FFDD00` |
| Blue     | `#0077B6` | `#0096C7` |

---

### Constraints

- No hue shifts  
- No semantic confusion  
- Adjustments must remain subtle  

---

### Priority

1. Outline  
2. Line width  
3. Opacity  
4. Color adjustment  

---

## 9. QGIS Implementation

### Mapbox raster vs vector expectations

Use **Mapbox raster tiles** when the goal is the closest visual parity with
Mapbox's own renderer. Raster tiles are pre-rendered by Mapbox, so they preserve
Mapbox GL styling decisions such as labels, sprites, fonts, antialiasing, and
zoom interpolation more faithfully.

Use **Mapbox vector tiles** when the goal is native QGIS rendering for an
interactive/local workflow. qfit converts and simplifies Mapbox style rules for
QGIS, but this remains an approximation: QGIS and Mapbox GL JS differ in
expression support, label placement and collision behavior, symbol/sprite
handling, font substitution, antialiasing, and zoom-stop interpolation.

For Mapbox Outdoors specifically:

- raster mode is the user-facing choice for highest visual fidelity;
- vector mode is intended to be a useful QGIS-native approximation, not a
  pixel-perfect clone;
- rendering-sensitive vector changes should be checked with the manual visual
  comparison harness in `docs/mapbox-outdoors-comparison-harness.md`.

### Symbology

Layer Properties → Symbology → Categorized  
Column: `sport_type`

---

### Recommended Styles

- `qfit_outdoor.qml`
- `qfit_light.qml`
- `qfit_satellite.qml`

---

## 10. Key Takeaways

- Use **one consistent palette**  
- Do NOT change color meaning across maps  
- Adapt rendering instead (width, outline, opacity)  
- Prioritize **semantic clarity over visual variety**

---

## 11. Future Improvements

- Automatic basemap detection  
- Color-blind simulation validation  
- User-customizable themes  
- Speed / elevation gradients  
- Time-based animation  

---

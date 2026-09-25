# 🏙️ CityPulse — The Live Civic Health Dashboard

> **One Glance. A Safer, Smarter City.**

CityPulse is a civic intelligence platform that brings together **weather, air quality, traffic, and civic incident data** into a single, easy-to-understand dashboard.

It combines **multi-source data fusion, zone-based analytics, anomaly detection, correlation analysis, interactive maps, real-time alerts, and AI-powered situation briefings** to help residents and civic stakeholders understand what is happening across a city.

---

## 🎯 Problem Statement

### AmiHacks — Problem Statement 2

**CityPulse: The Live Civic Health Dashboard**

Civic information is often scattered across multiple applications, departments, and data sources. Residents may discover problems only after they occur, while city operators may struggle to identify relationships between different events.

For example:

> **Heavy rainfall → traffic congestion → waterlogging incidents**

CityPulse attempts to connect these signals and present them as a **single civic pulse** that can be understood at a glance.

---

## 💡 Our Solution

CityPulse creates a unified civic-health view by:

* 🌦️ Collecting weather data
* 🌫️ Monitoring air-quality indicators
* 🚗 Tracking traffic conditions
* 🚨 Incorporating civic incidents
* 🔄 Normalizing heterogeneous data
* 📊 Calculating a composite **CityPulse Index**
* ⚠️ Detecting unusual conditions
* 🔗 Identifying correlations between civic signals
* 🤖 Generating AI-powered situation briefings
* 🗺️ Visualizing conditions geographically
* 🔔 Providing alerts for important changes
* 👥 Allowing users to report civic issues

---

## 🏗️ System Architecture

```text
                 ┌─────────────────────────┐
                 │      DATA SOURCES       │
                 │                         │
                 │ Weather   Air Quality   │
                 │ Traffic   Incidents     │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ DATA PROCESSING         │
                 │                         │
                 │ Fetch • Clean           │
                 │ Normalize • Timestamp   │
                 │ Zone Mapping            │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ ANALYTICS ENGINE        │
                 │                         │
                 │ CityPulse Index         │
                 │ Anomaly Detection       │
                 │ Correlation Analysis    │
                 └────────────┬────────────┘
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐
        │ AI INSIGHTS      │    │ DASHBOARD        │
        │                  │    │                  │
        │ Groq LLM         │    │ Map + KPIs       │
        │ Situation Brief  │    │ Alerts + Trends  │
        └──────────────────┘    └──────────────────┘
```

---

## ✨ Key Features

### 🌐 Multi-Source Data Fusion

CityPulse integrates multiple civic data categories:

* Weather
* Air Quality
* Traffic
* Civic Incidents

The data is converted into a common internal structure for analysis.

---

### 📍 Zone-Based Civic Intelligence

The prototype divides Jaipur into monitored zones, allowing conditions to be analyzed geographically rather than treating the entire city as one location.

Current prototype zones include:

* Mansarovar
* Vaishali Nagar
* Sodala
* Malviya Nagar
* C-Scheme
* Jagatpura
* Tonk Road
* Ajmer Road

---

### 📊 CityPulse Index

CityPulse calculates a composite civic-stress index using weighted signals from:

```text
Traffic        → 35%
Air Quality    → 30%
Incidents      → 20%
Weather        → 15%
```

The resulting score provides a simplified snapshot of current conditions.

> The CityPulse Index is an experimental prototype metric and is not an official government rating.

---

### ⚠️ Anomaly Detection

The system uses statistical analysis to identify unusual traffic conditions.

A Z-score based approach compares recent observations against their baseline and can flag unusual deviations.

```text
Historical Observations
          ↓
       Baseline
          ↓
    Mean + Std. Dev.
          ↓
       Z-Score
          ↓
   Anomaly Detection
```

---

### 🔗 Correlation Analysis

CityPulse analyzes relationships between civic signals, including:

* 🌧️ Rainfall ↔ Traffic
* 🚗 Traffic ↔ Air Quality

The system reports correlation values and sample sizes.

> Correlation is presented as an observed relationship and is **not treated as proof of causation**.

---

### 🤖 AI Situation Briefing

CityPulse uses a Groq-hosted LLM to transform structured analytical information into a concise, human-readable briefing.

The AI layer can provide:

* Current situation
* Why it matters
* Key observations
* Short-term outlook

The AI is grounded in the system's available data rather than being used as the source of sensor measurements.

---

### 🗺️ Interactive Map

The dashboard uses:

* **Leaflet**
* **OpenStreetMap**

The map displays zone conditions and civic incidents geographically.

---

### 🚨 Alerts & Notifications

The dashboard can identify important conditions and provide browser-based notifications when configured thresholds are reached.

---

### 👥 Public Issue Reporting

Users can report civic issues by providing:

* Area
* Issue type
* Severity
* Description

This allows the dashboard to incorporate community-generated civic information.

---

### 🧪 Scenario Simulation

CityPulse includes simulated scenarios for demonstration and testing:

#### 🌧️ Heavy Rain

Simulates increased rainfall, traffic stress and related incidents.

#### 🚗 Traffic Accident

Simulates a localized traffic disruption.

#### 🌫️ Pollution Spike

Simulates increased air-pollution indicators.

#### 🔄 Baseline

Returns the system to the baseline state.

This allows the complete analytics pipeline to be demonstrated without waiting for a real-world event.

---

## 🛠️ Technology Stack

| Layer           | Technology                                 |
| --------------- | ------------------------------------------ |
| Backend         | Python                                     |
| Web Application | Python HTTP/Web backend                    |
| Database        | SQLite                                     |
| Frontend        | HTML, CSS, JavaScript                      |
| Mapping         | Leaflet + OpenStreetMap                    |
| Weather Data    | Open-Meteo                                 |
| Air Quality     | Open-Meteo                                 |
| Traffic         | TomTom Traffic API                         |
| AI              | Groq API                                   |
| Analytics       | Statistical anomaly & correlation analysis |
| Testing         | Python `unittest`                          |

---

## 📂 Project Structure

```text
CityPulse/
│
├── app.py
├── index.html
├── README.md
├── .env.example
├── .gitignore
│
├── tests/
│   └── test_app.py
│
└── citypulse.db
```

> `citypulse.db` may be generated locally depending on the project configuration.

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/CityPulse.git
cd CityPulse
```

### 2. Create a virtual environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file based on `.env.example`.

```env
GROQ_API_KEY=your_groq_api_key
TOMTOM_API_KEY=your_tomtom_api_key
```

> **Never commit your `.env` file or API keys to GitHub.**

### 5. Run the application

```bash
python app.py
```

Open the local URL shown by the application in your browser.

---

## 🔐 Environment Variables

| Variable         | Purpose                          |
| ---------------- | -------------------------------- |
| `GROQ_API_KEY`   | Enables AI situation briefings   |
| `TOMTOM_API_KEY` | Enables traffic data integration |

The application can use simulated/fallback data where external data is unavailable.

---

## 🧪 Testing

Run the test suite with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The current implementation includes tests covering:

* Score calculation
* AQI normalization
* Dashboard data
* Simulation
* Correlation analysis
* Live observation timestamps
* Client/disconnection handling

---

## 📈 Data Flow

```text
External / Synthetic Data
          ↓
      Data Fetching
          ↓
    Data Normalization
          ↓
    Timestamp + Zone Mapping
          ↓
       SQLite Storage
          ↓
   ┌──────┴─────────┐
   ↓                ↓
Analytics          AI
   ↓                ↓
Index / Anomaly    Situation Brief
Correlation
   ↓                ↓
   └──────┬─────────┘
          ↓
     CityPulse Dashboard
```

---

## 🚀 Innovation & Uniqueness

### 1. Multi-Source Civic Fusion

Instead of displaying isolated datasets, CityPulse combines heterogeneous civic signals into one unified view.

### 2. Explainable Civic Intelligence

The system does not only display numbers; it attempts to explain **what is happening and why it matters**.

### 3. Zone-Level Analysis

Conditions are analyzed at the neighborhood/zone level, enabling localized insights.

### 4. AI-Assisted Interpretation

The AI layer converts structured analytical results into concise, plain-language briefings.

### 5. Anomaly + Correlation Detection

CityPulse looks beyond static dashboards by identifying unusual behavior and relationships between different civic signals.

### 6. Simulation-Driven Demonstration

Built-in scenarios allow the system to demonstrate how civic conditions propagate through the analytics pipeline.

---

## 🎯 Target Users

### 👨‍👩‍👧 Residents

Understand current conditions in their neighborhood.

### 🏛️ Civic Authorities

Identify emerging issues and prioritize attention.

### 🚑 Emergency Responders

Gain a consolidated view of potentially relevant conditions.

### 📰 Journalists

Access a unified view of civic events and trends.

### 🏪 Local Businesses

Understand environmental and mobility conditions affecting their area.

---

## 🔮 Future Scope

* Integration with official Indian civic and environmental datasets
* More real-time public transport feeds
* Advanced ML-based anomaly detection
* Predictive civic-risk modelling
* More cities and geographic regions
* Mobile application
* Role-based dashboards for authorities
* Historical CityPulse replay and trend analysis
* IoT sensor integration
* Advanced geospatial analytics
* Automated civic alert workflows

---

## ⚠️ Data & AI Disclaimer

CityPulse is a **prototype developed for the AmiHacks hackathon**.

Some data may be public, simulated, model-based, cached, or community-reported depending on availability.

The CityPulse Index is an experimental composite metric and should not be interpreted as an official civic-health rating.

Correlation analysis indicates relationships observed in available data and does not establish causation.

AI-generated explanations are grounded in the application's available data but should not replace official emergency, weather, traffic, or government information.

---

## 🏆 Hackathon

### AmiHacks

**Problem Statement:** PS-2
**Title:** CityPulse — The Live Civic Health Dashboard
**Team ID:** T082
**Team:** CodeForge
**Category:** Software
**Theme:** Industry / Open Innovation

---

## 👥 Team CodeForge

**Team T082 — CodeForge**

Built for **AmiHacks** with the goal of making complex civic data easier to understand, connect, and act upon.

---

## 📚 References

* Open-Meteo — Weather & Air Quality APIs
* TomTom Traffic APIs
* OpenStreetMap
* Leaflet
* Groq API
* Central Pollution Control Board (CPCB)
* AmiHacks Problem Statement-2: *CityPulse — The Live Civic Health Dashboard*

---

## ⭐ Vision

> **CityPulse transforms scattered civic signals into one understandable pulse of the city — helping people see what is happening, where it is happening, and why it matters.**

**One Glance. A Safer, Smarter City.** 🏙️

# 🏠 Estate Mind — BO3 Price Estimation & Regional Forecasting Module

BO3 is the intelligent property valuation and regional forecasting module of the Estate Mind platform.

It analyzes Tunisian real-estate data, predicts property prices, builds regional time series, and generates explainable forecasts using SARIMA and Explainable AI techniques.

This module was developed using Python, FastAPI, Machine Learning, Time Series Forecasting, and Explainable AI.

---

# 📌 Main Features

* Smart property price estimation
* Regional time-series forecasting
* SARIMA-based future price prediction
* Historical quotation integration
* Real-estate trend analysis
* Explainable AI predictions
* Regional market comparison
* Interactive visualization dashboards
* REST API integration
* Data preprocessing and fusion

---

# 🧠 Implemented Modules

## Historical Data Preparation

Processes and prepares historical real-estate datasets using:

* scraped property listings
* historical indices
* historical quotations (Historique Cotation)
* temporal aggregation
* regional structuring

Files:

```bash
bo3/data_preparation.py
bo3/cleaning.py
```

---

## Feature Engineering

Generates:

* average regional prices
* temporal indicators
* seasonal variables
* normalized market indicators
* trend-based features

File:

```bash
bo3/features.py
```

---

## SARIMA Forecasting

Builds regional time-series models using SARIMA.

The forecasting engine:

* detects trends
* handles seasonality
* predicts future market evolution
* generates future property price forecasts

Files:

```bash
bo3/sarima_engine.py
bo3/forecasting.py
```

---

## Explainable AI (XAI)

Explains property valuation predictions and forecasting behavior.

File:

```bash
bo3/xai.py
```

---

## FastAPI Backend

Handles:

* prediction routes
* forecasting APIs
* frontend integration
* regional analytics
* JSON responses

File:

```bash
main.py
```

---

## 📌 Overview

EstateMind is an intelligent real estate analytics platform designed to modernize property valuation and market forecasting in Tunisia.

The project combines:

* Machine Learning
* Explainable AI (XAI)
* Time Series Forecasting (SARIMA)
* Regional Real Estate Analytics
* Interactive Web Interfaces

Its main objective is to help users, investors, and agencies make accurate and explainable real estate decisions using data-driven insights.

---

# 🎯 BO3 — Estimate Prices with Confidence

Deliver accurate and explainable property valuations.

### 📍 Objectives

* Predict real estate prices using supervised learning models.
* Integrate temporal and territorial drivers.
* Explain predictions using XAI techniques.
* Detect under-valued and over-valued properties.
* Expose analytics and predictions through APIs and visual dashboards.

---

# 🧠 Main Features

## 🔹 Smart Property Price Estimation

EstateMind predicts property prices based on:

* Region
* Property characteristics
* Historical data
* Market trends
* Temporal indicators

The prediction system uses machine learning techniques combined with cleaned and processed real estate datasets.

---

## 🔹 Regional Time Series Forecasting (SARIMA)

One of the core innovations of EstateMind is the implementation of regional real estate forecasting using SARIMA models.

### 📈 What the system does:

For each Tunisian region:

* Builds a dedicated time series
* Analyzes historical market evolution
* Detects trends and seasonality
* Forecasts future real estate prices

### 🧩 Data Sources Used

The forecasting system combines:

#### ✅ Scraped Real Estate Data

Collected from real estate listings:

* Property prices
* Regions
* Dates
* Property information

#### ✅ Historical Indices

Used to understand the global evolution of the market.

#### ✅ Historical Quotations (Historique Cotation)

Integrated as a mandatory data source to model real market price evolution over time.

---

# 🤖 Why SARIMA?

SARIMA (Seasonal AutoRegressive Integrated Moving Average) was selected because:

* It handles seasonality efficiently
* It models long-term trends
* It captures temporal dependencies
* It is highly effective for real estate market forecasting

### 📊 SARIMA allows EstateMind to:

* Predict future property prices
* Analyze regional market behavior
* Detect cyclical market variations
* Generate reliable forecasts

---

# 🧪 Explainable AI (XAI)

EstateMind integrates Explainable AI techniques to make predictions transparent and understandable.

### 🔍 XAI helps:

* Explain why a property price was predicted
* Identify influential features
* Improve user trust
* Provide interpretable analytics

This transforms the platform from a simple prediction system into a decision-support solution.

---

# 🌍 Regional Intelligence

Unlike traditional stock-market-based forecasting systems, EstateMind focuses on:

✅ Real real-estate market data
✅ Regional analysis
✅ Territorial market behavior
✅ Local price evolution

Each region has its own forecasting pipeline and analytics.

---

# 🖥️ Platform Architecture

## 📂 Backend

Built with Python and FastAPI.

### Main Components:

| Module               | Description                                |
| -------------------- | ------------------------------------------ |
| `price_estimator.py` | Machine learning property valuation engine |
| `sarima_engine.py`   | Regional SARIMA forecasting system         |
| `main.py`            | FastAPI API endpoints                      |

---

## 🎨 Frontend

Modern premium UI inspired by:

* OpenAI
* Stripe
* Vercel
* Notion AI

### Main Interfaces

| Page                   | Description                       |
| ---------------------- | --------------------------------- |
| `estimation.html`      | Property valuation system         |
| `sarima.html`          | Time series forecasting dashboard |
| `recommandations.html` | Recommendations and analytics     |
| `xia.html`             | Explainable AI visualization      |

---

# 📚 Historical Data Preparation

EstateMind includes a dedicated historical data preparation pipeline designed to transform raw real estate information into structured datasets suitable for machine learning and time series forecasting.

The preparation phase integrates multiple heterogeneous data sources in order to build reliable and region-oriented real estate intelligence.

## 🔹 Data Sources

### ✅ Scraped Real Estate Listings

Data collected from real estate platforms includes:

* Property prices
* Property type
* Region and city
* Publication dates
* Property characteristics

These datasets represent the current and historical behavior of the Tunisian real estate market.

---

### ✅ Historical Indices

Historical index datasets are integrated to:

* Analyze market evolution over time
* Detect macro-level market trends
* Support regional forecasting models
* Improve temporal consistency

These indices help contextualize property price variations.

---

### ✅ Historical Quotations (Historique Cotation)

Historical quotation data is considered a core component of the project.

This dataset is used to:

* Track real price evolution through time
* Build accurate time series per region
* Improve forecasting reliability
* Capture historical market dynamics

The historical quotation data is mandatory in the forecasting pipeline.

---

## 🧹 Data Preparation Workflow

### 1️⃣ Data Cleaning

* Remove missing or corrupted values
* Normalize pricing formats
* Standardize region names
* Handle duplicated records

---

### 2️⃣ Temporal Processing

* Convert dates into datetime format
* Sort datasets chronologically
* Extract temporal features:

  * Month
  * Year
  * Seasonal periods

---

### 3️⃣ Regional Structuring

The data is reorganized by region in order to:

* Create independent regional time series
* Compare territorial market evolution
* Analyze regional price behavior

---

### 4️⃣ Data Fusion

The system combines:

* Scraped data
* Historical indices
* Historical quotations

into unified analytical datasets.

---

### 5️⃣ Aggregation

The final dataset structure becomes:

```text
Date | Region | Average_Price
```

This structure is then used for:

* Machine learning
* SARIMA forecasting
* Statistical analysis
* Visualization

---

# 📊 Data Processing Pipeline

The project includes:

## ✅ Data Cleaning

* Missing value handling
* Price normalization
* Region standardization

## ✅ Temporal Transformation

* Datetime conversion
* Chronological sorting
* Time aggregation

## ✅ Data Fusion

Combining:

* Scraped datasets
* Historical indices
* Historical quotations

## ✅ Time Series Construction

Structure:

```text
Date | Region | Average_Price
```

---

# 🔮 Forecasting Workflow

For every region:

1. Data preparation
2. Time series creation
3. SARIMA training
4. Trend analysis
5. Future forecasting
6. Visualization generation

---

# 📡 API Integration

EstateMind exposes predictions and analytics through REST APIs using FastAPI.

This enables:

* Frontend integration
* Real-time predictions
* External platform communication
* Scalable deployment

---

# 🚀 Technologies Used

## Backend

* Python
* FastAPI
* Pandas
* NumPy
* Statsmodels
* Scikit-learn

## Time Series

* SARIMA
* Statistical Forecasting

## Frontend

* HTML5
* CSS3
* JavaScript

## Deployment

* Railway
* Render
* Procfile-based deployment

---

# 📁 Project Structure

```bash
EstateMind/
│
├── backend/
│   ├── api/
│   │   └── main.py
│   ├── core/
│   │   ├── price_estimator.py
│   │   └── sarima_engine.py
│   └── data/
│
├── frontend/
│   ├── estimation.html
│   ├── sarima.html
│   ├── recommandations.html
│   ├── xia.html
│   ├── css/
│   ├── js/
│   └── assets/
│
├── requirements.txt
├── render.yaml
├── railway.json
└── Procfile
```

---

# ⚙️ Installation

## 1️⃣ Clone the repository

```bash
git clone <repository_url>
cd EstateMind
```

---

## 2️⃣ Create virtual environment

```bash
python -m venv venv
```

### Activate environment

#### Windows

```bash
venv\Scripts\activate
```

#### Linux / macOS

```bash
source venv/bin/activate
```

---

## 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4️⃣ Run the backend

```bash
uvicorn backend.api.main:app --reload
```

---

# 🌟 Future Improvements

* Interactive regional dashboards
* Advanced deep learning forecasting
* Real-time market monitoring
* Smart investment recommendations
* Geospatial analytics
* Streamlit integration

---

# 📚 Academic Contribution

EstateMind demonstrates the integration of:

* Artificial Intelligence
* Explainable AI
* Time Series Analysis
* Regional Market Intelligence
* Real Estate Analytics

inside a complete end-to-end intelligent platform.

---

# 👩‍💻 Authors

Developed as part of the EstateMind project.

Special focus on:

* BO3 — Estimate Prices with Confidence
* Regional SARIMA Forecasting
* Explainable AI Analytics

---

# 📄 License

This project is intended for educational, research, and innovation purposes.

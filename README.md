# Estate Mind – Smart Real Estate Decision Platform

## Overview

This project was developed as part of the PI-DS program at Esprit School of Engineering (Academic Year 2025–2026).

Estate Mind is a data-driven platform designed to optimize real estate decisions in Tunisia using Data Engineering, Machine Learning, and AI.

## Features

* Real estate data collection (web scraping)
* Data cleaning and preprocessing
* Price prediction models
* Investment decision support
* Risk and anomaly detection
* Explainable AI (SHAP)

## Tech Stack

### Data Engineering

* Python
* Scrapy / Playwright
* PostgreSQL
* FastAPI

### Data Science

* Scikit-learn
* XGBoost
* LightGBM
* SHAP

## Architecture

The system is based on a multi-agent architecture:

* Collector Agent (data scraping)
* Orchestrator Agent (pipeline management)
* Risk Detection Agent
* Legal Agent

## Contributors

* Manar Zaghouani
* Salma Alaya
* Wissem Bahar
* Yosser Ben mahmoud
* Wissal Bahar
* Nourhen Mraeih

## Academic Context

Developed at Esprit School of Engineering – Tunisia
PI-DS – 4DS5 | 2025–2026

## Getting Started

1. Clone the repository
2. Install dependencies
3. Run the pipeline
4. Launch API

## Acknowledgments

Thanks to Esprit School of Engineering for guidance and support.
## Project Structure

This project is organized into multiple repositories, each responsible for a specific layer of the system:

* 🔗 **Data Pipeline**: https://github.com/manarzh1/Esprit-PI-DS-4DS5-2026-EstateMind-DataPipeline
* 🔗 **Models (ML & DL)**: https://github.com/manarzh1/Esprit-PI-DS-4DS5-2026-EstateMind-Models

### Repository Roles

* **Data Pipeline**
  Responsible for data collection, preprocessing, and storage.
  It includes web scraping, data cleaning, and database integration (PostgreSQL).

* **Models (ML & DL)**
  Contains predictive modeling and experimentation components.
  It includes Machine Learning and Deep Learning models for price prediction, anomaly detection, and explainable AI (XAI).

This modular architecture ensures scalability, maintainability, and clear separation of concerns.



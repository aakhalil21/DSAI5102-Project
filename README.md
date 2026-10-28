# NYC Taxi Demand and Fare Analytics Pipeline

## Project overview

This project implements an end-to-end batch data pipeline for New York City Yellow Taxi trip records published by the New York City Taxi and Limousine Commission.

The pipeline will download monthly Parquet files, preserve the raw data, validate and transform trip records, load analytics-ready tables into a data warehouse, and serve the results through an interactive dashboard.

## Initial scope

- Dataset: NYC Yellow Taxi Trip Records
- Provider: New York City Taxi and Limousine Commission
- Initial period: January to June 2025
- Processing approach: Batch
- Supporting data: NYC Taxi Zone Lookup Table
- Ingestion: Python
- Orchestration: Prefect
- Transformation: dbt
- Analytical warehouse: DuckDB
- Dashboard: Metabase
- Deployment: Docker Compose

## Analytical questions

1. How does taxi demand vary by month, weekday, and hour?
2. Which pickup zones and boroughs generate the highest trip volume and revenue?
3. How do trip distance, duration, fare, and tip amount relate?
4. How do payment methods and congestion fees vary by time and location?

## Current project stage

The project is currently in the data-profiling and feasibility stage.

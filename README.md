# Commerce Pulse — E-Commerce Sales Analytics

By **Dakshesh Gautam**. An analytics portfolio project that takes a historical e-commerce export from data cleaning to an interactive SQL and AI analyst.

**[Open the live app](https://dakshesh-commerce-pulse.streamlit.app/)**

![Sales Pulse dashboard](reports/screenshots_dark/01_sales_pulse.png)

## Explore

- **Query Explorer:** 15 reviewed analyses with category, state, fulfillment, customer type and date filters. Charts, CSV downloads and the executed SQL accompany every result.
- **Ask Gemini:** bounded tool calls combine SQL results with cited project documentation. Unsupported profit, customer retention and causal questions are identified explicitly. Provider quota limits can temporarily interrupt chat; Query Explorer remains available.
- **Metric Guide:** definitions, cleaning decisions and data limitations.
- **Power BI:** four dashboard previews available inside the app.

## Data and methods

The Amazon snapshot covers **31 March–29 June 2022**. The model retains 128,975 source lines, flags six duplicate copies and analyses **128,969 lines across 120,378 orders**. Valued shipped sales are **₹69,660,658**, a sales proxy rather than collected or audited revenue. May/June comparisons use days 1–29 in both months.

Python prepares a MySQL star schema with four dimensions and one fact table. Bound SQL parameters, an allowlisted analysis registry, a SELECT-only database account and read-only sessions constrain database access. Remote connections validate the server certificate and hostname. Document retrieval uses four project documents and a prebuilt 17-passage index; generated prose is checked against numeric evidence and known citation IDs.

This repository contains the web deployment. Raw data, database backups and credentials stay outside GitHub. Dataset attribution: [E-Commerce Sales Dataset on Kaggle](https://www.kaggle.com/datasets/thedevastator/unlock-profits-with-e-commerce-sales-data).

Deployment checks passed: 26 local checks and all 14 baseline analyses on Aiven MySQL 8.4.11, using certificate-verified TLS and a SELECT-only reader. Results are recorded in [reports/deployment-checks.json](reports/deployment-checks.json) and [reports/cloud-database-checks.json](reports/cloud-database-checks.json).

## Run and deploy

Use Python 3.12 or 3.13, `pip install -r requirements.txt`, configure private credentials in `.env`, then run `streamlit run streamlit_app.py`. Cloud setup is documented in [docs/deployment.md](docs/deployment.md). AI chat requires a Gemini API key; the SQL explorer does not.

Do not use a billed Gemini project if you need a strict free-only deployment. The session allowance is not an account-wide spending cap. Free hosting may sleep while inactive.

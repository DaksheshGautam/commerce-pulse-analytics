# Free deployment

1. Publish this directory to the public GitHub repository `DaksheshGautam/commerce-pulse-analytics`.
2. Create **Aiven for MySQL, Free plan**. Do not select a paid trial or enter payment information. The compact private database import contains only the five star tables and two views.
3. Use a verified TLS connection to import into `ecommerce_db`. Create a dedicated SELECT-only reader for the application. Never deploy with the Aiven admin account.
4. On Streamlit Community Cloud, choose this repository, branch `main`, entrypoint `streamlit_app.py`, Python **3.12**. Add root-level Secrets using `secrets.example.toml` as the template. Paste the complete Aiven CA certificate into `MYSQL_SSL_CA_PEM`.
5. Deploy publicly. Verify overview KPIs, a filtered analysis, the Metric Guide and an AI question if a key is configured. Share the resulting `.streamlit.app` URL.

The database password, API key and CA file must not be uploaded to GitHub. Database connections are limited to a two-connection pool per process, with query and network timeouts. Free plans have resource and availability limits; inactive services may sleep.

Official documentation: [Streamlit deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [Aiven free MySQL](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier).

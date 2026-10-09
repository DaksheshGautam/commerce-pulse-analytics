# Free deployment

1. Publish this directory to the public GitHub repository `DaksheshGautam/commerce-pulse-analytics`.
2. Create **Aiven for MySQL, Free plan**. Do not select a paid trial or enter payment information. The compact private database import contains only the five star tables and two views.
3. Use a verified TLS connection to import into `ecommerce_db`. Create a dedicated SELECT-only reader for the application. Never deploy with the Aiven admin account.
4. On Streamlit Community Cloud, choose this repository, branch `main`, entrypoint `streamlit_app.py`, Python **3.12**. Add root-level Secrets using `secrets.example.toml` as the template. Paste the complete Aiven CA certificate into `MYSQL_SSL_CA_PEM`.
5. Deploy publicly. Verify overview KPIs, a filtered analysis, the Metric Guide and an AI question if a key is configured. Share the resulting `.streamlit.app` URL.

The database password, API key and CA file must not be uploaded to GitHub. Database connections are limited to a two-connection pool per process, with query and network timeouts. Free plans have resource and availability limits; inactive services may sleep.

## Groq chat configuration

Create a key in [GroqCloud](https://console.groq.com/keys) on the Free plan. Add `GROQ_API_KEY` privately in Streamlit Secrets and set `AI_PROVIDER = "groq"`. The default `GROQ_MODEL` is `openai/gpt-oss-120b`. Keep `GEMINI_API_KEY` and `GEMINI_EMBEDDING_MODEL` for document retrieval: the existing index uses Gemini embeddings, and Groq chat does not replace those vectors. Gemini is never used as an automatic chat fallback. To deliberately restore Gemini chat, set `AI_PROVIDER = "gemini"`.

Groq receives the question, bounded recent conversation, public project methods and catalog, and aggregate SQL results or retrieved public passages. It receives no database credentials or raw order exports. Tool arguments are validated against the existing reviewed analysis registry, and generated numeric claims and citations are checked before display. Document explanations use strict structured JSON with explicit supporting source IDs for each statement; SQL summaries remain separate. Any further numerical query requested in that JSON is validated by the same registry before execution. Provider retries are disabled so each request is counted against the session allowance.

Check both an aggregate sales question and a document-definition question after saving secrets. A Groq key alone enables analytical chat; document questions additionally need the Gemini embedding key. Keep Query Explorer available when either provider reaches its quota. Official references: [Groq tool calling](https://console.groq.com/docs/tool-use/local-tool-calling), [Groq limits](https://console.groq.com/docs/rate-limits).

Official documentation: [Streamlit deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [Aiven free MySQL](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier).

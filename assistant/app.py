"""E-Commerce Sales Analytics: local chat and audited SQL exploration."""
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import plotly.express as px
import streamlit as st
from assistant.config import ROOT, Settings
from assistant.gemini import AssistantError, AnalyticsAssistant
from assistant.queries import TITLES, QueryService, QuerySpec
from assistant.rag import DocumentRetriever, RetrievalError, SOURCES

st.set_page_config(page_title='E-Commerce Sales Analytics', page_icon='📊', layout='wide', initial_sidebar_state='collapsed')
st.markdown('''<style>
[data-testid="stHeader"] {display:none}
.block-container {padding:1.75rem 3rem 4rem;max-width:1280px}
[data-testid="stElementContainer"]:has(style) {display:none}
[data-testid="stMain"] h1 {font-size:2.5rem;line-height:1.2;letter-spacing:-1.25px;padding:0 0 12px!important}
.st-key-summary_kpis {max-width:1040px;width:100%;margin-inline:auto}
.st-key-summary_kpis [data-testid="stHorizontalBlock"] {gap:1.75rem}
.st-key-summary_kpis [data-testid="stColumn"] {flex:1 1 0;min-width:0}
.st-key-summary_kpis [data-testid="stMetric"] {background:#14243A;border:1px solid #253851;border-radius:12px;padding:20px 24px;text-align:center}
.st-key-summary_kpis [data-testid="stMetricLabel"] {display:flex;justify-content:center;text-align:center}
.st-key-summary_kpis [data-testid="stMetricValue"] {font-size:2.35rem;text-align:center}
.hero-note {color:#A6B7CE;font-size:16px;line-height:1.6;max-width:980px;margin:0 0 8px}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none}
.st-key-analysis_workspace {position:relative}
.st-key-analysis_workspace [data-testid="stElementContainer"]:has(.session-api-counter) {position:absolute;top:9px;right:0;width:auto;z-index:1}
.session-api-counter {color:#A6B7CE;font-size:14px;line-height:24px;white-space:nowrap;text-align:right}
.st-key-analysis_workspace [role="tablist"] {padding-right:225px}
@media (max-width:680px) {
 .block-container {padding:1.25rem 1.25rem 3rem}
 [data-testid="stMain"] h1 {font-size:2rem}
 .st-key-summary_kpis {max-width:360px}
 .st-key-summary_kpis [data-testid="stHorizontalBlock"] {flex-direction:column;gap:1rem}
 .st-key-summary_kpis [data-testid="stColumn"] {width:100%;flex:1 1 auto}
 .st-key-analysis_workspace [data-testid="stElementContainer"]:has(.session-api-counter) {position:relative;top:auto;align-self:flex-end}
 .st-key-analysis_workspace [role="tablist"] {padding-right:0}
}
</style>''', unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def connect(settings):
    return QueryService(settings)


def csv_bytes(frame):
    # Escape text cells that spreadsheet programs could treat as formulas.
    safe = frame.copy()
    for column in safe.columns:
        safe[column] = safe[column].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v)
    return safe.to_csv(index=False).encode('utf-8-sig')


def show_evidence(result, key):
    st.subheader(result['title'])
    chosen = {k: v for k, v in result['filters'].items() if v is not None and k not in {'analysis', 'row_limit'}}
    if 'rank_by' in chosen:
        chosen['ranking metric'] = 'shipped units' if chosen.pop('rank_by') == 'units' else 'shipped sales value'
    st.caption('Filters: ' + (', '.join(f'{k.replace("_", " ")}: {v}' for k, v in chosen.items()) or 'Full snapshot'))
    frame = pd.DataFrame(result['rows'])
    if frame.empty:
        st.info('No matching groups. Broaden your filters.')
    else:
        x = next((c for c in ['order_date', 'month_key', 'sku', 'category', 'ship_state', 'fulfillment', 'status', 'is_b2b', 'has_promotion'] if c in frame), None)
        y = next((c for c in ['value_change', 'shipped_value', 'recorded_value'] if c in frame), None)
        if result['analysis'] == 'sku_performance' and result['filters'].get('rank_by') == 'units':
            y = 'units'
        if result['analysis'] == 'status_distribution':
            y = 'line_count'
        y_label = ('Order lines' if y == 'line_count' else 'Shipped units' if y == 'units'
                   else (y.replace('_',' ').title() + ' (INR)' if y else ''))
        if x and y and len(frame) > 1:
            if x in ('order_date', 'month_key'):
                chart = px.line(frame, x=x, y=y, markers=True, color_discrete_sequence=['#3DE2C4'], labels={x:x.replace('_',' ').title(), y:y_label})
            else:
                plotted = frame.head(20).copy()
                plotted[x] = plotted[x].astype(str)
                hover = (['category', 'sales_rank', 'units', 'shipped_value'] if result['analysis'] == 'sku_performance'
                         else ['category', 'category_rank', 'line_count'] if x == 'sku' else None)
                chart = px.bar(plotted, x=y, y=x, orientation='h', color_discrete_sequence=['#3DE2C4'], hover_data=hover, labels={x:'SKU' if x == 'sku' else x.replace('_',' ').title(), y:y_label})
                chart.update_yaxes(autorange='reversed')
            chart.update_layout(height=max(350, len(plotted)*28+80) if x == 'sku' else 350, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor='#0B1322', plot_bgcolor='#0B1322', font_color='#F3F7FC')
            if x == 'month_key':
                chart.update_xaxes(type='category', title='Reporting month')
            st.plotly_chart(chart, width='stretch', key=key + '_chart')
            if x == 'sku':
                st.caption('Each bar shows one SKU under the selected filters. ' +
                    ('SKUs are ranked across all matching categories; no minimum line-count cutoff applies.' if result['analysis'] == 'sku_performance'
                     else 'These ranked SKUs are a subset of each category, not its full category total.') + ' Hover for category and rank.')
            if len(frame) > 20 and x not in ('order_date', 'month_key'):
                st.caption('Chart shows the first 20 returned groups. The table contains all returned rows.')
        st.dataframe(frame, hide_index=True, width='stretch')
        st.download_button('Download result CSV', csv_bytes(frame), result['analysis'] + '.csv', 'text/csv', key=key + '_csv')
    with st.expander('SQL evidence and metric notes'):
        for note in result['notes']:
            st.write('• ' + note)
        st.code(result['sql'], language='sql')
        st.json(result['parameters'])
        if 'summary' in result:
            st.write('Full filtered status summary (independent of the displayed row limit):')
            st.json(result['summary'])
            st.code(result['summary_sql'], language='sql')
            st.json(result['summary_parameters'])
        st.caption(f"Query time: {result['query_ms']:,.0f} ms · bound parameters · read-only transaction")


def show_sources(sources):
    if not sources:
        return
    st.markdown('**Project source passages**')
    st.caption('Project-authored documentation. Open a passage to inspect the evidence behind the explanation.')
    for source in sources:
        section = f" · {source['section']}" if source['section'] != source['title'] else ''
        with st.expander(f"[{source['citation']}] {source['title']}{section}"):
            st.caption(f"{source['source']} · lines {source['start_line']}–{source['end_line']}")
            st.markdown(source['text'])


try:
    settings = Settings.load()
    with st.spinner('Connecting to the sales database…'):
        service = connect(settings)
except Exception:
    st.title('E-Commerce Sales Analytics')
    st.error('The sales database is temporarily unavailable. Please try again shortly. The owner can check the database service and Streamlit Secrets.')
    st.stop()

st.session_state.setdefault('messages', [])
st.session_state.setdefault('api_calls', 0)

st.title('E-Commerce Sales Analytics')
st.markdown('<p class="hero-note">Explore sales and the methods behind the figures—with SQL evidence and cited project documents.</p>', unsafe_allow_html=True)
overview = service.execute(QuerySpec(analysis='overview'))['rows'][0]
with st.container(key='summary_kpis'):
    columns = st.columns(3)
    for col, label, value in zip(columns,
        ['Valued shipped sales', 'Valued orders', 'Cancelled lines'],
        [f"₹{overview['shipped_sales_value']/1e7:.2f} cr", f"{overview['valued_shipped_orders']:,}", f"{overview['cancelled_line_pct']:.2f}%"]):
        col.metric(label, value)
st.caption('Full snapshot KPIs · shipped value is a sales proxy · cancellation is a line rate')
with st.container(key='analysis_workspace'):
    api_counter = st.empty()
    chat, explorer, guide = st.tabs([f'Ask {settings.provider_label}', 'Query Explorer', 'Metric Guide'])


def update_usage_counter():
    api_counter.markdown(
        f'<div class="session-api-counter" aria-live="polite" title="This browser session allowance is separate from provider quotas and pricing.">Session API calls: {st.session_state.api_calls}/{settings.max_requests}</div>',
        unsafe_allow_html=True)


update_usage_counter()
with chat:
    if not settings.chat_ready:
        st.info('AI chat is currently unavailable. Query Explorer provides the same reviewed SQL analyses without an API key.')
    st.caption('Try: “Compare May and June on the same days”, “How were duplicates handled?”, or “Show Kurta sales in Maharashtra and explain how sales are defined.”')
    for index, answer in enumerate(st.session_state.messages):
        with st.chat_message('user'):
            st.write(answer.question)
        with st.chat_message('assistant'):
            st.write(answer.text)
            for number, result in enumerate(answer.evidence):
                show_evidence(result, f'chat_{index}_{number}')
            show_sources(getattr(answer, 'sources', []))
            retrieval_calls = getattr(answer, 'retrieval_calls', 0)
            searches = 'document search' if retrieval_calls == 1 else 'document searches'
            st.caption(f'{answer.api_calls} API requests ({retrieval_calls} {searches}) · {answer.input_tokens:,} input / {answer.output_tokens:,} output LLM tokens')
    question = st.chat_input('Ask about this sales snapshot…', max_chars=2000,
        disabled=not settings.chat_ready or st.session_state.api_calls >= settings.max_requests)
    if question:
        with st.chat_message('user'):
            st.write(question)
        try:
            with st.spinner('Checking SQL evidence and relevant project documents…'):
                answer = AnalyticsAssistant(settings, service).ask(question,
                    [item.context() for item in st.session_state.messages],
                    request_budget=settings.max_requests - st.session_state.api_calls)
            st.session_state.api_calls += answer.api_calls
            st.session_state.messages.append(answer)
            st.session_state.messages = st.session_state.messages[-12:]
            st.rerun()
        except AssistantError as error:
            st.session_state.api_calls += error.api_calls
            update_usage_counter()
            st.error(str(error))

with explorer:
    st.subheader('Explore the reviewed analyses')
    st.caption('Run the same SQL tools directly, with explicit filters and no AI requests.')
    with st.form('explorer'):
        analysis = st.selectbox('Analysis', list(TITLES), format_func=TITLES.get)
        a, b, c = st.columns(3)
        category = a.selectbox('Category', ['All'] + service.catalog['categories'])
        state = b.selectbox('Shipping state', ['All'] + service.catalog['states'])
        fulfillment = c.selectbox('Fulfillment', ['All', 'Amazon', 'Merchant'])
        a, b, c = st.columns(3)
        customer_type = a.selectbox('Customer type', ['All', 'Retail', 'Business (B2B)'])
        dates = b.date_input('Source date range', (date(2022, 3, 31), date(2022, 6, 29)), min_value=date(2022, 3, 31), max_value=date(2022, 6, 29))
        limit = c.number_input('Maximum returned rows', min_value=1, max_value=200, value=10, step=1)
        ranking_metric = st.selectbox('SKU ranking metric', ['shipped_value', 'units'],
            format_func=lambda value: 'Shipped sales value (INR)' if value == 'shipped_value' else 'Shipped units',
            help='Applies to Top-selling SKUs overall. Other analyses use their defined metrics.')
        st.caption('Overall SKU ranking has no minimum line count and uses the selected sales metric. Within-category SKU ranking retains the original ≥30-line and rank ≤5 rules. May/June comparison tools use days 1–29; other filters still apply.')
        run = st.form_submit_button('Run analysis', type='primary')
    if run:
        try:
            if len(dates) != 2:
                raise ValueError('Choose both a start and end date.')
            selected = dict(analysis=analysis, row_limit=int(limit), start_date=dates[0], end_date=dates[1])
            if analysis == 'sku_performance':
                selected['rank_by'] = ranking_metric
            selected.update({k: None if v == 'All' else v for k, v in dict(category=category, state=state, fulfillment=fulfillment, customer_type=customer_type).items()})
            st.session_state.explorer_result = service.execute(QuerySpec(**selected))
        except ValueError:
            st.error('Check the selected filters and choose a complete date range.')
        except Exception:
            st.error('The analysis could not complete. Please try again shortly.')
    if 'explorer_result' in st.session_state:
        show_evidence(st.session_state.explorer_result, 'explorer_result')

with guide:
    st.subheader('How answers are grounded')
    st.write('MySQL calculates figures. Document retrieval finds relevant definitions, cleaning decisions and dataset notes. The AI assistant combines the evidence into an explanation with source citations.')
    try:
        knowledge = DocumentRetriever(settings)
        st.caption(f'Knowledge base ready · {len(SOURCES)} project documents · {len(knowledge.chunks)} searchable passages')
    except RetrievalError as error:
        st.info(str(error))
    with st.expander('Documents in the knowledge base'):
        for source in SOURCES:
            st.write(source)
        st.caption('These describe this project. They are not official Amazon operating policies.')
    st.divider()
    st.markdown((ROOT / 'docs/metric_contract.md').read_text(encoding='utf-8'))
    st.divider()
    st.write('Numeric and citation checks reject unsupported numbers and unknown source IDs. They do not guarantee that every interpretation is correct. Inspect the SQL evidence and source passages for decisions. Embedding requests count toward the session allowance; one-time index builds run separately.')


with st.expander('About this project · Power BI dashboard'):
    st.write('Commerce Pulse by Dakshesh Gautam. A portfolio project connecting Python data preparation, a MySQL star schema, reviewed SQL analyses, Power BI and an AI assistant with cited project documentation.')
    st.write('The dataset is a historical sales snapshot from 2022. Figures describe the exported data; they are not live Amazon sales or audited accounting revenue.')
    st.link_button('View code on GitHub', 'https://github.com/DaksheshGautam/commerce-pulse-analytics')
    for name, caption in [('01_sales_pulse', 'Sales Pulse'), ('02_product_drivers', 'Product Drivers'),
                          ('03_market_demand', 'Market Demand'), ('04_operations', 'Operations')]:
        st.image(str(ROOT / 'reports/screenshots_dark' / (name + '.png')), caption=caption, width='stretch')

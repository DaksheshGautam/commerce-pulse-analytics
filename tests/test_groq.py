"""Exercise the real SDK with a fake HTTP transport, without paid requests."""
from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
import pytest
from groq import Groq

from assistant.config import Settings
from assistant.gemini import AnalyticsAssistant, AssistantError
from assistant.providers import GroqInteractions
from assistant.rag import DocumentRetriever, RetrievalError


SETTINGS = Settings(host='127.0.0.1', port=3306, database='test', user='reader',
    password='unused', provider='groq', groq_api_key='test-private-key')


class Service:
    catalog = {'states': ['MAHARASHTRA', 'TELANGANA'], 'categories': ['Kurta']}

    def __init__(self):
        self.specs = []

    def execute(self, spec):
        self.specs.append(spec)
        return {'analysis': spec.analysis, 'title': 'Sales overview',
            'filters': spec.model_dump(mode='json'), 'rows': [{
                'analytical_lines': 100, 'shipped_sales_value': 200,
                'valued_shipped_orders': 10, 'cancelled_line_pct': 2}],
            'sql': 'SELECT private_sql', 'parameters': {}, 'query_ms': 1}


def tool_call(name, args, id='call_1'):
    return {'id': id, 'type': 'function', 'function': {
        'name': name, 'arguments': args if isinstance(args, str) else json.dumps(args)}}


def client_with(responses, requests):
    def handle(request):
        requests.append(json.loads(request.content))
        response = responses.pop(0)
        if isinstance(response, int):
            return httpx.Response(response, json={'error': {'message':
                'private upstream details and key must not appear', 'type': 'api_error'}})
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion',
            'created': 1, 'model': SETTINGS.groq_model,
            'choices': [{'index': 0, 'message': {'role': 'assistant', **response},
                'finish_reason': 'tool_calls' if response.get('tool_calls') else 'stop'}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}})
    sdk = Groq(api_key=SETTINGS.groq_api_key, max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    return SimpleNamespace(interactions=GroqInteractions(sdk))


def test_sql_tool_roundtrip_uses_real_groq_sdk_and_preserves_filters():
    requests, service = [], Service()
    client = client_with([
        {'tool_calls': [tool_call('query_analysis', {'analysis': 'overview', 'state': 'MAHARASHTRA'})]},
        {'content': 'Valued shipped sales are INR 200 across 10 orders.'}], requests)
    answer = AnalyticsAssistant(SETTINGS, service, client=client).ask('Show shipped sales in Maharashtra')
    assert answer.kind == 'analysis' and answer.api_calls == 2
    assert answer.input_tokens == 200 and answer.output_tokens == 40
    assert service.specs[0].state == 'MAHARASHTRA'
    assert requests[0]['model'] == 'openai/gpt-oss-120b'
    assert requests[0]['include_reasoning'] is False
    assert requests[0]['tools'][0]['function']['name'] == 'query_analysis'
    assert requests[1]['messages'][-1]['role'] == 'tool'
    assert requests[1]['messages'][-1]['tool_call_id'] == 'call_1'
    assert 'private_sql' not in requests[1]['messages'][-1]['content']


@pytest.mark.parametrize('bad_args', ['{broken json', {'analysis': 'DROP TABLE orders'},
    {'analysis': 'overview', 'start_date': '2025-01-01'}])
def test_invalid_tools_never_execute_a_database_query(bad_args):
    requests, service = [], Service()
    client = client_with([{'tool_calls': [tool_call('query_analysis', bad_args)]},
        {'content': 'No verified result.'}], requests)
    answer = AnalyticsAssistant(SETTINGS, service, client=client).ask('Show shipped sales')
    assert not service.specs and not answer.evidence
    assert 'Invalid analysis' in requests[1]['messages'][-1]['content']


def test_numeric_hallucinations_fall_back_to_verified_sql():
    requests = []
    client = client_with([{'tool_calls': [tool_call('query_analysis', {'analysis': 'overview'})]},
        {'content': 'Sales are INR 999999.'}], requests)
    answer = AnalyticsAssistant(SETTINGS, Service(), client=client).ask('Show shipped sales')
    assert '999999' not in answer.text and '200.00' in answer.text


@pytest.mark.parametrize('status', [429, 401, 403, 503])
def test_provider_failures_do_not_retry_or_expose_private_details(status):
    requests = []
    client = client_with([status], requests)
    with pytest.raises(AssistantError) as result:
        AnalyticsAssistant(SETTINGS, Service(), client=client).ask('Show shipped sales')
    assert len(requests) == 1 and result.value.api_calls == 1
    assert 'Groq' in str(result.value)
    assert 'private upstream' not in str(result.value) and SETTINGS.groq_api_key not in str(result.value)


def test_request_budget_stops_before_second_provider_call():
    requests = []
    client = client_with([{'tool_calls': [tool_call('query_analysis', {'analysis': 'overview'})]}], requests)
    answer = AnalyticsAssistant(SETTINGS, Service(), client=client).ask('Show shipped sales', request_budget=1)
    assert len(requests) == answer.api_calls == 1
    assert answer.evidence and '200.00' in answer.text


def test_document_search_keeps_embedding_client_separate(monkeypatch):
    requests, embedding_clients = [], []
    sources = [{'citation': 'D1', 'source': 'docs/metric_contract.md',
        'text': 'Shipped sales are a sales proxy.'}]

    class Retriever:
        def __init__(self, settings, client=None):
            embedding_clients.append(client)

        def search(self, query):
            return sources

    monkeypatch.setattr('assistant.gemini.DocumentRetriever', Retriever)
    client = client_with([{'tool_calls': [tool_call('search_documents', {'query': 'shipped sales definition'})]},
        {'content': 'Shipped sales are a sales proxy [D1].'}], requests)
    answer = AnalyticsAssistant(SETTINGS, Service(), client=client).ask('Define shipped sales')
    assert embedding_clients == [None]
    assert answer.kind == 'documentation' and answer.sources == sources
    assert answer.api_calls == 3 and answer.retrieval_calls == 1


def test_groq_chat_does_not_require_gemini_key_and_hides_key_in_repr():
    assert SETTINGS.chat_ready and not SETTINGS.gemini_ready
    assert SETTINGS.groq_api_key not in repr(SETTINGS)
    assert not replace(SETTINGS, groq_api_key='').chat_ready
    assert not replace(SETTINGS, provider='invalid').chat_ready


def test_missing_embedding_key_leaves_an_actionable_document_error():
    with pytest.raises(RetrievalError, match='GEMINI_API_KEY'):
        DocumentRetriever(SETTINGS).search('Define shipped sales')


def test_environment_configuration_selects_groq(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'test-private-env-key')
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    settings = Settings.load()
    assert settings.provider == 'groq' and settings.chat_ready
    assert settings.chat_model == 'openai/gpt-oss-120b'
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    assert Settings.load().provider == 'gemini'

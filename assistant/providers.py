"""Translate provider messages while keeping the reviewed tool loop shared."""
from dataclasses import dataclass
import json
from types import SimpleNamespace
from .queries import QuerySpec


@dataclass
class Step:
    type: str
    id: str = ''
    name: str = ''
    arguments: object = None
    text: str = ''

    def model_dump(self, mode='json'):
        return vars(self).copy()


def groq_messages(history, instruction):
    messages = [{'role': 'system', 'content': instruction}]
    for step in history:
        kind = step['type']
        if kind == 'user_input':
            messages.append({'role': 'user', 'content': '\n'.join(
                part.get('text', '') for part in step['content'])})
        elif kind == 'function_call':
            call = {'id': step['id'], 'type': 'function', 'function': {
                'name': step['name'], 'arguments': json.dumps(step['arguments'])}}
            if messages[-1]['role'] == 'assistant' and 'tool_calls' in messages[-1]:
                messages[-1]['tool_calls'].append(call)
            else:
                messages.append({'role': 'assistant', 'content': None, 'tool_calls': [call]})
        elif kind == 'function_result':
            messages.append({'role': 'tool', 'tool_call_id': step['call_id'],
                'content': '\n'.join(part.get('text', '') for part in step['result'])})
        elif kind == 'text':
            messages.append({'role': 'assistant', 'content': step['text']})
        else:
            raise ValueError('Unsupported provider message.')
    return messages


class GroqInteractions:
    def __init__(self, client):
        self.client = client

    def create(self, *, model, input, system_instruction, tools, source_ids=None, **kwargs):
        messages = groq_messages(input, system_instruction)
        options = dict(model=model, messages=messages, temperature=0,
            reasoning_effort='low', include_reasoning=False, max_completion_tokens=2048)
        if source_ids:
            # Groq Structured Outputs cannot be combined with tool use. Further
            # query requests are encoded in JSON and validated in the tool loop.
            query_schema = QuerySpec.model_json_schema()
            query_schema['required'] = list(query_schema['properties'])
            for field in query_schema['properties'].values():
                field.pop('default', None)
            statement_schema = {'type': 'object', 'additionalProperties': False,
                'required': ['text', 'citations'], 'properties': {
                    'text': {'type': 'string'},
                    'citations': {'type': 'array', 'items': {'type': 'string', 'enum': source_ids}}}}
            schema = {'type': 'object', 'additionalProperties': False,
                'required': ['analyses', 'sql_summary', 'statements'], 'properties': {
                    'analyses': {'type': 'array', 'items': query_schema},
                    'sql_summary': {'type': 'string'},
                    'statements': {'type': 'array', 'items': statement_schema}}}
            messages.append({'role': 'user', 'content':
                'Return JSON matching the response schema. If the original question still needs '
                'numerical evidence, request reviewed queries in analyses, leave sql_summary '
                'empty and statements empty. Otherwise analyses must be empty; provide '
                'verified figures in sql_summary and document explanations in statements. '
                'Every explanation statement needs at least one supporting citation ID. '
                'Use no financial totals in explanations unless verified by SQL. '
                'This JSON replaces the compose_answer tool; do not emit a tool call.'})
            options['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'sourced_answer', 'strict': True, 'schema': schema}}
        else:
            options.update(tools=[{'type': 'function', 'function': {key: tool[key]
                for key in ('name', 'description', 'parameters')}} for tool in tools],
                tool_choice='auto', parallel_tool_calls=False)
        response = self.client.chat.completions.create(**options)
        if not response.choices:
            raise ValueError('The provider returned no answer.')
        message = response.choices[0].message
        steps = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments)
            except (ValueError, TypeError):
                arguments = {'__invalid_tool_arguments__': True}
            steps.append(Step('function_call', id=call.id,
                name=call.function.name, arguments=arguments))
        text = message.content or ''
        if source_ids:
            payload = json.loads(text)
            if not isinstance(payload, dict) or not isinstance(payload.get('analyses'), list):
                raise ValueError('Invalid structured answer.')
            if payload['analyses']:
                steps = [Step('function_call', id=f'structured_query_{index}',
                    name='query_analysis', arguments=arguments)
                    for index, arguments in enumerate(payload['analyses'])]
            else:
                steps = [Step('function_call', id='structured_answer', name='compose_answer',
                    arguments={key: payload[key] for key in ('sql_summary', 'statements')})]
            text = ''
        if not steps and text:
            steps.append(Step('text', text=text))
        usage = response.usage
        return SimpleNamespace(steps=steps, output_text=text, usage=SimpleNamespace(
            total_input_tokens=getattr(usage, 'prompt_tokens', 0) or 0,
            total_output_tokens=getattr(usage, 'completion_tokens', 0) or 0))


def make_chat_client(settings):
    if settings.provider == 'groq':
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key, timeout=90, max_retries=0)
        return SimpleNamespace(interactions=GroqInteractions(client))
    from google import genai
    from google.genai import types
    return genai.Client(api_key=settings.api_key,
        http_options=types.HttpOptions(timeout=90000,
            retry_options=types.HttpRetryOptions(attempts=1)))

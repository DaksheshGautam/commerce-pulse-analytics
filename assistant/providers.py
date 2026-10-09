"""Translate provider messages while keeping the reviewed tool loop shared."""
from dataclasses import dataclass
import json
from types import SimpleNamespace


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

    def create(self, *, model, input, system_instruction, tools, require_tool=False, **kwargs):
        response = self.client.chat.completions.create(
            model=model, messages=groq_messages(input, system_instruction),
            tools=[{'type': 'function', 'function': {key: tool[key]
                for key in ('name', 'description', 'parameters')}} for tool in tools],
            tool_choice='required' if require_tool else 'auto', parallel_tool_calls=False,
            temperature=0, reasoning_effort='low', include_reasoning=False,
            max_completion_tokens=2048)
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

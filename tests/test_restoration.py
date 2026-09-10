import asyncio
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

from kiloframe.agent import Agent
from kiloframe.config import Settings
from kiloframe.memory import MemoryStore
from kiloframe.prompt import CORE_DIRECTIVE
from kiloframe.profiles import PROFILES
from kiloframe.security import PermissionManager
from kiloframe.tools import ToolRegistry
from kiloframe.providers import Provider, ProviderRegistry, ProviderError, KNOWN_PROVIDERS
from kiloframe.provider_protocol import anthropic_payload, consolidated_system_messages
from kiloframe.tui_full import KiloApp, _ChatLexer, _COMMANDS
from prompt_toolkit.document import Document
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
from prompt_toolkit.data_structures import Point


class ScriptRuntime:
    def __init__(self, steps):
        self.steps = iter(steps)
        self.payloads = []

    def active_model(self):
        return 'test-model'

    async def ensure_ready(self):
        pass

    async def chat_stream(self, payload):
        self.payloads.append(json.loads(json.dumps(payload)))
        step = next(self.steps, 'The operation failed; the task is incomplete.')
        if isinstance(step, tuple):
            name, args = step
            yield {'delta': {'tool_calls': [{'index': 0, 'id': f'call-{len(self.payloads)}',
                'function': {'name': name, 'arguments': json.dumps(args)}}]}}
        else:
            yield {'delta': {'content': step}, 'finish_reason': 'stop'}


class RestorationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cloud_protocol_consolidates_every_directive_in_order(self):
        messages = [
            {"role": "system", "content": CORE_DIRECTIVE},
            {"role": "system", "content": "Telegram behavior"},
            {"role": "user", "content": "act"},
            {"role": "system", "content": "finish the task"},
        ]
        normalized = consolidated_system_messages(messages)
        self.assertEqual([item["role"] for item in normalized], ["system", "user"])
        self.assertTrue(normalized[0]["content"].startswith(CORE_DIRECTIVE))
        self.assertTrue(normalized[0]["content"].endswith("finish the task"))

    async def test_real_command_failure_recovery_write_read_and_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(home=root, data_dir=root, config_dir=root, runtime_dir=root, log_dir=root)
            memory = MemoryStore(root / 'memory.db')
            tools = ToolRegistry(settings, memory, PermissionManager(root / 'policy.json'))
            runtime = ScriptRuntime([
                ('run_command', {'command': 'ls missing-file'}),
                ('run_command', {'command': 'pwd'}),
                ('write_file', {'path': 'result.txt', 'content': 'first'}),
                ('read_file', {'path': 'result.txt'}),
                ('write_file', {'path': 'result.txt', 'content': 'verified'}),
                ('read_file', {'path': 'result.txt'}),
                'Created and verified the requested file.',
            ])
            async def approve(*args):
                return True
            events = [e async for e in Agent(settings, runtime, memory, tools).run(
                'Create result.txt and verify it.', cwd=Path('/outside-workspace'), permission_callback=approve)]
            results = [e for e in events if e['type'] == 'tool_end']
            self.assertEqual([e['ok'] for e in results], [False, True, True, True, True, True])
            self.assertEqual((root / 'result.txt').read_text(), 'verified')
            self.assertIn(str(root), results[1]['summary'])
            self.assertTrue(all(p['messages'][0]['content'].startswith(CORE_DIRECTIVE) for p in runtime.payloads))
            answer = ''.join(e.get('text', '') for e in events if e['type'] == 'token')
            self.assertTrue(answer.startswith('Sir'))
            self.assertTrue(answer.endswith('Sir.'))
            memory.close()

    async def test_failed_action_cannot_be_recorded_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(home=root, data_dir=root, config_dir=root, runtime_dir=root, log_dir=root)
            memory = MemoryStore(root / 'memory.db')
            tools = ToolRegistry(settings, memory, PermissionManager(root / 'policy.json'))
            runtime = ScriptRuntime([('run_command', {'command': 'ls nonexistent'}), 'Done.', 'Done.', 'Done.'])
            events = [e async for e in Agent(settings, runtime, memory, tools).run('Inspect nonexistent')]
            self.assertTrue(events[-1]['task_failed'])
            self.assertIn('not verified', memory.history(events[-1]['session_id'])[-1]['content'])
            memory.close()

    async def test_all_specialists_keep_the_same_directive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(home=root, data_dir=root, config_dir=root, runtime_dir=root, log_dir=root, max_agent_steps=1)
            memory = MemoryStore(root / 'memory.db')
            tools = ToolRegistry(settings, memory, PermissionManager(root / 'policy.json'))
            for name in PROFILES:
                with self.subTest(profile=name):
                    runtime = ScriptRuntime(['Ready.'])
                    events = [e async for e in Agent(settings, runtime, memory, tools).run('Hello', agent_profile=name)]
                    self.assertTrue(runtime.payloads[0]['messages'][0]['content'].startswith(CORE_DIRECTIVE))
                    tokens = ''.join(e.get('text', '') for e in events if e['type'] == 'token')
                    self.assertTrue(tokens.startswith('Sir'))
                    self.assertTrue(tokens.endswith('Sir.'))
            memory.close()

    async def test_slash_unknown_blank_cancel_and_selectable_configuration(self):
        app = KiloApp(SimpleNamespace(request=AsyncMock()))
        app.app = SimpleNamespace(invalidate=lambda: None)
        app._enqueue = lambda *args, **kwargs: self.fail('command leaked into model chat')
        app._accept(SimpleNamespace(text='/modelXYZ'))
        self.assertIn('unknown command', app.output.text)
        app._handle_command('/agent')
        self.assertEqual(app._pending['kind'], 'command')
        await app._resume_pending('/agent coding')
        self.assertEqual(app.forced_profile, 'coding')
        app._pending = {'kind': 'cloud_key'}
        app._accept(SimpleNamespace(text=''))
        self.assertIsNone(app._pending)
        names = [name.strip() for name, _ in _COMMANDS]
        self.assertEqual(len(names), len(set(names)))

    async def test_scrollbar_click_moves_content_and_output_does_not_snap_back(self):
        app = KiloApp(SimpleNamespace())
        app._append('\n'.join(f'line {i}' for i in range(500)))
        app._scroll_to(499)
        click = app._scrollbar_text()[0][2]
        click(MouseEvent(Point(x=0, y=1), MouseEventType.MOUSE_DOWN, MouseButton.LEFT, frozenset()))
        self.assertEqual(app.output.buffer.document.cursor_position_row, 0)
        app._append('\nnew output')
        self.assertEqual(app.output.buffer.document.cursor_position_row, 0)
        click(MouseEvent(Point(x=0, y=7), MouseEventType.MOUSE_DOWN, MouseButton.LEFT, frozenset()))
        self.assertGreater(app.output.buffer.document.cursor_position_row, 300)

    def test_large_history_highlighting_does_not_rescan_on_input_redraw(self):
        lexer = _ChatLexer()
        document = Document('plain output\n' * 10000)
        get_line = lexer.lex_document(document)
        start = time.monotonic()
        for _ in range(10):
            for i in range(9960, 10000):
                get_line(i)
            self.assertIs(lexer.lex_document(document), get_line)
        self.assertLess(time.monotonic() - start, 0.1)


class ProviderRestorationTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_catalog_entry_sends_correct_auth_endpoint_and_tools(self):
        schema = [{'type': 'function', 'function': {'name': 'system_info', 'description': 'inspect',
                  'parameters': {'type': 'object', 'properties': {}}}}]
        for name, meta in KNOWN_PROVIDERS.items():
            with self.subTest(provider=name):
                provider = Provider(name, meta['base_url'].replace('{account_id}', 'test-account'), 'fixture-secret', meta['model'] or 'catalogue-model')
                requests = []
                def open_url(request, timeout):
                    requests.append(request)
                    if name == 'anthropic':
                        return io.BytesIO(b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"ok"}}\n\ndata: {"type":"message_stop"}\n\n')
                    return io.BytesIO(b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
                with patch('urllib.request.urlopen', side_effect=open_url):
                    result = [e async for e in ProviderRegistry(Path('/unused')).stream(provider, [{'role': 'system', 'content': CORE_DIRECTIVE}, {'role': 'user', 'content': 'hello'}], 200, schema)]
                request = requests[0]
                headers = {k.lower(): v for k, v in request.header_items()}
                self.assertEqual(headers.get('x-api-key' if name == 'anthropic' else 'authorization'), 'fixture-secret' if name == 'anthropic' else 'Bearer fixture-secret')
                self.assertTrue(request.full_url.endswith('/messages' if name == 'anthropic' else '/chat/completions'))
                payload = json.loads(request.data)
                self.assertIn('tools', payload)
                self.assertTrue(result)

    async def test_truncated_and_error_streams_raise(self):
        provider = Provider('custom', 'https://example.com/v1', 'secret', 'test')
        for data in [b'data: {"choices":[{"delta":{"content":"partial"}}]}\n', b'data: {"error":{"message":"quota"}}\n']:
            with self.subTest(data=data), patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
                with self.assertRaises(ProviderError):
                    _ = [e async for e in ProviderRegistry(Path('/unused')).stream(provider, [], 200)]

    def test_anthropic_parallel_results_follow_tool_uses(self):
        messages = [{'role': 'system', 'content': CORE_DIRECTIVE}, {'role': 'user', 'content': 'inspect'},
                    {'role': 'assistant', 'content': None, 'tool_calls': [
                        {'id': str(i), 'function': {'name': 'run_command', 'arguments': '{"command":"pwd"}'}} for i in range(2)]},
                    *[{'role': 'tool', 'tool_call_id': str(i), 'content': '{"exit_code":1}'} for i in range(2)]]
        result = anthropic_payload({'model': 'model', 'messages': messages, 'max_tokens': 200})
        self.assertEqual(result['system'], CORE_DIRECTIVE)
        self.assertEqual(len(result['messages'][-1]['content']), 2)
        self.assertTrue(result['messages'][-1]['content'][0]['is_error'])


if __name__ == '__main__':
    unittest.main()

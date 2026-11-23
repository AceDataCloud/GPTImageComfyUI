"""Actual node defaults and saved widgets through the request boundary, without network."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from test_package import Client, client_module, nodes

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / 'contracts/images.json').read_text())
FIELDS = {
    'edit': ['parameters_json', 'model', 'image_urls', 'prompt', 'count', 'background',
             'input_fidelity', 'output_format', 'output_compression', 'quality', 'size', 'callback_url'],
    'generate': ['parameters_json', 'model', 'prompt', 'background', 'moderation', 'count',
                 'output_compression', 'output_format', 'partial_images', 'size', 'quality',
                 'style', 'callback_url'],
}


def node_class(operation):
    return next(cls for cls in nodes.NODE_CLASS_MAPPINGS.values()
                if getattr(cls, 'TOOL', '') == 'gpt_image_' + operation + '_image')


class ImageContractTests(unittest.TestCase):
    def defaults(self, operation):
        required = node_class(operation).INPUT_TYPES()['required']
        self.assertEqual(list(required), FIELDS[operation])
        self.assertEqual(required['quality'], ('STRING', {'multiline': False, 'default': ''}))
        self.assertEqual(required['size'], ('STRING', {'multiline': False, 'default': ''}))
        self.assertEqual(required['model'][0][0], nodes.SENTINEL)
        return {key: value[1]['default'] for key, value in required.items()}

    def post(self, operation, values):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = {'task_id': 'offline-task'}
        response.__enter__.return_value = response
        with patch.object(nodes, '_credential', return_value='offline-placeholder'):
            with patch.object(client_module.requests, 'request', return_value=response) as request:
                result = node_class(operation)().run(**values)
        request.assert_called_once()
        self.assertEqual(request.call_args.args, ('POST', 'https://api.acedata.cloud' + CONTRACT[operation]['path']))
        self.assertEqual(result['result'][1], 'offline-task')
        return request.call_args.kwargs['json']

    def test_generated_contract_and_registered_choices(self):
        subprocess.run([sys.executable, 'scripts/sync_image_contracts.py', '--check'], cwd=ROOT, check=True)
        for operation, contract in CONTRACT.items():
            self.assertEqual(len(contract['fields']['model']['enum']), 24)
            self.assertEqual(len(contract['fields']['quality']['enum']), 8 if operation == 'generate' else 7)
            required = node_class(operation).INPUT_TYPES()['required']
            self.assertEqual(required['model'][0][1:], contract['fields']['model']['enum'])
            endpoint = client_module.ENDPOINTS['gpt_image_' + operation + '_image']
            for field in ['model', 'quality']:
                self.assertEqual(endpoint['schema']['properties'][field]['enum'], contract['fields'][field]['enum'])
                self.assertEqual(endpoint['properties'][field]['enum'], contract['fields'][field]['enum'])

    def test_all_48_new_node_requests_omit_blank_quality_size(self):
        for operation, contract in CONTRACT.items():
            for model in contract['fields']['model']['enum']:
                with self.subTest(operation=operation, model=model):
                    values = self.defaults(operation)
                    values.update(model=model, prompt='Offline fixture')
                    if operation == 'edit':
                        values['image_urls'] = '["https://example.com/transparent.png"]'
                    body = self.post(operation, values)
                    self.assertEqual(body['model'], model)
                    self.assertNotIn('quality', body)
                    self.assertNotIn('size', body)
                    self.assertTrue(body['async'])
                    self.assertEqual(body['n'], 1)
                    if operation == 'edit':
                        self.assertEqual(body['image'], ['https://example.com/transparent.png'])
                        self.assertNotIn('mask', body)

    def test_json_values_and_saved_nonempty_widgets_are_preserved(self):
        values = self.defaults('generate')
        values.update(parameters_json=json.dumps({'model': 'gpt-image-2.6-sunburst:official',
                      'prompt': 'Offline fixture', 'quality': 'xhigh', 'size': '3840x2160'}))
        body = self.post('generate', values)
        self.assertEqual((body['quality'], body['size']), ('xhigh', '3840x2160'))
        values.update(quality='low', size='1024x1024')
        body = self.post('generate', values)
        self.assertEqual((body['quality'], body['size']), ('low', '1024x1024'))
        self.assertEqual(body['model'], 'gpt-image-2.6-sunburst:official')

    def test_dall_e_explicit_invalid_parameters_stop_before_post(self):
        for model, invalid in [
            ('dall-e-2', {'quality': 'auto'}), ('dall-e-3', {'quality': 'low'}),
            ('dall-e-2', {'size': 'auto'}), ('dall-e-3', {'size': '256x256'}),
            ('dall-e-3', {'count': '2'}),
        ]:
            values = self.defaults('generate')
            values.update(model=model, prompt='Offline fixture', **invalid)
            with patch.object(nodes, '_credential', return_value='offline-placeholder'):
                with patch.object(client_module.requests, 'request') as request:
                    with self.assertRaises(ValueError):
                        node_class('generate')().run(**values)
                request.assert_not_called()

    def test_dall_e_single_alpha_png_url_and_existing_image_outputs(self):
        values = self.defaults('edit')
        values.update(model='dall-e-2', prompt='Offline fixture',
                      image_urls='https://example.com/transparent.png', quality='standard')
        body = self.post('edit', values)
        self.assertEqual(body['image'], ['https://example.com/transparent.png'])
        self.assertEqual(body['quality'], 'standard')
        values['image_urls'] = '["https://example.com/a.png", "https://example.com/b.png"]'
        with patch.object(nodes, '_credential', return_value='offline-placeholder'):
            with patch.object(client_module.requests, 'request') as request:
                with self.assertRaisesRegex(ValueError, 'exactly one image'):
                    node_class('edit')().run(**values)
            request.assert_not_called()
        self.assertEqual(node_class('edit').RETURN_TYPES, ('STRING',) * 6)
        self.assertEqual(node_class('edit').INPUT_TYPES()['required']['image_urls'][0], 'STRING')
        loader = next(cls for name, cls in nodes.NODE_CLASS_MAPPINGS.items() if name.endswith('LoadImage'))
        self.assertEqual(loader.RETURN_TYPES[0], 'IMAGE')

    def test_static_output_formats_do_not_expand_to_gif(self):
        with self.assertRaises(ValueError):
            Client('offline-placeholder').prepare('gpt_image_generate_image', {
                'prompt': 'Offline fixture', 'output_format': 'gif'})

    def test_json_mask_is_rejected_instead_of_silently_dropped(self):
        for field in ['mask', 'mask_url']:
            with self.assertRaisesRegex(ValueError, 'multipart'):
                Client('offline-placeholder').prepare('gpt_image_edit_image', {
                    'prompt': 'Offline fixture', 'image_urls': 'https://example.com/alpha.png',
                    field: 'https://example.com/mask.png'})

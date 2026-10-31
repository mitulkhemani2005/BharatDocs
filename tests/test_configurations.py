import io
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.paths import resource_root
from backend.services.configurations import database
import json


class ConfigurationTests(unittest.TestCase):
    def test_individual_sizes_are_saved_and_printed_with_default_inheritance(self):
        layout = {**self.layout, 'regions': [
            {'name': 'Small name', 'rect': [10, 10, 180, 70], 'font_size': 10},
            {'name': 'Large name', 'rect': [10, 90, 180, 160], 'font_size': 24},
        ]}
        created = self.client.post('/configurations', json=layout, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        key = created.json()['id']
        with fitz.open() as doc:
            page = doc.new_page(width=300, height=200)
            page.insert_text((20, 40), 'ASHOK', fontsize=12)
            page.insert_text((20, 120), 'ASHOK', fontsize=12)
            source = doc.tobytes()
        upload_id = self.client.post('/upload', files={'file': ('sizes.pdf', source, 'application/pdf')}).json()['upload_id']
        for default_size, override, expected in ((18, 10, 10), (22, None, 22)):
            layout['font_size'] = default_size
            layout['regions'][0]['font_size'] = override
            self.assertEqual(self.client.put(f'/configurations/{key}', json=layout, headers=self.headers).status_code, 200)
            loaded = self.client.get('/configurations', headers=self.headers).json()['configurations'][0]
            self.assertEqual(loaded['regions'][0]['font_size'], override)
            self.assertEqual(loaded['regions'][1]['font_size'], 24)
            result = self.client.post('/translate-pdf', json={'upload_id': upload_id, 'configuration_id': key}, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            with fitz.open(stream=result.content, filetype='pdf') as doc:
                for box, size in (([10, 10, 180, 70], expected), ([10, 90, 180, 160], 24)):
                    spans = [span for block in doc[0].get_text('dict', clip=fitz.Rect(box))['blocks'] for line in block.get('lines', []) for span in line['spans'] if 'अशोक' in span['text']]
                    self.assertTrue(spans)
                    self.assertAlmostEqual(spans[0]['size'], size, delta=.01)

    def test_invalid_individual_size_is_rejected(self):
        for size in (7, 33):
            layout = {**self.layout, 'regions': [{**self.layout['regions'][0], 'font_size': size}]}
            self.assertEqual(self.client.post('/configurations', json=layout, headers=self.headers).status_code, 400)

    def test_user_selected_font_size_is_preserved_when_loaded(self):
        key = str(uuid.uuid4())
        old = {**self.layout, 'font_size': 10}
        with database() as connection:
            connection.execute('INSERT INTO layouts VALUES (?, ?, ?)', (key, self.headers['X-Configuration-Owner'], json.dumps(old)))
        loaded = self.client.get('/configurations', headers=self.headers).json()['configurations'][0]
        self.assertEqual(loaded['font_size'], 10)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.patches = [patch('backend.services.configurations.user_documents_root', return_value=root)]
        for constant, folder in [('UPLOAD_FOLDER', 'Work'), ('INPUT_FOLDER', 'Input'), ('OUTPUT_FOLDER', 'Output')]:
            path = root / folder
            path.mkdir()
            self.patches.append(patch(f'backend.api.routes.{constant}', path))
        for replacement in self.patches:
            replacement.start()
        self.client = TestClient(app)
        self.headers = {'X-Configuration-Owner': str(uuid.uuid4())}
        self.layout = {'name': 'Shop bills', 'page_width': 300, 'page_height': 200, 'font_size': 18,
                       'regions': [{'name': 'Shop name', 'rect': [10, 10, 180, 40], 'text_rect': [10, 45, 180, 65]}]}

    def tearDown(self):
        self.client.close()
        for replacement in reversed(self.patches):
            replacement.stop()
        self.temporary.cleanup()

    def test_saved_layout_crud_is_persistent_and_scoped_to_owner(self):
        created = self.client.post('/configurations', json=self.layout, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        key = created.json()['id']
        with TestClient(app) as another_client:
            self.assertEqual(another_client.get('/configurations', headers=self.headers).json()['configurations'][0]['id'], key)
        stranger = {'X-Configuration-Owner': str(uuid.uuid4())}
        self.assertEqual(self.client.get('/configurations', headers=stranger).json()['configurations'], [])
        self.assertEqual(self.client.delete(f'/configurations/{key}', headers=stranger).status_code, 404)
        self.assertEqual(self.client.put(f'/configurations/{key}', json=self.layout, headers=stranger).status_code, 404)
        changed = {**self.layout, 'name': 'Updated bill'}
        self.assertEqual(self.client.put(f'/configurations/{key}', json=changed, headers=self.headers).json()['name'], 'Updated bill')
        self.assertEqual(self.client.delete(f'/configurations/{key}', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/configurations', headers=self.headers).json()['configurations'], [])

    def test_rejects_invalid_areas(self):
        self.assertEqual(self.client.get('/configurations').status_code, 400)
        for regions in ([{'name': 'Outside', 'rect': [0, 0, 301, 40]}],
                        [{'name': 'Backwards', 'rect': [100, 10, 20, 40]}]):
            response = self.client.post('/configurations', json={**self.layout, 'regions': regions}, headers=self.headers)
            self.assertEqual(response.status_code, 400, response.text)

    def test_conversion_requires_an_existing_saved_configuration(self):
        self.assertEqual(self.client.get('/configurations', headers=self.headers).json()['configurations'], [])
        with fitz.open() as document:
            document.new_page(width=300, height=200).insert_text((20, 30), 'ASHOK')
            source = document.tobytes()
        upload_id = self.client.post('/upload', files={'file': ('bill.pdf', source, 'application/pdf')}).json()['upload_id']
        for fields in ({}, {'configuration_id': None}, {'configuration_id': ''}):
            response = self.client.post('/translate-pdf', json={'upload_id': upload_id, **fields}, headers=self.headers)
            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn('Create or select a saved configuration', response.json()['error'])
        for endpoint in ('/extract-regions', '/translate-regions'):
            response = self.client.get(endpoint, params={'upload_id': upload_id}, headers=self.headers)
            self.assertEqual(response.status_code, 400)
        key = self.client.post('/configurations', json=self.layout, headers=self.headers).json()['id']
        self.client.delete(f'/configurations/{key}', headers=self.headers)
        response = self.client.post('/translate-pdf', json={'upload_id': upload_id, 'configuration_id': key}, headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_packaged_resources_do_not_need_a_bundled_layout(self):
        resources = Path(self.temporary.name) / 'resources'
        executable = resources / 'backend' / 'desktop_backend.exe'
        executable.parent.mkdir(parents=True)
        (resources / 'hindi_terms.json').write_text('{}', encoding='utf-8')
        with patch('sys.frozen', True, create=True), patch('sys.executable', str(executable)):
            self.assertEqual(resource_root(), resources)

    def test_overlapping_areas_remain_separately_saved_but_extract_once(self):
        layout = {**self.layout, 'regions': [
            {'name': 'Area 1', 'rect': [10, 10, 90, 40]},
            {'name': 'Area 2', 'rect': [60, 10, 140, 40]},
            {'name': 'Area 3', 'rect': [120, 10, 180, 40]},
        ]}
        response = self.client.post('/configurations', json=layout, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        key = response.json()['id']
        with fitz.open() as doc:
            doc.new_page(width=300, height=200).insert_text((20, 30), 'ASHOK')
            source = doc.tobytes()
        upload_id = self.client.post('/upload', files={'file': ('overlap.pdf', source, 'application/pdf')}).json()['upload_id']
        extracted = self.client.get('/extract-regions', params={'upload_id': upload_id, 'configuration_id': key}, headers=self.headers)
        self.assertEqual([item['text'] for item in extracted.json()['regions']], ['ASHOK', '', ''])
        saved = self.client.get('/configurations', headers=self.headers).json()['configurations'][0]
        self.assertEqual([area['name'] for area in saved['regions']], ['Area 1', 'Area 2', 'Area 3'])
        self.assertEqual([area['rect'] for area in saved['regions']], [area['rect'] for area in layout['regions']])

    def test_protected_layer_preserves_pixels_and_upload_can_be_reused(self):
        with fitz.open() as document:
            for scale in (1, 2):
                page = document.new_page(width=300*scale, height=200*scale)
                page.insert_text((20*scale, 30*scale), 'ASHOK', fontsize=12*scale)
                page.insert_text((150*scale, 30*scale), '12345', fontsize=12*scale)
            source = document.tobytes()
        upload_id = self.client.post('/upload', files={'file': ('protected.pdf', source, 'application/pdf')}).json()['upload_id']
        layout = {**self.layout, 'regions': [
            {'name': 'Name', 'rect': [10, 10, 250, 45]},
            {'name': 'Amount', 'rect': [145, 10, 240, 45], 'mode': 'preserve'},
        ]}
        created = self.client.post('/configurations', json=layout, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        key = created.json()['id']
        extracted = self.client.get('/extract-regions', params={'upload_id': upload_id, 'configuration_id': key}, headers=self.headers).json()['regions']
        self.assertEqual([region['text'] for region in extracted], ['ASHOK', 'ASHOK'])
        for _ in range(2):
            result = self.client.post('/translate-pdf', json={'upload_id': upload_id, 'configuration_id': key}, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            with fitz.open(stream=result.content, filetype='pdf') as output, fitz.open(stream=source, filetype='pdf') as original:
                for index, scale in enumerate((1, 2)):
                    clip = fitz.Rect(145*scale, 10*scale, 240*scale, 45*scale)
                    self.assertEqual(original[index].get_pixmap(clip=clip).samples, output[index].get_pixmap(clip=clip).samples)

    def test_preview_and_selected_layout_convert_every_page_at_scaled_coordinates(self):
        with fitz.open() as document:
            for scale in (1, 2):
                page = document.new_page(width=300 * scale, height=200 * scale)
                page.insert_text((20 * scale, 30 * scale), 'ASHOK', fontsize=12 * scale)
                page.insert_text((20 * scale, 100 * scale), 'KEEP', fontsize=12 * scale)
            source = document.tobytes()
        uploaded = self.client.post('/upload', files={'file': ('sample.pdf', io.BytesIO(source), 'application/pdf')}).json()
        upload_id = uploaded['upload_id']
        preview = self.client.get('/pdf-page', params={'upload_id': upload_id, 'page': 2})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual((preview.json()['width'], preview.json()['height']), (600, 400))
        self.assertTrue(preview.json()['image'].startswith('data:image/png;base64,iVBOR'))
        self.assertEqual(self.client.get('/pdf-page', params={'upload_id': upload_id, 'page': 3}).status_code, 400)
        key = self.client.post('/configurations', json=self.layout, headers=self.headers).json()['id']
        result = self.client.post('/translate-pdf', json={'upload_id': upload_id, 'configuration_id': key}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text if result.status_code != 200 else '')
        with fitz.open(stream=result.content, filetype='pdf') as document:
            self.assertEqual(len(document), 2)
            for page, scale in zip(document, (1, 2)):
                self.assertIn('KEEP', page.get_text())
                placed = page.get_text(clip=fitz.Rect(10*scale, 10*scale, 180*scale, 40*scale))
                self.assertIn('अशोक', placed)

    def test_empty_selection_fails_instead_of_returning_an_unchanged_pdf(self):
        with fitz.open() as document:
            document.new_page(width=300, height=200).insert_text((20, 100), 'Outside selection')
            source = document.tobytes()
        upload_id = self.client.post('/upload', files={'file': ('empty-area.pdf', source, 'application/pdf')}).json()['upload_id']
        key = self.client.post('/configurations', json=self.layout, headers=self.headers).json()['id']
        result = self.client.post('/translate-pdf', json={'upload_id': upload_id, 'configuration_id': key}, headers=self.headers)
        self.assertEqual(result.status_code, 422)
        self.assertIn('No selectable text', result.json()['error'])

    def test_rotated_page_preview_and_translation_share_visible_coordinates(self):
        with fitz.open() as document:
            page = document.new_page(width=300, height=200)
            page.insert_text((20, 30), 'ASHOK', fontsize=12)
            page.set_rotation(90)
            source = document.tobytes()
            page.remove_rotation()
            bounds = page.get_text('blocks')[0][:4]
        upload_id = self.client.post('/upload', files={'file': ('rotated.pdf', source, 'application/pdf')}).json()['upload_id']
        preview = self.client.get('/pdf-page', params={'upload_id': upload_id}).json()
        self.assertEqual((preview['width'], preview['height']), (200, 300))
        layout = {**self.layout, 'page_width': 200, 'page_height': 300,
                  'regions': [{'name': 'Rotated name', 'rect': [110, 0, 200, 110], 'text_rect': [10, 120, 190, 150]}]}
        created = self.client.post('/configurations', json=layout, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        result = self.client.post('/translate-pdf', json={'upload_id': upload_id, 'configuration_id': created.json()['id']}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        with fitz.open(stream=result.content, filetype='pdf') as document:
            self.assertIn('अशोक', document[0].get_text(clip=fitz.Rect(110, 0, 200, 110)))


if __name__ == '__main__':
    unittest.main()

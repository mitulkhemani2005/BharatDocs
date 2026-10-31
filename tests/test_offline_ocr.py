import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from backend.core.paths import resource_root
from backend.services.pdf_modifier import apply_translations_to_pdf
from backend.services.pdf_reader import PdfValidationError
from backend.services.region_text_extractor import extract_text_from_regions
from backend.services.region_translator import translate_regions


class OfflineOcrTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / 'scanned.pdf'
        self.regions = [
            {'name': 'Name', 'rect': [10, 10, 180, 55], 'page_size': [300, 200]},
            {'name': 'Address', 'rect': [10, 70, 180, 110], 'page_size': [300, 200]},
        ]

    def make_scan(self):
        with fitz.open() as raster, fitz.open() as document:
            page = raster.new_page(width=300, height=200)
            page.insert_text((20, 40), 'ASHOK', fontsize=18)
            page.insert_text((20, 95), 'MAIN ROAD', fontsize=18)
            page.insert_text((190, 40), '12345', fontsize=14)
            page.draw_line((185, 0), (185, 200), width=1)
            image = page.get_pixmap(matrix=fitz.Matrix(3, 3)).tobytes('png')
            for scale in (1, 2):
                page = document.new_page(width=300 * scale, height=200 * scale)
                page.insert_image(page.rect, stream=image)
                page.insert_text((20 * scale, 170 * scale), 'KEEP', fontsize=12 * scale)
            document.save(self.source)

    def require_data(self):
        if not (resource_root() / 'models/tessdata/eng.traineddata').is_file():
            self.skipTest('Run python scripts/prepare_ocr_data.py to prepare offline OCR')

    def test_scanned_areas_translate_offline_on_all_pages_without_changing_surroundings(self):
        self.require_data()
        self.make_scan()
        with patch('socket.create_connection', side_effect=AssertionError('OCR must work offline')):
            extracted = extract_text_from_regions(self.source, self.regions)
            self.assertEqual([item['text'] for item in extracted], ['ASHOK', 'MAIN ROAD'] * 2)
            self.assertTrue(all(item['ocr'] and item['source_rects'] for item in extracted))
            translated = translate_regions(extracted)
            target = self.folder / 'hindi.pdf'
            apply_translations_to_pdf(self.source, target, translated, {'font_size': 18})
        with fitz.open(self.source) as source, fitz.open(target) as output:
            self.assertEqual(len(output), 2)
            for index, scale in enumerate((1, 2)):
                self.assertIn('अशोक', output[index].get_text())
                self.assertIn('KEEP', output[index].get_text())
                original = source[index].get_pixmap()
                changed = output[index].get_pixmap()
                before, after = bytearray(original.samples), bytearray(changed.samples)
                for region in self.regions:
                    box = fitz.Rect([value * scale for value in region['rect']]).irect
                    for y in range(box.y0, box.y1):
                        start, end = (y * original.width + box.x0) * 3, (y * original.width + box.x1) * 3
                        before[start:end] = after[start:end]
                self.assertEqual(before, after, 'Pixels outside the selected rectangles must stay unchanged')
                clip = fitz.Rect(20 * scale, 24 * scale, 45 * scale, 41 * scale)
                self.assertNotEqual(source[index].get_pixmap(clip=clip).samples,
                                    output[index].get_pixmap(clip=clip).samples)

    def test_overlapping_scan_selections_do_not_translate_the_same_words_twice(self):
        self.require_data()
        self.make_scan()
        regions = [self.regions[0], {**self.regions[0], 'name': 'Overlapping name'}]
        extracted = extract_text_from_regions(self.source, regions)
        self.assertEqual([item['text'] for item in extracted], ['ASHOK', '', 'ASHOK', ''])

    def test_protected_scan_text_is_neither_extracted_nor_painted(self):
        self.require_data()
        self.make_scan()
        regions = [
            {**self.regions[0], 'rect': [10, 10, 290, 55]},
            {'name': 'Number', 'rect': [185, 10, 295, 55], 'mode': 'preserve', 'page_size': [300, 200]},
        ]
        extracted = extract_text_from_regions(self.source, regions)
        self.assertEqual([item['text'] for item in extracted], ['ASHOK', 'ASHOK'])
        target = self.folder / 'protected.pdf'
        apply_translations_to_pdf(self.source, target, translate_regions(extracted))
        with fitz.open(self.source) as source, fitz.open(target) as output:
            for index, scale in enumerate((1, 2)):
                clip = fitz.Rect(185 * scale, 10 * scale, 295 * scale, 55 * scale)
                self.assertEqual(source[index].get_pixmap(clip=clip).samples, output[index].get_pixmap(clip=clip).samples)

    def test_missing_ocr_data_reports_setup_instead_of_mislabeling_a_valid_selection(self):
        self.make_scan()
        with patch('backend.services.ocr.resource_root', return_value=self.folder):
            with self.assertRaisesRegex(PdfValidationError, 'offline OCR data is missing'):
                extract_text_from_regions(self.source, self.regions)

    def test_existing_ocr_layer_does_not_trigger_recognition_again_for_overlaps(self):
        self.make_scan()
        layered = self.folder / 'existing-ocr.pdf'
        with fitz.open(self.source) as document:
            for index, scale in enumerate((1, 2)):
                document[index].insert_text((20 * scale, 40 * scale), 'ASHOK', fontsize=18 * scale, render_mode=3)
            document.save(layered)
        with patch('backend.services.region_text_extractor.recognize_area', side_effect=AssertionError('Use the existing text layer')):
            extracted = extract_text_from_regions(layered, [self.regions[0], {**self.regions[0], 'name': 'Overlap'}])
        self.assertEqual([item['text'] for item in extracted], ['ASHOK', '', 'ASHOK', ''])
        target = self.folder / 'existing-ocr-hindi.pdf'
        apply_translations_to_pdf(layered, target, translate_regions(extracted))
        with fitz.open(target) as output:
            self.assertIn('अशोक', output[0].get_text())

    def test_native_text_uses_tight_selection_without_invoking_ocr(self):
        with fitz.open() as document:
            page = document.new_page(width=300, height=200)
            page.insert_text((20, 40), 'ASHOK', fontsize=18)
            document.save(self.source)
        with patch('backend.services.region_text_extractor.recognize_area', side_effect=AssertionError('Native text must stay fast')):
            extracted = extract_text_from_regions(self.source, [{'name': 'Tight', 'rect': [15, 26, 100, 41]}])
        self.assertEqual(extracted[0]['text'], 'ASHOK')
        self.assertFalse(extracted[0]['ocr'])

    def test_mixed_page_uses_ocr_only_for_the_area_without_selectable_text(self):
        self.require_data()
        self.make_scan()
        mixed = self.folder / 'mixed.pdf'
        with fitz.open(self.source) as document:
            for index, scale in enumerate((1, 2)):
                document[index].insert_text((20 * scale, 40 * scale), 'ASHOK', fontsize=18 * scale, render_mode=3)
            document.save(mixed)
        from backend.services.ocr import recognize_area
        with patch('backend.services.region_text_extractor.recognize_area', wraps=recognize_area) as ocr:
            extracted = extract_text_from_regions(mixed, self.regions)
        self.assertEqual([item['text'] for item in extracted], ['ASHOK', 'MAIN ROAD'] * 2)
        self.assertEqual([item['ocr'] for item in extracted], [False, True, False, True])
        self.assertEqual(ocr.call_count, 2, 'Only the scanned address on each page needs OCR')
        for call, scale in zip(ocr.call_args_list, (1, 2)):
            self.assertEqual(list(call.args[1]), [value * scale for value in self.regions[1]['rect']])


if __name__ == '__main__':
    unittest.main()

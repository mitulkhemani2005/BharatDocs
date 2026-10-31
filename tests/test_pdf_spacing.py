import unittest
import tempfile
import random
from pathlib import Path

import fitz

from backend.services.pdf_modifier import (
    FONT_DIRECTORY, PdfProcessingError, _fit_text_rect, _font_css,
    _prepare_hindi_text, _source_clear_rect,
    apply_translations_to_pdf, _subtract_rectangles,
)


class HindiSpacingTests(unittest.TestCase):
    def test_selected_size_is_exact_even_when_a_continuation_is_needed(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source.pdf'
            with fitz.open() as doc:
                doc.new_page(width=100, height=80).insert_text((10, 25), 'NAME', fontsize=6)
                doc.save(source)
            for size in (10, 24, 32):
                output = Path(temporary) / f'{size}.pdf'
                apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Name', 'rect': [8, 15, 35, 28], 'hindi_text': 'अशोक किराना एवं जनरल स्टोर'}], {'font_size': size})
                with fitz.open(output) as doc:
                    spans = [span for page in doc for block in page.get_text('dict')['blocks'] for line in block.get('lines', []) for span in line['spans'] if 'अशोक' in span['text']]
                    self.assertTrue(spans)
                    for span in spans:
                        self.assertAlmostEqual(span['size'], size, delta=.01)

    def test_shared_space_is_tried_at_large_size_before_compacting(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'source.pdf', Path(temporary) / 'output.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=300, height=180)
                page.insert_text((20, 60), 'NAME', fontsize=8)
                doc.save(source)
            apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Name', 'rect': [15, 50, 45, 65], 'hindi_text': 'अशोक किराना'}])
            with fitz.open(output) as doc:
                spans = [span for block in doc[0].get_text('dict')['blocks'] for line in block.get('lines', []) for span in line['spans'] if 'अशोक' in span['text']]
                self.assertTrue(spans)
                self.assertGreaterEqual(spans[0]['size'], 17.09)

    def test_fast_clipping_preserves_exact_unmasked_coverage(self):
        rng = random.Random(42)
        for _ in range(40):
            masks = []
            for _ in range(8):
                x, y = rng.randint(-5, 20), rng.randint(-5, 20)
                masks.append(fitz.Rect(x, y, x + rng.randint(1, 10), y + rng.randint(1, 10)))
            pieces = _subtract_rectangles(fitz.Rect(0, 0, 20, 20), masks + masks)
            expected = sum(not any((x + .5, y + .5) in mask for mask in masks) for x in range(20) for y in range(20))
            self.assertEqual(sum(rect.get_area() for rect in pieces), expected)
            for i, first in enumerate(pieces):
                for second in pieces[i + 1:]:
                    self.assertFalse(first.intersects(second))

    def test_crowded_fields_borrow_shared_space_without_a_continuation(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'source.pdf', Path(temporary) / 'output.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=220, height=120)
                page.insert_text((11, 28), 'A', fontsize=6)
                page.insert_text((40, 28), 'B', fontsize=6)
                page.draw_line((0, 18), (220, 18))
                page.draw_line((0, 42), (220, 42))
                doc.save(source)
            apply_translations_to_pdf(source, output, [
                {'page': 0, 'region_name': 'Name', 'rect': [10, 20, 30, 32], 'hindi_text': 'अशोक किराना एवं जनरल स्टोर'},
                {'page': 0, 'region_name': 'Address', 'rect': [32, 20, 180, 32], 'hindi_text': 'नगर'},
            ])
            with fitz.open(output) as doc:
                self.assertEqual(len(doc), 1)
                self.assertIn('अशोक', doc[0].get_text())
                self.assertIn('नगर', doc[0].get_text())

    def test_full_page_gets_readable_continuation_and_original_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'source.pdf', Path(temporary) / 'output.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=200, height=100)
                image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 10), False)
                image.clear_with(240)
                page.insert_image(page.rect, pixmap=image)
                page.insert_text((20, 35), 'ASHOK', fontsize=12)
                before = page.get_pixmap().samples
                doc.save(source)
            apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Shop name', 'rect': [15, 20, 100, 40], 'hindi_text': 'अशोक किराना'}])
            with fitz.open(output) as doc:
                self.assertEqual(len(doc), 2)
                self.assertEqual(doc[0].get_pixmap().samples, before)
                self.assertIn('अशोक', doc[1].get_text())

    def test_long_continuation_paginates_without_losing_words(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'source.pdf', Path(temporary) / 'output.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=200, height=100)
                page.insert_text((20, 35), 'ASHOK', fontsize=12)
                doc.save(source)
            apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Name', 'rect': [15, 20, 40, 30], 'protected_rects': [[0, 0, 200, 100]], 'hindi_text': ' '.join(['अशोक'] * 1000)}])
            with fitz.open(output) as doc:
                self.assertGreater(len(doc), 2)
                self.assertEqual(sum(page.get_text().count('अशोक') for page in list(doc)[1:]), 1000)

    def test_long_hindi_wraps_automatically_without_covering_neighbor(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'source.pdf', Path(temporary) / 'output.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=300, height=200)
                page.insert_text((20, 70), 'NAME', fontsize=8)
                page.insert_text((20, 130), 'KEEP THIS LABEL', fontsize=10)
                before = page.get_pixmap(clip=fitz.Rect(15, 117, 150, 135)).samples
                doc.save(source)
            apply_translations_to_pdf(source, output, [{
                'page': 0, 'region_name': 'name', 'rect': [15, 60, 90, 75],
                'hindi_text': 'अशोक किराना एवं जनरल स्टोर ऋषि नगर',
            }])
            with fitz.open(output) as doc:
                self.assertEqual(before, doc[0].get_pixmap(clip=fitz.Rect(15, 117, 150, 135)).samples)
                self.assertIn('अशोक', doc[0].get_text())

    def test_upper_and_lower_matras_stay_inside_separate_rows(self):
        destinations = [fitz.Rect(20, 20, 219, 33.3), fitz.Rect(20, 34.9, 219, 49)]
        texts = ["कृष्ण किराना स्टोर", "ऋषि नगर, उज्जैन"]
        with fitz.open() as shaped, fitz.open() as output:
            archive = fitz.Archive(str(FONT_DIRECTORY))
            prepared = [_prepare_hindi_text(shaped, text, 14, _font_css('Noto Sans Devanagari', 14), archive) for text in texts]
            page = output.new_page(width=240, height=70)
            for (number, ink), destination in zip(prepared, destinations):
                fitted = _fit_text_rect(destination, ink, .7)
                self.assertTrue(destination.contains(fitted))
                page.show_pdf_page(fitted, shaped, number, clip=ink)
            pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), alpha=True)
            alpha = pix.samples[3::4]
            nonempty_rows = []
            for row in range(pix.height):
                if any(alpha[row * pix.width:(row + 1) * pix.width]):
                    nonempty_rows.append(row / 4)
            self.assertTrue(any(20 <= y <= 33.3 for y in nonempty_rows))
            self.assertTrue(any(34.9 <= y <= 49 for y in nonempty_rows))
            self.assertTrue(all(19.75 <= y <= 33.3 or 34.65 <= y <= 49 for y in nonempty_rows), nonempty_rows)

    def test_source_descenders_are_fully_cleared(self):
        bbox = fitz.Rect(96, 68, 296, 77)
        source = {'bbox': (115, 69, 195, 78.2)}
        label = {'bbox': (37, 69, 94, 77)}
        clear = _source_clear_rect(bbox, [source, label])
        self.assertTrue(clear.contains(fitz.Rect(source['bbox'])))
        self.assertFalse(clear.intersects(fitz.Rect(label['bbox'])))

    def test_long_text_cannot_be_forced_into_an_unreadable_box(self):
        with self.assertRaises(PdfProcessingError):
            _fit_text_rect(fitz.Rect(0, 0, 20, 5), fitz.Rect(0, 0, 200, 15), .7)

    def test_moving_mobile_preserves_gst_and_clears_the_old_row(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'source.pdf', Path(temporary) / 'output.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=320, height=140)
                page.insert_text((115, 75), 'ASHOK', fontsize=7)
                page.insert_text((140, 99), 'Mobile: 9988776655', fontsize=6.5)
                page.insert_text((37, 112), 'GSTIN: 23ABCDE1234F1Z5', fontsize=7)
                gst_clip = fitz.Rect(35, 103, 175, 115)
                before = page.get_pixmap(clip=gst_clip, matrix=fitz.Matrix(3, 3)).samples
                doc.save(source)
            apply_translations_to_pdf(source, output, [{
                'page': 0, 'region_name': 'name', 'rect': [96, 68, 296, 77],
                'text_rect': [96, 69.5, 295, 82.8], 'hindi_text': 'अशोक किराना',
            }], {'move_regions': [{'rect': [126, 92, 296, 102], 'destination': [190, 101, 295, 113]}]})
            with fitz.open(output) as doc:
                page = doc[0]
                self.assertEqual(before, page.get_pixmap(clip=gst_clip, matrix=fitz.Matrix(3, 3)).samples)
                old = page.get_pixmap(clip=fitz.Rect(126, 92, 296, 102), colorspace=fitz.csGRAY)
                moved = page.get_pixmap(clip=fitz.Rect(190, 101, 295, 113), colorspace=fitz.csGRAY)
                self.assertTrue(all(value == 255 for value in old.samples))
                self.assertGreater(sum(value < 128 for value in moved.samples), 20)


if __name__ == '__main__':
    unittest.main()

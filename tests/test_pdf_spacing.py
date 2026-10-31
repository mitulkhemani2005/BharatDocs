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
    def test_short_bill_cell_can_auto_fit_below_eight_points(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary)/'source.pdf', Path(temporary)/'output.pdf'
            with fitz.open() as doc:
                doc.new_page(width=300, height=100).insert_text((25, 28), 'NAME', fontsize=6)
                doc.save(source)
            apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Short cell', 'rect': [20, 20, 220, 29.5], 'hindi_text': 'अशोक ऊँचे ऋषि कूँज'}])
            with fitz.open(output) as doc:
                self.assertEqual(len(doc), 1)
                spans = [span for block in doc[0].get_text('dict')['blocks'] for line in block.get('lines', []) for span in line['spans'] if 'अशोक' in span['text']]
                self.assertTrue(spans)
                self.assertGreaterEqual(spans[0]['size'], 5.99)
                self.assertLess(spans[0]['size'], 8)

    def test_only_crowded_area_shrinks_and_everything_stays_inside(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary)/'source.pdf', Path(temporary)/'output.pdf'
            boxes = [fitz.Rect(20, 20, 150, 65), fitz.Rect(20, 100, 250, 170)]
            with fitz.open() as doc:
                page = doc.new_page(width=300, height=200)
                page.insert_text((25, 40), 'NAME', fontsize=6)
                page.insert_text((25, 125), 'NAME', fontsize=6)
                before = page.get_pixmap().samples
                doc.save(source)
            apply_translations_to_pdf(source, output, [
                {'page': 0, 'region_name': 'Tight', 'rect': list(boxes[0]), 'font_size': 32, 'hindi_text': 'अशोक किराना एवं जनरल स्टोर'},
                {'page': 0, 'region_name': 'Roomy', 'rect': list(boxes[1]), 'font_size': 24, 'hindi_text': 'अशोक'},
            ])
            with fitz.open(output) as doc:
                self.assertEqual(len(doc), 1)
                for box, maximum in zip(boxes, (32, 24)):
                    spans = [span for block in doc[0].get_text('dict', clip=box)['blocks'] for line in block.get('lines', []) for span in line['spans'] if 'अशोक' in span['text']]
                    self.assertTrue(spans)
                    size = spans[0]['size']
                    self.assertGreaterEqual(size, 7.99)
                    if maximum == 32:
                        self.assertLess(size, maximum)
                    else:
                        self.assertAlmostEqual(size, maximum, delta=.01)
                after = doc[0].get_pixmap().samples
                for y in range(200):
                    for x in range(300):
                        if not any((x+.5, y+.5) in box for box in boxes):
                            start = (y*300+x)*3
                            self.assertEqual(before[start:start+3], after[start:start+3])

    def test_exact_font_and_pixels_outside_selected_area_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source.pdf'
            box = fitz.Rect(20, 20, 200, 120)
            with fitz.open() as doc:
                page = doc.new_page(width=300, height=200)
                page.insert_text((30, 50), 'NAME', fontsize=6)
                page.insert_text((20, 170), 'KEEP OUTSIDE', fontsize=12)
                before = page.get_pixmap().samples
                doc.save(source)
            for size in (10, 24, 32):
                output = Path(temporary) / f'{size}.pdf'
                apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Name', 'rect': list(box), 'text_rect': [20, 130, 200, 190], 'hindi_text': 'अशोक किराना'}], {'font_size': size})
                with fitz.open(output) as doc:
                    self.assertEqual(len(doc), 1)
                    page = doc[0]
                    after = page.get_pixmap().samples
                    for y in range(200):
                        if 20 <= y < 120:
                            ranges = ((0, 20), (200, 300))
                        else:
                            ranges = ((0, 300),)
                        for x0, x1 in ranges:
                            start, end = (y*300+x0)*3, (y*300+x1)*3
                            self.assertEqual(before[start:end], after[start:end])
                    spans = [span for block in page.get_text('dict')['blocks'] for line in block.get('lines', []) for span in line['spans'] if 'अशोक' in span['text']]
                    self.assertTrue(spans)
                    self.assertAlmostEqual(spans[0]['size'], size, delta=.01)
                    self.assertIn('अशोक', page.get_text(clip=box))

    def test_crowded_area_reports_its_name_without_moving_or_appending(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary)/'source.pdf', Path(temporary)/'output.pdf'
            with fitz.open() as doc:
                doc.new_page(width=300, height=200).insert_text((20, 30), 'NAME', fontsize=8)
                doc.save(source)
            with self.assertRaisesRegex(PdfProcessingError, "Shop name.*6 pt"):
                apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Shop name', 'rect': [15, 20, 40, 30], 'hindi_text': 'अशोक किराना एवं जनरल स्टोर'}])
            self.assertFalse(output.exists())

    def test_hindi_wraps_inside_a_tall_selected_area(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary)/'source.pdf', Path(temporary)/'output.pdf'
            with fitz.open() as doc:
                doc.new_page(width=300, height=220).insert_text((25, 40), 'NAME', fontsize=8)
                doc.save(source)
            box = fitz.Rect(20, 20, 110, 195)
            apply_translations_to_pdf(source, output, [{'page': 0, 'region_name': 'Name', 'rect': list(box), 'hindi_text': 'अशोक किराना एवं जनरल स्टोर ऋषि नगर'}])
            with fitz.open(output) as doc:
                self.assertEqual(len(doc), 1)
                self.assertIn('अशोक', doc[0].get_text(clip=box))




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



if __name__ == '__main__':
    unittest.main()

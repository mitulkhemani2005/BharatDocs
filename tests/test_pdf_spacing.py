import unittest
import tempfile
from pathlib import Path

import fitz

from backend.services.pdf_modifier import (
    FONT_DIRECTORY, PdfProcessingError, _fit_text_rect, _font_css,
    _prepare_hindi_text, _source_clear_rect,
    apply_translations_to_pdf,
)


class HindiSpacingTests(unittest.TestCase):
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

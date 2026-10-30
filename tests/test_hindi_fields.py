import json
import re
import socket
import unittest
from unittest.mock import patch

from backend.services.translator import MODEL_DIRECTORY, translate_to_hindi


class HindiFieldsTests(unittest.TestCase):
    def test_shop_abbreviations_and_names(self):
        self.assertEqual(translate_to_hindi("ASHOK KI.& GEN ST."), "अशोक किराना एवं जनरल स्टोर")
        self.assertEqual(translate_to_hindi("ASIA. KGM"), "एशिया. केजीएम")
        self.assertEqual(translate_to_hindi("SAI SHREE PROVISION"), "साईं श्री प्रोविजन")

    def test_address_identifiers_are_preserved(self):
        self.assertEqual(translate_to_hindi("31B - INDRAPURI BANK OF INDIA KE PAS, SETHI NAGAR"),
                         "31B - इंद्रपुरी बैंक ऑफ इंडिया के पास, सेठी नगर")
        self.assertEqual(translate_to_hindi("LIG-I,54,INDIRANAGAR"), "एलआईजी-१,54,इंदिरा नगर")

    def test_existing_hindi_and_empty_fields(self):
        self.assertEqual(translate_to_hindi("श्री ASHOK, 456001"), "श्री अशोक, 456001")
        self.assertEqual(translate_to_hindi("  "), "  ")

    @unittest.skipUnless((MODEL_DIRECTORY / "model.bin").exists(), "Offline model not prepared")
    def test_neural_name_spelling_without_network(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            self.assertEqual(translate_to_hindi("KHEMANI"), "खेमानी")
            self.assertEqual(translate_to_hindi("RAKESH"), "राकेश")
            result = translate_to_hindi("SAIFUDDIN & SONS")
            self.assertFalse(re.search(r"[A-Za-z<>\ufffd]", result), result)


if __name__ == "__main__":
    unittest.main()

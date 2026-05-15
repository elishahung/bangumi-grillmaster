import unittest

from services.gemini.fixed_glossary import (
    _normalize_jp,
    filter_fixed_glossary,
    load_fixed_glossary,
)


class NormalizeJpTests(unittest.TestCase):
    def test_katakana_hiragana_fold(self):
        self.assertEqual(_normalize_jp("ポット"), _normalize_jp("ぽっと"))
        self.assertEqual(_normalize_jp("フニャオ"), _normalize_jp("ふにゃお"))
        self.assertEqual(_normalize_jp("メゾン"), _normalize_jp("めぞん"))

    def test_nfkc_width_and_case(self):
        self.assertEqual(_normalize_jp("ＡＢＣ１２３"), "abc123")

    def test_strips_longvowel_space_punctuation(self):
        self.assertEqual(_normalize_jp("ザ・マミィ"), _normalize_jp("ザマミィ"))
        self.assertEqual(
            _normalize_jp("熊元　プロレス"), _normalize_jp("熊元プロレス")
        )

    def test_non_phonetic_terms_stay_distinct(self):
        # "filtered" mode is deliberately NOT phonetic — Tier-2 ASR garble
        # must remain unmatched (that is "full" mode's responsibility).
        self.assertNotEqual(_normalize_jp("パラパラ"), _normalize_jp("パロパロ"))
        self.assertNotEqual(
            _normalize_jp("クーマイメテオ"), _normalize_jp("空前メテオ")
        )


class FilterFixedGlossaryTests(unittest.TestCase):
    def test_matches_kana_script_drift(self):
        entries = [
            (["渡辺ポット", "渡邊ポット"], "渡邊Pot"),
            (["めぞん"], "Maison"),
            (["原田フニャオ"], "原田Funyao"),
        ]
        srt = "\n".join(
            [
                "ダイオウ渡辺ぽっと",  # hiragana vs glossary katakana
                "メゾン原一国",  # katakana vs glossary hiragana
                "ダンビラムーチョ、原田ふにゃお",
            ]
        )
        matched = filter_fixed_glossary(entries, srt)
        self.assertEqual(
            {zh for _, zh in matched}, {"渡邊Pot", "Maison", "原田Funyao"}
        )

    def test_matches_fullwidth_space_and_middledot(self):
        entries = [
            (["熊元プロレス"], "熊元摔角"),
            (["ザ・マミィ"], "The Mommy"),
        ]
        matched = filter_fixed_glossary(entries, "出演：熊元　プロレス と ザマミィ")
        self.assertEqual(
            {zh for _, zh in matched}, {"熊元摔角", "The Mommy"}
        )

    def test_does_not_phonetically_overmatch(self):
        entries = [
            (["パロパロ"], "ParoParo"),
            (["空前メテオ"], "空前Meteor"),
        ]
        matched = filter_fixed_glossary(
            entries, "パラパラと踊る\nクーマイメテオ、茶屋"
        )
        self.assertEqual(matched, [])

    def test_empty_normalized_alias_does_not_match_everything(self):
        entries = [(["・・・"], "Bogus")]
        matched = filter_fixed_glossary(entries, "なんでもいい haystack 文字列")
        self.assertEqual(matched, [])

    def test_no_texts_returns_empty(self):
        entries = [(["メゾン"], "Maison")]
        self.assertEqual(filter_fixed_glossary(entries), [])
        self.assertEqual(filter_fixed_glossary(entries, None, ""), [])


class LoadFixedGlossaryTests(unittest.TestCase):
    def test_loads_real_file_shape(self):
        entries = load_fixed_glossary()
        self.assertTrue(entries)  # bundled file exists and parses non-empty
        for aliases, zh in entries:
            self.assertIsInstance(aliases, list)
            self.assertTrue(all(isinstance(a, str) and a for a in aliases))
            self.assertIsInstance(zh, str)
            self.assertTrue(zh)


if __name__ == "__main__":
    unittest.main()

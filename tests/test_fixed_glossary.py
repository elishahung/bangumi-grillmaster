import json
import tempfile
import unittest
from pathlib import Path

from services.fixed_glossary import (
    FixedGlossary,
    TalentUnit,
    _normalize_jp,
    filter_fixed_glossary,
    format_fixed_glossary_block,
    load_fixed_glossary,
)


def U(group, members):
    """Build a TalentUnit (members given as a plain list of entries)."""
    return TalentUnit(group, tuple(members))


def G(*talents, others=()):
    """Build a FixedGlossary from talent units and other entries."""
    return FixedGlossary(tuple(talents), tuple(others))


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
        glossary = G(
            others=(
                (["渡辺ポット", "渡邊ポット"], "渡邊Pot"),
                (["めぞん"], "Maison"),
                (["原田フニャオ"], "原田Funyao"),
            )
        )
        srt = "\n".join(
            [
                "ダイオウ渡辺ぽっと",  # hiragana vs glossary katakana
                "メゾン原一国",  # katakana vs glossary hiragana
                "ダンビラムーチョ、原田ふにゃお",
            ]
        )
        matched = filter_fixed_glossary(glossary, srt)
        self.assertEqual(matched.talents, ())
        self.assertEqual(
            {zh for _, zh in matched.others},
            {"渡邊Pot", "Maison", "原田Funyao"},
        )

    def test_matches_fullwidth_space_and_middledot(self):
        glossary = G(
            others=(
                (["熊元プロレス"], "熊元摔角"),
                (["ザ・マミィ"], "The Mommy"),
            )
        )
        matched = filter_fixed_glossary(
            glossary, "出演：熊元　プロレス と ザマミィ"
        )
        self.assertEqual(matched.talents, ())
        self.assertEqual(
            {zh for _, zh in matched.others}, {"熊元摔角", "The Mommy"}
        )

    def test_does_not_phonetically_overmatch(self):
        glossary = G(
            others=(
                (["パロパロ"], "ParoParo"),
                (["空前メテオ"], "空前Meteor"),
            )
        )
        matched = filter_fixed_glossary(
            glossary, "パラパラと踊る\nクーマイメテオ、茶屋"
        )
        self.assertFalse(matched)
        self.assertEqual(matched.others, ())

    def test_empty_normalized_alias_does_not_match_everything(self):
        glossary = G(others=((["・・・"], "Bogus"),))
        matched = filter_fixed_glossary(
            glossary, "なんでもいい haystack 文字列"
        )
        self.assertEqual(matched.others, ())

    def test_no_texts_returns_empty(self):
        glossary = G(others=((["メゾン"], "Maison"),))
        self.assertFalse(filter_fixed_glossary(glossary))
        self.assertFalse(filter_fixed_glossary(glossary, None, ""))

    def test_talent_unit_emitted_whole_on_single_member_match(self):
        unit = U(
            (["かまいたち"], "鎌鼬"),
            [(["山内"], "山內"), (["濱家"], "濱家")],
        )
        matched = filter_fixed_glossary(G(unit), "ゲストは濱家さん")
        self.assertEqual(len(matched.talents), 1)
        got = matched.talents[0]
        self.assertEqual(got.group, (["かまいたち"], "鎌鼬"))
        self.assertEqual(
            [zh for _, zh in got.members], ["山內", "濱家"]
        )

    def test_talent_unit_emitted_on_group_only_match(self):
        unit = U((["かまいたち"], "鎌鼬"), [(["山内"], "山內")])
        matched = filter_fixed_glossary(G(unit), "次はかまいたちの出番")
        self.assertEqual(len(matched.talents), 1)
        self.assertEqual(matched.talents[0].group, (["かまいたち"], "鎌鼬"))

    def test_talent_unit_not_emitted_when_nothing_matches(self):
        unit = U((["かまいたち"], "鎌鼬"), [(["山内"], "山內")])
        self.assertFalse(filter_fixed_glossary(G(unit), "無關內容"))

    def test_solo_unit_match(self):
        solo = U(None, [(["ヒコロヒー"], "Hikorohee")])
        self.assertEqual(
            len(filter_fixed_glossary(G(solo), "ヒコロヒーです").talents), 1
        )
        self.assertFalse(filter_fixed_glossary(G(solo), "別人").talents)

    def test_others_unchanged_alongside_talents(self):
        unit = U((["かまいたち"], "鎌鼬"), [(["山内"], "山內")])
        glossary = G(
            unit,
            others=(
                (["かまいたちの知らんけど"], "鎌鼬的我是不知道啦"),
                (["ボケ"], "裝傻"),
            ),
        )
        matched = filter_fixed_glossary(glossary, "山内くんとボケの話")
        self.assertEqual(len(matched.talents), 1)
        self.assertEqual(
            {zh for _, zh in matched.others}, {"裝傻"}
        )

    def test_empty_member_alias_guard_in_unit(self):
        unit = U(None, [(["・・・"], "Bogus")])
        self.assertFalse(
            filter_fixed_glossary(G(unit), "なんでもいい haystack").talents
        )


class LoadFixedGlossaryTests(unittest.TestCase):
    def _load(self, obj):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.json"
            p.write_text(
                json.dumps(obj, ensure_ascii=False), encoding="utf-8"
            )
            return load_fixed_glossary(path=p)

    def test_bad_top_level_type_returns_empty(self):
        # An un-migrated old flat-list file must degrade safely, not crash.
        g = self._load([{"jp": ["x"], "zh": "y"}])
        self.assertFalse(g)
        self.assertEqual(g, FixedGlossary())

    def test_talents_and_others_both_loaded(self):
        g = self._load(
            {
                "talents": [
                    {
                        "group": {"jp": ["かまいたち"], "zh": "鎌鼬"},
                        "members": [{"jp": ["山内"], "zh": "山內"}],
                    },
                    {"members": [{"jp": ["ヒコロヒー"], "zh": "Hikorohee"}]},
                ],
                "others": [{"jp": ["ボケ"], "zh": "裝傻"}],
            }
        )
        self.assertEqual(len(g.talents), 2)
        self.assertEqual(g.talents[0].group, (["かまいたち"], "鎌鼬"))
        self.assertIsNone(g.talents[1].group)
        self.assertEqual({zh for _, zh in g.others}, {"裝傻"})

    def test_malformed_unit_skipped(self):
        g = self._load(
            {
                "talents": [
                    "not-an-object",
                    {"members": []},  # empty members → dropped
                    {  # bad optional group → dropped group, unit kept
                        "group": {"jp": [], "zh": "x"},
                        "members": [{"jp": ["盛山"], "zh": "盛山"}],
                    },
                    {"members": [{"jp": ["valid"], "zh": "OK"}]},
                ],
                "others": [
                    {"jp": "notalist", "zh": "bad"},
                    {"jp": ["good"], "zh": "Good"},
                ],
            }
        )
        self.assertEqual(len(g.talents), 2)
        kept_group = g.talents[0]
        self.assertIsNone(kept_group.group)
        self.assertEqual([zh for _, zh in kept_group.members], ["盛山"])
        self.assertEqual({zh for _, zh in g.others}, {"Good"})

    def test_loads_real_file_shape(self):
        # Bundled file must parse non-empty into the new grouped structure.
        glossary = load_fixed_glossary()
        self.assertTrue(glossary)
        for unit in glossary.talents:
            self.assertIsInstance(unit, TalentUnit)
            self.assertTrue(unit.members)
            for entry in unit.entries():
                aliases, zh = entry
                self.assertIsInstance(aliases, list)
                self.assertTrue(all(isinstance(a, str) and a for a in aliases))
                self.assertIsInstance(zh, str)
                self.assertTrue(zh)
        for aliases, zh in glossary.others:
            self.assertIsInstance(aliases, list)
            self.assertTrue(all(isinstance(a, str) and a for a in aliases))
            self.assertIsInstance(zh, str)
            self.assertTrue(zh)


class FormatFixedGlossaryBlockTests(unittest.TestCase):
    def test_falsy_glossary_renders_empty(self):
        self.assertEqual(
            format_fixed_glossary_block(FixedGlossary(), full_mode=False), ""
        )

    def test_grouped_layout_with_group_and_solo(self):
        glossary = G(
            U((["かまいたち"], "鎌鼬"), [(["山内", "山內健司"], "山內")]),
            U(None, [(["ヒコロヒー"], "Hikorohee")]),
            others=((["ボケ"], "裝傻"),),
        )
        out = format_fixed_glossary_block(glossary, full_mode=False)
        self.assertIn("〔藝人/組合〕", out)
        self.assertIn("・組合：かまいたち → 鎌鼬", out)
        self.assertIn("    · 山内 / 山內健司 → 山內", out)
        self.assertIn("・（單人）", out)
        self.assertIn("    · ヒコロヒー → Hikorohee", out)
        self.assertIn("〔節目/單元/品牌/術語〕", out)
        self.assertIn("- ボケ → 裝傻", out)

    def test_header_differs_full_vs_filtered(self):
        glossary = G(others=((["ボケ"], "裝傻"),))
        full = format_fixed_glossary_block(glossary, full_mode=True)
        filtered = format_fixed_glossary_block(glossary, full_mode=False)
        self.assertIn("完整參照表", full)
        self.assertNotIn("完整參照表", filtered)
        self.assertIn("最高優先級", filtered)

    def test_empty_section_omitted(self):
        only_others = format_fixed_glossary_block(
            G(others=((["ボケ"], "裝傻"),)), full_mode=False
        )
        self.assertNotIn("〔藝人/組合〕", only_others)
        self.assertIn("〔節目/單元/品牌/術語〕", only_others)

        only_talents = format_fixed_glossary_block(
            G(U(None, [(["ヤス"], "Yasu")])), full_mode=False
        )
        self.assertIn("〔藝人/組合〕", only_talents)
        self.assertNotIn("〔節目/單元/品牌/術語〕", only_talents)


if __name__ == "__main__":
    unittest.main()

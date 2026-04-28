import unittest

from services.ytdlp.info import (
    _parse_abema_casts_response,
    _parse_tver_talents_response,
)


class YtDlpInfoTests(unittest.TestCase):
    def test_parse_tver_talents_response_normalizes_roles(self):
        talents = _parse_tver_talents_response(
            {
                "talents": [
                    {
                        "id": "t001",
                        "name": "小栗　有以",
                        "name_kana": "オグリ　ユイ",
                        "genre1": "アイドル",
                        "genre2": "",
                        "genre3": "俳優",
                        "thumbnail_path": "/images/t001.jpg",
                    }
                ]
            }
        )

        self.assertEqual(len(talents), 1)
        self.assertEqual(talents[0].id, "t001")
        self.assertEqual(talents[0].name, "小栗　有以")
        self.assertEqual(talents[0].roles, ["アイドル", "俳優"])

    def test_parse_abema_casts_response_assigns_section_roles(self):
        talents = _parse_abema_casts_response(
            {
                "credit": {
                    "casts": [
                        "■MC",
                        "千鳥",
                        "■ゲスト",
                        "渡部健（アンジャッシュ）",
                    ]
                }
            },
            "90-979_s1_p359",
        )

        self.assertEqual(len(talents), 2)
        self.assertEqual(talents[0].name, "千鳥")
        self.assertEqual(talents[0].roles, ["MC"])
        self.assertEqual(talents[1].name, "渡部健（アンジャッシュ）")
        self.assertEqual(talents[1].roles, ["ゲスト"])


if __name__ == "__main__":
    unittest.main()

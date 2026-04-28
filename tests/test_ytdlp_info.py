import unittest

from services.ytdlp.info import _parse_tver_talents_response


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


if __name__ == "__main__":
    unittest.main()

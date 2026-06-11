"""Tests del fallback de Instagram (parser y selección de formatos)."""

import unittest

from app.instagram_fallback import (
    _parse_title,
    _shortcode,
    extract_info,
    parse_video_versions,
)

# Estructura real observada en el DOM renderizado por Chrome headless:
# video_versions con types 101/102/103 y URLs JSON-escapadas del CDN.
DOM_FIXTURE = r"""
<html><head>
<meta property="og:title" content="La Huerta | Huerto en Instagram: &quot;Hoy toca poda&quot;"/>
<meta property="og:image" content="https://scontent-mad1-1.cdninstagram.com/v/thumb.jpg"/>
</head><body>
<script>{"video_versions":[
{"type":101,"url":"https:\/\/scontent-mad1-1.cdninstagram.com\/o1\/v\/t2\/f2\/m86\/alta.mp4?efg=abc"},
{"type":102,"url":"https:\/\/scontent-mad1-1.cdninstagram.com\/o1\/v\/t2\/f2\/m86\/alta.mp4?efg=abc"},
{"type":103,"url":"https:\/\/scontent-mad2-1.cdninstagram.com\/o1\/v\/t2\/f2\/m78\/baja.mp4?efg=xyz"}
],"username":"mi_huerto_eco"}</script>
</body></html>
"""


class TestParseVideoVersions(unittest.TestCase):
    def test_extracts_and_dedupes_by_url(self):
        versions = parse_video_versions(DOM_FIXTURE)
        # types 101 y 102 comparten URL: debe quedar solo el 101 + el 103
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["type"], 101)
        self.assertIn("alta.mp4", versions[0]["url"])
        self.assertEqual(versions[1]["type"], 103)
        self.assertIn("baja.mp4", versions[1]["url"])

    def test_urls_are_unescaped(self):
        versions = parse_video_versions(DOM_FIXTURE)
        self.assertTrue(versions[0]["url"].startswith("https://scontent-"))
        self.assertNotIn("\\/", versions[0]["url"])

    def test_empty_dom(self):
        self.assertEqual(parse_video_versions(""), [])
        self.assertEqual(parse_video_versions("<html>login</html>"), [])

    def test_malformed_json_is_skipped(self):
        dom = '"video_versions":[{"type":101,"url":}]'
        self.assertEqual(parse_video_versions(dom), [])


class TestMetadata(unittest.TestCase):
    def test_title_from_og(self):
        title = _parse_title(DOM_FIXTURE)
        self.assertIn("La Huerta", title)
        self.assertIn('"Hoy toca poda"', title)  # entidades HTML decodificadas

    def test_title_fallback_username(self):
        dom = '{"username":"alguien"}'
        self.assertEqual(_parse_title(dom), "Vídeo de @alguien")

    def test_shortcode(self):
        self.assertEqual(
            _shortcode("https://www.instagram.com/reel/DZKa4LXMSqE/?utm_source=x"),
            "DZKa4LXMSqE",
        )
        self.assertEqual(_shortcode("https://instagram.com/p/ABC-_123/"), "ABC-_123")


class TestExtractInfoOffline(unittest.TestCase):
    def test_no_chrome_returns_none(self):
        import app.instagram_fallback as mod

        original = mod.find_chrome
        mod.find_chrome = lambda: None
        try:
            self.assertIsNone(extract_info("https://www.instagram.com/reel/X/"))
        finally:
            mod.find_chrome = original


if __name__ == "__main__":
    unittest.main()

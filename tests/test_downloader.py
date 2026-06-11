"""Tests del mapeo de errores y de la exposición de URLs directas."""

import unittest

from app.downloader import _map_yt_dlp_error, _progressive_formats

# Formato progresivo como lo devuelve el extractor de twitter de yt-dlp
TWITTER_FORMAT = {
    "format_id": "http-2176",
    "ext": "mp4",
    "protocol": "https",
    "height": 720,
    "filesize": 1234567,
    "url": "https://video.twimg.com/amplify_video/1/vid/avc1/1280x720/x.mp4",
}


class TestMapError(unittest.TestCase):
    def test_forbidden_maps_to_honest_403(self):
        exc = Exception("unable to download video data: HTTP Error 403: Forbidden")
        err = _map_yt_dlp_error(exc)
        self.assertEqual(err.status_code, 403)
        self.assertIn("bloqueado", err.message)

    def test_login_still_wins_over_forbidden(self):
        # El caso de Instagram "login required" debe seguir disparando el
        # mensaje de cookies (y el fallback), no el de IP bloqueada
        exc = Exception("HTTP Error 403: Forbidden. You need to login to access")
        err = _map_yt_dlp_error(exc)
        self.assertIn("cookies", err.message.lower())

    def test_generic_fallthrough_unchanged(self):
        err = _map_yt_dlp_error(Exception("something exotic happened"))
        self.assertEqual(err.status_code, 422)

    def test_403_inside_tweet_id_not_misclassified(self):
        # Los snowflakes de 19 dígitos contienen "403" en ~1,7% de los casos;
        # un "no video" con ese ID no debe mapearse al error de IP bloqueada
        exc = Exception(
            "ERROR: [twitter] 1940312403998765432: "
            "No video could be found in this tweet"
        )
        err = _map_yt_dlp_error(exc)
        self.assertEqual(err.status_code, 422)
        self.assertIn("no contiene", err.message)


class TestProgressiveFormats(unittest.TestCase):
    def test_direct_url_included_when_requested(self):
        fmts = _progressive_formats({"formats": [TWITTER_FORMAT]}, include_direct_url=True)
        self.assertEqual(fmts[0]["direct_url"], TWITTER_FORMAT["url"])

    def test_direct_url_omitted_by_default(self):
        fmts = _progressive_formats({"formats": [TWITTER_FORMAT]})
        self.assertNotIn("direct_url", fmts[0])

    def test_streaming_formats_still_filtered(self):
        hls = dict(TWITTER_FORMAT, format_id="hls-1", protocol="m3u8_native")
        fmts = _progressive_formats({"formats": [hls]}, include_direct_url=True)
        self.assertEqual(fmts, [])


if __name__ == "__main__":
    unittest.main()

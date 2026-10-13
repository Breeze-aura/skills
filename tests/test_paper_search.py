"""Regression tests for retrieval, filtering, persistence, and metadata output.

Transport doubles replace only external API responses. All parsing, routing,
sorting, filtering, formatting, and file writes run through the real script.
"""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error


SCRIPT = Path(__file__).resolve().parents[1] / "skills/paper-search/scripts/search_papers.py"
spec = importlib.util.spec_from_file_location("paper_search_under_test", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


def paper(title="Sample Paper", year=2024, citations=7, url="https://example.org/paper", doi=None):
    return {
        "paperId": None, "title": title, "authors": [{"name": "Test Author"}],
        "year": year, "abstract": "Synthetic abstract for transport tests.",
        "venue": "Test Journal", "url": url, "citationCount": citations,
        "externalIds": {"DOI": doi} if doi else {},
    }


ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>https://arxiv.org/abs/1801.00001v1</id><title>Old paper</title>
<published>2018-01-01T00:00:00Z</published><author><name>A Author</name></author>
<summary>Old synthetic abstract.</summary></entry>
<entry><id>https://arxiv.org/abs/2401.00001v1</id><title>New paper</title>
<published>2024-01-01T00:00:00Z</published><author><name>B Author</name></author>
<summary>New synthetic abstract.</summary><arxiv:doi>10.1234/example</arxiv:doi></entry></feed>'''


class PaperSearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_year_filter_survives_arxiv_fallback(self):
        def transport(request, **kwargs):
            if "semanticscholar.org" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", {}, None)
            return Response(ATOM)
        with patch.object(module.urllib.request, "urlopen", side_effect=transport), patch.object(module.time, "sleep"), redirect_stderr(io.StringIO()):
            papers, source = module.search("EEG microstate", year_from=2020)
        self.assertEqual([p["title"] for p in papers], ["New paper"])
        self.assertIn("arXiv", source)

    def test_arxiv_error_entry_is_not_a_paper(self):
        error_feed = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/api/errors#incorrect_id_format</id><title>Error</title>
<summary>Bad query syntax</summary></entry></feed>'''
        with patch.object(module.urllib.request, "urlopen", return_value=Response(error_feed)):
            papers, error = module.arxiv_search("EEG")
        self.assertIsNone(papers)
        self.assertIsNotNone(error)

    def test_same_batch_duplicates_are_saved_once(self):
        target = self.root / "reading_list.md"
        with redirect_stdout(io.StringIO()):
            module.save_to_list([paper(), paper()], target, "EEG")
        self.assertEqual(target.read_text(encoding="utf-8").count("《Sample Paper》"), 1)

    def test_substring_titles_remain_distinct(self):
        target = self.root / "reading_list.md"
        target.write_text("- 《Brain Networks》(2024) https://example.org/one\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            module.save_to_list([paper("Brain", url="https://example.org/two")], target, "EEG")
        self.assertIn("《Brain》", target.read_text(encoding="utf-8"))

    def test_doi_identity_survives_title_changes(self):
        target = self.root / "reading_list.md"
        with redirect_stdout(io.StringIO()):
            module.save_to_list([paper("Initial Title", doi="10.1234/ABC")], target, "EEG")
            module.save_to_list([paper("Corrected Title", url="https://example.org/new", doi="https://doi.org/10.1234/abc")], target, "EEG")
        self.assertEqual(target.read_text(encoding="utf-8").count("- 《"), 1)

    def test_different_dois_with_identical_titles_are_preserved(self):
        target = self.root / "reading_list.md"
        with redirect_stdout(io.StringIO()):
            module.save_to_list([paper(doi="10.1234/one"), paper(doi="10.1234/two", url="https://example.org/two")], target, "EEG")
        self.assertEqual(target.read_text(encoding="utf-8").count("- 《"), 2)

    def test_invalid_limit_is_rejected_before_search(self):
        for limit in (0, -1, 101):
            with self.subTest(limit=limit):
                with patch.object(module.urllib.request, "urlopen", side_effect=RuntimeError("unexpected transport call")), patch.object(module.time, "sleep"), redirect_stderr(io.StringIO()):
                    with self.assertRaises(ValueError):
                        module.search("EEG", limit=limit)

    def test_permanent_http_error_does_not_sleep_or_retry(self):
        calls = []
        def transport(request, **kwargs):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 400, "Bad request", {}, None)
        delays = []
        with patch.object(module.urllib.request, "urlopen", side_effect=transport), patch.object(module.time, "sleep", side_effect=delays.append):
            papers, error = module.s2s_search("EEG")
        self.assertIsNone(papers)
        self.assertIsNotNone(error)
        self.assertEqual(len(calls), 1)
        self.assertEqual(delays, [])

    def test_retries_are_bounded_without_final_sleep(self):
        calls = []
        def transport(request, **kwargs):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 429, "Slow down", {"Retry-After": "1"}, None)
        delays = []
        with patch.object(module.urllib.request, "urlopen", side_effect=transport), patch.object(module.time, "sleep", side_effect=delays.append):
            papers, error = module.s2s_search("EEG")
        self.assertIsNone(papers)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(delays), 2)

    def test_citation_sort_places_zero_before_unknown(self):
        payload = {"data": [paper("Unknown", citations=None), paper("Zero", citations=0), paper("High", citations=8)]}
        with patch.object(module.urllib.request, "urlopen", return_value=Response(json.dumps(payload).encode())):
            papers, source = module.search("EEG", sort="citations")
        self.assertEqual([p["title"] for p in papers], ["High", "Zero", "Unknown"])
        self.assertIsNone(papers[-1]["citationCount"])

    def test_json_output_preserves_metadata_only_status(self):
        output = io.StringIO()
        with patch.object(module, "search", return_value=([paper(citations=None)], "Semantic Scholar")), patch.object(module.sys, "argv", [str(SCRIPT), "--query", "EEG", "--format", "json"]), redirect_stdout(output), redirect_stderr(io.StringIO()):
            module.main()
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["source"], "Semantic Scholar")
        self.assertEqual(payload["verification_status"], "metadata_only")
        self.assertIsNone(payload["papers"][0]["citationCount"])
        self.assertTrue(payload["retrieved_at"])

    def test_json_save_does_not_mix_status_text_into_stdout(self):
        output = io.StringIO()
        target = self.root / "reading_list.md"
        with patch.object(module, "search", return_value=([paper()], "Semantic Scholar")), patch.object(module.sys, "argv", [str(SCRIPT), "--query", "EEG", "--format", "json", "--save", "--save-path", str(target)]), redirect_stdout(output), redirect_stderr(io.StringIO()):
            module.main()
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["papers"][0]["title"], "Sample Paper")
        self.assertTrue(target.is_file())

    def test_truncated_s2_response_retries_then_falls_back(self):
        class Truncated(Response):
            def read(self):
                raise http.client.IncompleteRead(b"partial", 100)
        def transport(request, **kwargs):
            return Truncated(b"") if "semanticscholar.org" in request.full_url else Response(ATOM)
        with patch.object(module.urllib.request, "urlopen", side_effect=transport), patch.object(module.time, "sleep"), redirect_stderr(io.StringIO()):
            papers, source = module.search("EEG", year_from=2020)
        self.assertEqual(source, "arXiv")
        self.assertEqual([p["title"] for p in papers], ["New paper"])

    def test_truncated_arxiv_response_is_a_service_error(self):
        class Truncated(Response):
            def read(self):
                raise http.client.IncompleteRead(b"partial", 100)
        with patch.object(module.urllib.request, "urlopen", return_value=Truncated(b"")):
            papers, error = module.arxiv_search("EEG")
        self.assertIsNone(papers)
        self.assertIsInstance(error, http.client.IncompleteRead)

    def test_enriched_identity_is_preserved_across_save_calls(self):
        target = self.root / "reading_list.md"
        first = paper(url="https://www.semanticscholar.org/paper/s2-example")
        first["paperId"] = "s2-example"
        enriched = dict(first, externalIds={"DOI": "10.1234/enriched", "ArXiv": "2401.00001v1"})
        arxiv = paper(url="https://arxiv.org/abs/2401.00001v2", doi="10.1234/enriched")
        arxiv["externalIds"]["ArXiv"] = "2401.00001v2"
        with redirect_stdout(io.StringIO()):
            additions = [module.save_to_list([record], target, "EEG") for record in (first, enriched, arxiv)]
        self.assertEqual(additions, [1, 0, 0])
        self.assertEqual(target.read_text(encoding="utf-8").count("- 《"), 1)

    def test_null_author_name_does_not_crash_text_cli(self):
        record = paper()
        record["authors"] = [{"name": None}]
        response = Response(json.dumps({"data": [record]}).encode())
        output = io.StringIO()
        with patch.object(module.urllib.request, "urlopen", return_value=response), patch.object(module.sys, "argv", [str(SCRIPT), "--query", "EEG"]), redirect_stdout(output):
            result = module.main()
        self.assertEqual(result, 0)
        self.assertIn("unknown", output.getvalue())

    def test_failed_list_commit_preserves_existing_notes(self):
        target = self.root / "reading_list.md"
        original = "# My reading notes\nKeep this personal note.\n"
        target.write_text(original, encoding="utf-8")
        with patch.object(module.os, "replace", side_effect=PermissionError("commit blocked")), redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                module.save_to_list([paper()], target, "EEG")
        self.assertEqual(target.read_text(encoding="utf-8"), original)
        self.assertEqual([p.name for p in self.root.iterdir()], ["reading_list.md"])

    def test_cli_uses_utf8_even_when_pipe_encoding_is_ascii(self):
        record = paper("测试论文 🧠")
        data = json.dumps({"data": [record]}).encode()
        code = (
            "import io, runpy, sys; from unittest.mock import patch; "
            f"sys.argv = [{str(SCRIPT)!r}, '--query', 'EEG', '--format', 'json']; "
            f"response = io.BytesIO({data!r}); "
            "mock = patch('urllib.request.urlopen', return_value=response); "
            f"mock.start(); runpy.run_path({str(SCRIPT)!r}, run_name='__main__')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], env=dict(os.environ, PYTHONIOENCODING="ascii"),
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["papers"][0]["title"], "测试论文 🧠")


if __name__ == "__main__":
    unittest.main()

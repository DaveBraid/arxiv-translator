import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


download = load_module("download", ROOT / "arxiv-translator" / "scripts" / "download.py")
compile_script = load_module("compile_script", ROOT / "arxiv-translator" / "scripts" / "compile.py")


class PaperLibraryPathTests(unittest.TestCase):
    def test_resolve_paper_dir_reuses_existing_arxiv_id_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            existing = library / "2501.12948v2 - Old Title"
            existing.mkdir()

            resolved = download.resolve_paper_dir(str(library), "2501.12948v2", "New Title")

            self.assertEqual(Path(resolved), existing)

    def test_resolve_paper_dir_uses_arxiv_id_and_sanitized_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            resolved = download.resolve_paper_dir(str(tmp), "2501.12948v2", "A/B: 🤖 Test Paper")

            self.assertEqual(Path(resolved).name, "2501.12948v2 - A-B_ Test Paper")

    def test_pdf_name_replaces_abbreviation_colon_with_brackets(self):
        pdf_name = download.pdf_name_from_title("RMA: Rapid Motor Adaptation", "fallback")

        self.assertEqual(pdf_name, "【RMA】Rapid Motor Adaptation")

    def test_pdf_name_replaces_camel_case_prefix_colon_with_brackets(self):
        pdf_name = download.pdf_name_from_title(
            "DayDreamer: World Models for Physical Robot Learning",
            "fallback",
        )

        self.assertEqual(pdf_name, "【DayDreamer】World Models for Physical Robot Learning")

    def test_pdf_name_keeps_plain_word_colon_as_sanitized_separator(self):
        pdf_name = download.pdf_name_from_title("Understanding: A Survey", "fallback")

        self.assertEqual(pdf_name, "Understanding_ A Survey")

    def test_download_env_round_trip_uses_single_paper_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            paper_dir = Path(tmp) / "2501.12948v2 - Test Paper"
            work_dir = paper_dir / ".tmp_arxiv" / "2501.12948v2"
            work_dir.mkdir(parents=True)

            download.write_download_env(
                str(paper_dir),
                paper_id="2501.12948v2",
                work_dir=str(work_dir),
                main_tex="main.tex",
                pdf_name="Test Paper",
            )

            work_arg, main_arg, pdf_arg = compile_script.paper_dir_compile_args(str(paper_dir))

            self.assertEqual(Path(work_arg), work_dir)
            self.assertEqual(main_arg, "main.tex")
            self.assertEqual(Path(pdf_arg), paper_dir / "2501.12948v2 - Test Paper.pdf")


if __name__ == "__main__":
    unittest.main()

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
cleanup_script = load_module("cleanup_script", ROOT / "arxiv-translator" / "scripts" / "cleanup.py")


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

    def test_cleanup_removes_managed_local_work_and_metadata_but_keeps_pdfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            paper_dir = Path(tmp) / "2501.12948v2 - Test Paper"
            paper_dir.mkdir()
            local_work = Path(download.create_local_work_dir("2501.12948v2"))
            (local_work / "main.tex").write_text("translated", encoding="utf-8")
            download.write_download_env(
                str(paper_dir),
                paper_id="2501.12948v2",
                work_dir=str(local_work),
                main_tex="main.tex",
                pdf_name="Test Paper",
                local_work_dir=str(local_work),
            )
            en_pdf = paper_dir / f"{paper_dir.name}.en.pdf"
            zh_pdf = paper_dir / f"{paper_dir.name}.zh.pdf"
            en_pdf.write_bytes(b"en")
            zh_pdf.write_bytes(b"zh")

            cleanup_script.cleanup(str(paper_dir))

            self.assertFalse(local_work.exists())
            self.assertFalse((paper_dir / "download.env").exists())
            self.assertEqual(sorted(path.name for path in paper_dir.iterdir()), [en_pdf.name, zh_pdf.name])

    def test_publish_moves_staged_pdf_to_final_zh_name(self):
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
            _, _, staged_pdf, final_pdf = compile_script.paper_dir_staged_compile_args(str(paper_dir))
            Path(staged_pdf).write_bytes(b"%PDF-staged")

            published = compile_script.publish_staged_pdf(str(paper_dir))

            self.assertEqual(Path(published), Path(final_pdf))
            self.assertEqual(Path(final_pdf).read_bytes(), b"%PDF-staged")

    def test_cleanup_refuses_unmanaged_local_work_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            paper_dir = Path(tmp) / "2501.12948v2 - Test Paper"
            unmanaged = Path(tmp) / "unmanaged"
            unmanaged.mkdir()
            download.write_download_env(
                str(paper_dir),
                paper_id="2501.12948v2",
                work_dir=str(unmanaged),
                main_tex="main.tex",
                pdf_name="Test Paper",
                local_work_dir=str(unmanaged),
            )

            cleanup_script.cleanup(str(paper_dir))

            self.assertTrue(unmanaged.exists())
            self.assertTrue((paper_dir / "download.env").exists())


if __name__ == "__main__":
    unittest.main()

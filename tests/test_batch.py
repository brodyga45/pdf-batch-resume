"""Integration checks using generated documents, never customer PDFs."""
import csv
import hashlib
import json
import os
import random
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pdfbatch


def pdf(path, image=False, form=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(595, 842), pageCompression=0)
    c.setFont("Helvetica", 18)
    c.drawString(42, 795, "Synthetic batch fixture - page 1")
    if image:
        # Reproducible synthetic chart with fine labels and coloured geometry.
        noise = Image.frombytes("L", (2400, 3000), random.Random(7).randbytes(2400 * 3000)).convert("RGB")
        im = Image.blend(Image.new("RGB", noise.size, "white"), noise, 0.15)
        draw = ImageDraw.Draw(im)
        for y in range(0, 3000, 8):
            draw.line((0, y, 2400, y), fill=(y % 255, (y * 3) % 255, 190), width=3)
        for x in range(100, 2300, 200):
            draw.rectangle((x, 100, x + 90, 2800), outline="black", width=3)
        im_path = path.with_suffix(".png")
        im.save(im_path)
        c.drawImage(str(im_path), 42, 80, width=510, height=638)
        im_path.unlink()
    else:
        c.drawString(42, 750, "Text remains searchable: 0123456789")
    if form:
        c.acroForm.textfield(name="example", x=42, y=680, width=200, height=25)
    c.showPage()
    c.save()


class BatchIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.src = self.base / "input"
        self.out = self.base / "output"
        self.src.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *extra):
        p = subprocess.run([sys.executable, str(ROOT / "pdfbatch.py"), str(self.src), str(self.out), *extra],
                           text=True, capture_output=True, timeout=40)
        reports = sorted(self.out.glob("batch-report-*.json"), key=lambda f: f.stat().st_mtime_ns)
        return p, json.loads(reports[-1].read_text(encoding="utf-8")) if reports else None

    def test_compression_original_hashes_and_exact_resume(self):
        original = self.src / "nested" / "chart.PDF"
        pdf(original, image=True)
        before = pdfbatch.digest(original)
        p, report = self.run_cli()
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        target = self.out / "nested" / "chart.PDF"
        self.assertEqual(before, pdfbatch.digest(original))
        self.assertLess(target.stat().st_size, original.stat().st_size)
        self.assertEqual(PdfReader(original).pages[0].extract_text(), PdfReader(target).pages[0].extract_text())
        saved = pdfbatch.digest(target)
        p, report = self.run_cli("--resume")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(report["files"][0]["status"], "resumed")
        self.assertEqual(saved, pdfbatch.digest(target))

    def test_corruption_does_not_stop_next_file(self):
        (self.src / "a-broken.pdf").write_bytes(b"not a PDF")
        pdf(self.src / "b-valid.pdf")
        p, report = self.run_cli()
        self.assertEqual(p.returncode, 2)
        self.assertEqual((report["completed"], report["need_review"]), (1, 1))
        self.assertTrue((self.out / "b-valid.pdf").exists())
        self.assertFalse((self.out / "a-broken.pdf").exists())
        self.assertEqual(report["completed_input_bytes"], (self.src / "b-valid.pdf").stat().st_size)

    def test_existing_output_changed_source_and_tampering_never_overwritten(self):
        pdf(self.src / "a.pdf")
        p, _ = self.run_cli()
        self.assertEqual(p.returncode, 0)
        before = (self.out / "a.pdf").read_bytes()
        with (self.src / "a.pdf").open("ab") as stream:
            stream.write(b"\n% source changed\n")
        p, report = self.run_cli("--resume")
        self.assertEqual(p.returncode, 2)
        self.assertEqual((self.out / "a.pdf").read_bytes(), before)
        (self.out / "a.pdf").write_bytes(b"manual output")
        p, _ = self.run_cli("--resume")
        self.assertEqual(p.returncode, 2)
        self.assertEqual((self.out / "a.pdf").read_bytes(), b"manual output")

    def test_forms_annotations_encryption_skipped(self):
        pdf(self.src / "form.pdf", form=True)
        pdf(self.src / "normal.pdf")
        w = PdfWriter(clone_from=self.src / "normal.pdf")
        w.encrypt("test-only-password")
        w.write(self.src / "encrypted.pdf")
        p, report = self.run_cli()
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertEqual(report["need_review"], 2)
        self.assertFalse((self.out / "form.pdf").exists())
        self.assertFalse((self.out / "encrypted.pdf").exists())
        self.assertTrue((self.out / "normal.pdf").exists())

    def test_timeout_is_reported_and_no_partial_output(self):
        pdf(self.src / "a.pdf")
        pdf(self.src / "b.pdf")
        # A real OS timeout of actual worker processes, not a mocked result.
        p, report = self.run_cli("--timeout", "0.00001")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(report["need_review"], 2)
        self.assertTrue(all("timeout" in r["reason"] for r in report["files"]))
        self.assertEqual(list(self.out.glob("*.pdf")), [])
        p, report = self.run_cli("--resume")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(report["completed"], 2)

    def test_no_larger_output_in_lossless_mode(self):
        pdf(self.src / "a.pdf")
        p, report = self.run_cli("--lossless")
        self.assertEqual(p.returncode, 0)
        self.assertLessEqual((self.out / "a.pdf").stat().st_size, (self.src / "a.pdf").stat().st_size)
        self.assertEqual(report["files"][0]["images_reencoded"], 0)

    def test_page_order_crop_rotation_and_unicode_name(self):
        pdf(self.src / "seed.pdf")
        reader = PdfReader(self.src / "seed.pdf")
        writer = PdfWriter()
        for i in range(3):
            page = writer.add_page(reader.pages[0])
            page.rotate(90 if i == 1 else 0)
            page.cropbox.upper_right = (550 - i * 10, 800)
        original = self.src / "извештај 03.pdf"
        writer.write(original)
        expected = [(tuple(p.cropbox), p.rotation, p.extract_text()) for p in PdfReader(original).pages]
        p, _ = self.run_cli()
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        observed = [(tuple(p.cropbox), p.rotation, p.extract_text())
                    for p in PdfReader(self.out / original.name).pages]
        self.assertEqual(expected, observed)

    def test_overlap_refused(self):
        pdf(self.src / "a.pdf")
        self.out = self.src / "nested-output"
        p, _ = self.run_cli()
        self.assertEqual(p.returncode, 1)
        self.assertFalse(self.out.exists())

    def test_legacy_console_unicode_paths_do_not_stop_queue(self):
        name = "извештај 😀.pdf"
        pdf(self.src / name)
        pdf(self.src / "z-after.pdf")
        before = pdfbatch.digest(self.src / name)
        env = dict(os.environ, PYTHONIOENCODING="ascii:strict")
        command = [sys.executable, str(ROOT / "pdfbatch.py"), str(self.src), str(self.out)]
        first = subprocess.run(command, env=env, capture_output=True, timeout=40)
        self.assertEqual(first.returncode, 0, first.stderr.decode("ascii"))
        self.assertIn(b"\\u0438", first.stdout)
        self.assertTrue((self.out / name).is_file())
        self.assertTrue((self.out / "z-after.pdf").is_file())
        self.assertEqual(before, pdfbatch.digest(self.src / name))
        report = json.loads(max(self.out.glob("batch-report-*.json"),
                                key=lambda p: p.stat().st_mtime_ns).read_text(encoding="utf-8"))
        self.assertEqual(report["completed"], 2)
        self.assertIn(name, [row["path"] for row in report["files"]])
        resumed = subprocess.run(command + ["--resume"], env=env, capture_output=True, timeout=40)
        self.assertEqual(resumed.returncode, 0, resumed.stderr.decode("ascii"))
        self.assertEqual(resumed.stdout.count(b"resumed:"), 2)

    def test_symlink_output_does_not_create_outside_directories(self):
        pdf(self.src / "linked" / "new" / "a.pdf")
        self.out.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        (self.out / "linked").symlink_to(outside, target_is_directory=True)
        p, report = self.run_cli()
        self.assertEqual(p.returncode, 2)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlink_and_csv_formula(self):
        pdf(self.src / "=SUM(1,2).pdf")
        (self.src / "linked.pdf").symlink_to(self.src / "=SUM(1,2).pdf")
        p, report = self.run_cli()
        self.assertEqual(p.returncode, 2)
        self.assertEqual(report["completed"], 1)
        with next(self.out.glob("*.csv")).open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows[0]["path"].startswith("'="))
        self.assertFalse((self.out / "linked.pdf").exists())

    def test_lock_and_untracked_existing_file(self):
        pdf(self.src / "a.pdf")
        self.out.mkdir()
        with pdfbatch.output_lock(self.out):
            p, _ = self.run_cli()
            self.assertEqual(p.returncode, 1)
        (self.out / "a.pdf").write_bytes(b"existing")
        p, report = self.run_cli()
        self.assertEqual(p.returncode, 2)
        self.assertEqual((self.out / "a.pdf").read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Actual Tk window/start/worker/report/continue integration, when a display exists."""
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pdfbatch
import pdfbatch_gui
from test_batch import pdf


class DesktopWindowIntegration(unittest.TestCase):
    def test_start_report_and_continue_in_real_window(self):
        if sys.platform == "darwin" and not os.environ.get("PDFBATCH_REQUIRE_GUI"):
            self.skipTest("Native macOS UI is not exercised by the local automated suite")
        try:
            import tkinter as tk
            root = tk.Tk()
        except (ImportError, RuntimeError) as exc:
            if os.environ.get("PDFBATCH_REQUIRE_GUI"):
                raise
            self.skipTest(str(exc))
        except Exception as exc:
            if os.environ.get("PDFBATCH_REQUIRE_GUI"):
                raise
            self.skipTest("Desktop unavailable: " + str(exc))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Originals - извештаји"
            output = Path(directory) / "Compressed"
            source.mkdir()
            valid = source / "b-извештај.pdf"
            pdf(valid)
            (source / "a-broken.pdf").write_bytes(b"not a PDF")
            original_hash = pdfbatch.digest(valid)
            app = pdfbatch_gui.create_window(root)

            def wait_for_batch():
                deadline = time.monotonic() + 25
                while app.last_code is None and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.02)
                self.assertIsNotNone(app.last_code, "Window did not receive the real worker result")
                root.update()

            try:
                root.update()
                self.assertFalse(output.exists(), "Opening the window must not start processing")
                app.source.set(str(source))
                app.output.set(str(output))
                app.mode.set("lossless")
                app.start_button.invoke()
                self.assertTrue(app.start_button.instate(["disabled"]))
                wait_for_batch()
                self.assertEqual(app.last_code, 2)
                self.assertIn("1 need review", app.status.get())
                report_path = Path(app.report.get())
                self.assertTrue(report_path.is_file())
                report = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual((report["completed"], report["need_review"]), (1, 1))
                self.assertEqual(pdfbatch.digest(valid), original_hash)
                output_hash = pdfbatch.digest(output / valid.name)
                self.assertTrue(app.start_button.instate(["!disabled"]))
                self.assertTrue(app.stop_button.instate(["disabled"]))
                qa = ROOT / "qa"
                qa.mkdir(exist_ok=True)
                evidence = {"platform": platform.platform(), "python": sys.version,
                            "Tk": tk.TkVersion, "scenario": "Real window Start -> damaged and valid PDF -> visible report -> Continue",
                            "first_exit": app.last_code, "first_status": app.status.get(),
                            "original_unchanged": True, "customer_files": False,
                            "native_folder_picker_exercised": False,
                            "physical_Windows10_or_11": False}
                try:
                    from PIL import ImageGrab
                    box = (root.winfo_rootx(), root.winfo_rooty(),
                           root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height())
                    ImageGrab.grab(bbox=box).save(qa / "gui-smoke.png")
                    evidence["screenshot"] = "gui-smoke.png"
                except Exception as exc:
                    evidence["screenshot_unavailable"] = type(exc).__name__ + ": " + str(exc)
                app.start_button.invoke()
                wait_for_batch()
                self.assertEqual(app.last_code, 2)
                self.assertIn("resumed: b-извештај.pdf", app.log.get("1.0", "end"))
                self.assertEqual(pdfbatch.digest(output / valid.name), output_hash)
                evidence["continue_verified"] = True
                (qa / "gui-smoke.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            finally:
                app.stop.set()
                if app.worker is not None:
                    app.worker.join(timeout=10)
                root.destroy()


if __name__ == "__main__":
    unittest.main()

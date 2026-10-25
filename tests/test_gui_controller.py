"""Exercise the graphical entry point against real files and worker processes."""
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pdfbatch
import pdfbatch_gui
from test_batch import pdf


class GraphicalQueueIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = self.base / "Original PDFs - извештаји"
        self.source.mkdir()
        self.output = self.base / "Compressed PDFs"

    def tearDown(self):
        self.temp.cleanup()

    def options(self):
        return pdfbatch_gui.make_options(str(self.source), str(self.output), "lossless", "120")

    def run_controller(self):
        events = queue.Queue()
        thread = threading.Thread(target=pdfbatch_gui.execute,
                                  args=(self.options(), events, threading.Event()))
        thread.start()
        thread.join(timeout=30)
        self.assertFalse(thread.is_alive(), "The graphical controller did not return")
        result = []
        while not events.empty():
            result.append(events.get_nowait())
        return result

    def test_actual_queue_errors_report_and_verified_resume(self):
        (self.source / "a-broken.pdf").write_bytes(b"not a PDF")
        good = self.source / "b-извештај.pdf"
        pdf(good)
        source_hash = pdfbatch.digest(good)
        events = self.run_controller()
        progress = [e for e in events if e["type"] == "progress"]
        self.assertEqual([(e["index"], e["total"]) for e in progress], [(1, 2), (2, 2)])
        self.assertEqual(progress[0]["record"]["status"], "error")
        self.assertIn(progress[1]["record"]["status"], {"compressed", "kept_original"})
        done = next(e for e in events if e["type"] == "finished")
        report = json.loads(Path(done["report"]).read_text(encoding="utf-8"))
        self.assertEqual((report["completed"], report["need_review"]), (1, 1))
        self.assertTrue(Path(done["csv"]).is_file())
        self.assertEqual(events[-1], {"type": "exit", "code": 2})
        self.assertEqual(pdfbatch.digest(good), source_hash)
        output_hash = pdfbatch.digest(self.output / good.name)
        repeated = self.run_controller()
        repeat_progress = [e for e in repeated if e["type"] == "progress"]
        self.assertEqual(repeat_progress[-1]["record"]["status"], "resumed")
        self.assertEqual(pdfbatch.digest(self.output / good.name), output_hash)

    def test_boundary_stop_saves_first_file_then_resumes_remaining(self):
        pdf(self.source / "a.pdf")
        pdf(self.source / "b.pdf")
        stop = threading.Event()
        events = []

        def receive(event):
            events.append(event)
            if event["type"] == "progress":
                stop.set()

        code = pdfbatch.run_batch(self.options(), on_event=receive, stop_requested=stop.is_set)
        self.assertEqual(code, 130)
        self.assertEqual([e["type"] for e in events], ["progress", "stopped"])
        self.assertTrue((self.output / "a.pdf").is_file())
        self.assertFalse((self.output / "b.pdf").exists())
        state = json.loads((self.output / ".pdfbatch-state.json").read_text(encoding="utf-8"))
        self.assertEqual(list(state["files"]), ["a.pdf"])
        output_hash = pdfbatch.digest(self.output / "a.pdf")
        finished = self.run_controller()
        self.assertEqual(finished[-1]["code"], 0)
        final_progress = [e["record"]["status"] for e in finished if e["type"] == "progress"]
        self.assertEqual(final_progress[0], "resumed")
        self.assertIn(final_progress[1], {"compressed", "kept_original"})
        self.assertEqual(pdfbatch.digest(self.output / "a.pdf"), output_hash)

    def test_configuration_error_delivered_without_writing_input(self):
        pdf(self.source / "a.pdf")
        self.output = self.source / "nested"
        before = sorted(p.relative_to(self.source).as_posix() for p in self.source.rglob("*"))
        events = self.run_controller()
        self.assertEqual([e["type"] for e in events], ["error", "exit"])
        self.assertEqual(events[-1]["code"], 1)
        self.assertIn("separate folders", events[0]["message"])
        self.assertEqual(before, sorted(p.relative_to(self.source).as_posix() for p in self.source.rglob("*")))

    def test_paths_are_preserved_and_nonfinite_timeout_rejected(self):
        options = pdfbatch_gui.make_options(" /exact input ", "/exact output ", "balanced", "120")
        self.assertEqual(options.input, " /exact input ")
        self.assertEqual(options.output, "/exact output ")
        for value in ("nan", "inf", "-inf", "0", "oops"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pdfbatch_gui.make_options("a", "b", "balanced", value)


if __name__ == "__main__":
    unittest.main()

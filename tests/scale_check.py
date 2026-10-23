"""Run a synthetic 800-file queue; this is not an 800-document customer trial."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from test_batch import ROOT, pdf

base = ROOT / "qa" / "scale"
source, target = base / "input", base / "output"
source.mkdir(parents=True, exist_ok=False)
pdf(source / "000-scan.pdf", image=True)
pdf(source / "001-text.pdf")
for index in range(2, 800):
    folder = source / f"set-{index // 100}"
    folder.mkdir(exist_ok=True)
    shutil.copyfile(source / "001-text.pdf", folder / f"{index:03}.pdf")
command = [sys.executable, str(ROOT / "pdfbatch.py"), str(source), str(target)]
results = []
for mode in ([], ["--resume"]):
    started = time.monotonic()
    with (base / ("resume.log" if mode else "first.log")).open("w") as stream:
        result = subprocess.run(command + mode, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    reports = sorted(target.glob("batch-report-*.json"), key=lambda f: f.stat().st_mtime_ns)
    report = json.loads(reports[-1].read_text())
    assert result.returncode == 0, reports[-1]
    assert report["completed"] == 800 and report["need_review"] == 0
    if mode:
        assert all(r["status"] == "resumed" for r in report["files"])
    results.append({"mode": "resume" if mode else "first", "elapsed_seconds": round(time.monotonic()-started, 3),
                    "completed": 800, "need_review": 0, "report": reports[-1].name,
                    "completed_input_bytes": report["completed_input_bytes"],
                    "output_bytes": report["output_bytes"], "saved_bytes": report["saved_bytes"]})
    print(json.dumps(results[-1]), flush=True)
(base / "summary.json").write_text(json.dumps(results, indent=2) + "\n")

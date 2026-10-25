# PDF Batch Resume

Compress a folder of image-heavy PDFs, one document at a time. A broken or slow file gets its own report entry; the remaining queue continues. Stop with Ctrl+C and resume completed files using verified hashes. All processing stays on your computer.

Version 0.2.0 adds a desktop folder picker and progress window to the existing Python engine. Choose two folders, start the batch, and see which files need attention. Stop after the active PDF and continue completed work with verified hashes. Compression uses pypdf and Pillow.

## Graphical launch on Windows

Requires Python 3.10 or newer with Tcl/Tk, available from the [official Python Windows downloads](https://www.python.org/downloads/windows/). Keep the whole extracted folder together.

1. Double-click `Setup Windows.cmd` once. It creates a `.venv` in this folder and downloads the pinned packages from PyPI. Wait for **Ready**; setup errors are shown rather than hidden.
2. Double-click `Start Windows.cmd`.
3. Browse for the original PDF folder and a separate output folder. Choose image quality, then **Start / Continue**.

The default smaller-image mode is lossy. Try a few representative copies and inspect small text and diagrams before a large batch. **Keep image pixels** avoids image re-encoding; size savings may be small or zero.

The window shows progress and per-file exceptions. **Stop after current PDF** lets the active PDF and its journal entry finish, then stops. It can take up to the per-file timeout. Closing an active window also waits for that safe stop. Choose the same folders and settings and press **Start / Continue** to verify and reuse completed outputs. Changes or conflicts are reported; files are not silently overwritten.

The JSON and CSV reports are written when the queue finishes. A safely stopped queue keeps its resume journal; continue it to produce a full report. After completion, the report path can be selected/copied from the window, and per-file reasons remain in the log. The GUI runs locally, without a web server or document uploads.

On another Python installation with working Tcl/Tk, the direct entry point is `python pdfbatch_gui.py` after installing `requirements.txt`. macOS GUI execution is not verified. The command-line instructions remain available for Python builds without Tk.

## Install and run

Requires Python 3.10 or newer. Unzip this folder and open a terminal inside it.

Windows:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python pdfbatch.py "C:\Documents\Original PDFs" "C:\Documents\Compressed PDFs"
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python pdfbatch.py "$HOME/Documents/Original PDFs" "$HOME/Documents/Compressed PDFs"
```

Choose a separate output folder, outside the input folder. Subfolders and filenames are retained. No account, upload or Ghostscript installation is needed. Dependency installation downloads packages from PyPI; compression itself has no network operations.

Start with copies of a few representative documents and inspect them before running the whole batch. The default is **lossy**: eligible RGB/greyscale images are re-encoded at JPEG quality 85 and reduced to a maximum edge of 2000 pixels. This is a pixel limit, not a DPI setting. To keep original image pixels, use `--lossless`; its size savings may be small or zero.

```sh
.venv/bin/python pdfbatch.py INPUT OUTPUT --lossless
.venv/bin/python pdfbatch.py INPUT OUTPUT --quality 90 --max-edge 0
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python`.

## Continue an interrupted batch

Run the identical command with `--resume`:

```sh
.venv/bin/python pdfbatch.py INPUT OUTPUT --resume
```

The tool verifies the source hash, options and output hash before skipping a file. Each PDF gets a fresh worker process and a 120-second timeout; adjust it with `--timeout 300` for large documents. Only one batch may use an output folder at a time.

On terminals that cannot display a filename, progress uses escaped characters instead of stopping the queue. The filenames and UTF-8 JSON/CSV reports keep their original Unicode text.

Existing output files are never overwritten. If a source or output changed, or the options differ, use a new output folder or review the conflicting file yourself. A hard OS shutdown during the final copy can leave an untracked partial output; resume reports the conflict for review instead of adopting or replacing it. Ctrl+C saves completed work; the interrupted file is retried.

## Read the result

The output folder contains PDF copies, a hidden resume journal, and timestamped CSV/JSON reports.

| Status | Meaning |
| --- | --- |
| `compressed` | Validated smaller candidate published |
| `kept_original` | Candidate was no smaller; exact original copy published |
| `resumed` | Existing output matched the journal and current source/options |
| `skipped_protected` | Document requires a separate workflow; no output published |
| `error` | File failed, timed out or conflicted; see its reason |

Exit codes: 0 = all complete; 2 = some files need review; 1 = configuration/folder error; 130 = interrupted. `saved_bytes` counts completed files only, so skipped and failed PDFs do not inflate reported savings.

## Document scope

Designed for ordinary image documents. Encrypted PDFs, forms, signatures, annotations (including links), actions and embedded files are deliberately skipped. Inline, transparent, indexed, bilevel and CMYK images may remain unchanged, with a warning. Originals are preserved even if processing fails. Output files are never larger than their corresponding original.

Before publication of an output, page count, page boxes, rotation and extracted text are checked. This is not a guarantee of every PDF feature or visual equivalence. There is no PDF/A, accessibility, signed-document, malware-sandbox or archival certification. Review visible quality in your actual viewer, especially fine scanned text and diagrams. Independent review found a renderer-dependent title display discrepancy on one synthetic sample (Poppler versus PDFium); see `QA.md`. Lossless mode avoids image re-encoding but still rewrites PDF structure.

## Evidence and limits

The included integration tests generate synthetic PDFs and exercise real processing, corruption, protection, timeouts, resume, conflicts, hashes, paths, locking and CSV output. A separate 800-file queue check uses one image-heavy synthetic PDF and 799 small text PDFs (mostly repeated copies). It tests orchestration, not 800 different production documents. The before/after sample was rendered with Poppler and visually inspected.

Version 0.2.0 passed all 17 tests on GitHub-hosted Windows Server 2022 and Ubuntu 24.04, including an actual Tk window processing a damaged and a valid PDF, showing the report, and continuing verified work. See the [checked run](https://github.com/brodyga45/pdf-batch-resume/actions/runs/40184705996) and `QA.md`. Native folder dialogs, clicking Stop/closing the live window, and installation on a physical Windows 10/11 computer were not exercised.

The original checks ran on macOS with Python 3.12.14. Version 0.1.1 also passed 12 integration tests on GitHub-hosted Windows Server 2022 (Python 3.12.10, cp1252) and Ubuntu 24.04 (Python 3.12.15), with pypdf 6.10.0 and Pillow 12.3.0. This checks the command-line engine; a Windows 10/11 desktop installation, the requester's OS and their actual PDFs remain unverified. No customer files were used and no customer result or sale is claimed.

Developers can run `python -m pip install reportlab==4.4.9` and `python -m unittest discover -s tests -v`. `python tests/scale_check.py` creates the synthetic queue under `qa/scale`; use a fresh extracted folder for another scale run.

## Source and reproducible checks

Source and Windows/Linux integration runs: https://github.com/brodyga45/pdf-batch-resume .

## License

The original wrapper and tests are MIT licensed; see `LICENSE`. Third-party dependencies retain their own terms, listed in `THIRD_PARTY_NOTICES.md`. No dependency code or customer PDFs are included in the source download.

# PDF Batch Resume

Compress a folder of image-heavy PDFs, one document at a time. A broken or slow file gets its own report entry; the remaining queue continues. Stop with Ctrl+C and resume completed files using verified hashes. All processing stays on your computer.

This is a Python command-line tool, version 0.1.1. It is useful when a large batch fails and you want separate output copies, progress, and a list of exceptions. It uses pypdf and Pillow, not a new PDF compression algorithm.

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

Actual run details are in `QA.md`. The original checks ran on macOS with Python 3.12.14. Version 0.1.1 also passed 12 integration tests on GitHub-hosted Windows Server 2022 (Python 3.12.10, cp1252) and Ubuntu 24.04 (Python 3.12.15), with pypdf 6.10.0 and Pillow 12.3.0. This checks the command-line engine; a Windows 10/11 desktop installation, the requester's OS and their actual PDFs remain unverified. No customer files were used and no customer result or sale is claimed.

Developers can run `python -m pip install reportlab==4.4.9` and `python -m unittest discover -s tests -v`. `python tests/scale_check.py` creates the synthetic queue under `qa/scale`; use a fresh extracted folder for another scale run.

## Source and reproducible checks

Source and Windows/Linux integration runs: https://github.com/brodyga45/pdf-batch-resume .

## License

The original wrapper and tests are MIT licensed; see `LICENSE`. Third-party dependencies retain their own terms, listed in `THIRD_PARTY_NOTICES.md`. No dependency code or customer PDFs are included in the source download.

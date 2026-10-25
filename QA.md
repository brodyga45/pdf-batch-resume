# Validation, 23 October 2026

- macOS 26.6.1, Python 3.12.14, pypdf 6.10.0, Pillow 12.3.0.
- 11 integration tests passed. See `qa/integration-tests.txt`.
- Actual subprocess queue: 800/800 synthetic PDFs completed, no review entries, 89.002 seconds. One image-heavy chart and 799 small text PDFs, mostly repeated copies. This is not 800 heterogeneous customer documents.
- Hash-verified resume: 800/800 skipped, 7.304 seconds.
- Image sample: 5485463 bytes before, 1146987 after. Pixel resizing and JPEG are lossy; this sample does not establish a general reduction percentage.
- Poppler renders of that sample before/after were inspected: matching page layout, title, bars and chart geometry; expected image colour/detail differences. Poppler emitted local fontconfig cache warnings; both renders completed. No claim of fine scanned-text fidelity follows from this chart.
- Corruption, protected PDFs, real worker timeouts followed by successful retry, existing-output preservation, changed source and tampering, overlap refusal, directory/source symlinks, locking, CSV formula escaping and three-page crop/rotation/text checks passed.
- At this original macOS checkpoint, Windows/Linux runtime, customer OS/documents, extreme memory pressure and abrupt power loss were not tested. The later 0.1.1 CI results below supersede only the Windows/Linux engine-runtime gap. A hard shutdown can leave an untracked output requiring review. No malware-sandbox claim.
- No customer files, accounts, payments or uploads are part of these tests. Original source code is MIT; dependencies are separately licensed.

## Additional fine-print sample and independent review

A second synthetic 300-dpi raster page includes 6/8/10/12-point text, document IDs, amounts and a table on a lightly noisy background. Default settings produced 302,437 bytes from 7,742,515 bytes. Before/after were rendered at150dpi and visually read: all displayed sample lines and numbers remained readable, with expected JPEG softening. This single sample does not establish readability for customer documents.

Rasp independently tested the frozen source archive: a bad middle PDF did not stop a following valid file; verified resume preserved outputs; after replacing the bad input, the queue completed. Original hashes were retained. Rasp observed the chart's title absent in one Poppler rendering environment while PDFium rendered the title in both PDFs; this author's Poppler renders also show it in both. Text/font/content checks did not establish title deletion. Treat this as renderer-dependent uncertainty, not proven universal fidelity or universal corruption. Compare outputs in your actual viewer before trusting a batch.


## Version 0.1.1 — actual Windows/Linux check and Unicode fix

The first public CI run reproduced a real Windows failure: with cp1252 output, printing a Cyrillic filename raised UnicodeEncodeError and stopped the queue. Linux passed all 11 original tests. Source: https://github.com/brodyga45/pdf-batch-resume/actions/runs/40006740826 .

Commit e1cd301c6c51d3aeabde2e6fb7e1057645969de8 keeps the existing stdout/stderr encoding and uses backslash escapes for characters it cannot display. Actual files and UTF-8 reports retain their Unicode names. A real subprocess regression forces ASCII output, processes a Cyrillic/emoji filename and another PDF, verifies the original hash and Unicode report path, and resumes both completed outputs.

The corrected run passed all 12 integration tests on both Windows Server 2022 x64/Python 3.12.10/cp1252 (9.308 seconds) and Ubuntu 24.04 x64/Python 3.12.15 (8.186 seconds). Source: https://github.com/brodyga45/pdf-batch-resume/actions/runs/40006959962 . These timings are for the small generated integration fixtures, not an 800-file workload.

This is hosted command-line engine testing, not proof of a Windows 10/11 desktop installation, an executable installer, customer document quality, or customer acceptance. No customer data was used.


## Version 0.2.0 — graphical launch and progress

The existing engine now has a Tk desktop entry point. GitHub Actions run [40184705996](https://github.com/brodyga45/pdf-batch-resume/actions/runs/40184705996), source `a2fd93db6bd0dcb83e4f5feae500a63d10003e64`, passed all 17 tests on both Windows Server 2022 and Ubuntu 24.04 with Python 3.12. The actual-window test ran on both systems (Linux used Xvfb); it was not skipped.

The real window started a synthetic damaged PDF followed by a valid PDF, displayed the exception and report path, then continued and verified the existing output. Four controller tests also exercised worker events, safe stop between documents with a saved journal, resume, validation, path preservation and report results. Local macOS ran 16 tests with one explicit GUI skip; its GUI is unverified.

Independent review found that the active filename appeared too late and the Windows taskbar obscured the bottom note. The current source emits the filename before hashing/processing and fits the initial window inside the display. Corrected Windows and Ubuntu screenshot/JSON artifacts from this run were downloaded through the connected GitHub tool; their SHA256 and ZIP CRC matched the original metadata. Windows artifact digest: `e659d07bb24ab36ecd050b92d9553b21dff33cb7e18f2793d2940be65d1f23d1`; Ubuntu: `33c7b6b2762bd5b562e5be6d18c59f7befa5ae388bc0d284c02f0642e8c65dc0`. Both bottom lines are visible; Rasp closed the two GUI findings and supported release within these limits.

This is synthetic hosted desktop evidence. The native folder picker, clicking the live Stop button or window close control, physical Windows 10/11 installation and customer PDFs were not exercised. Safe-stop controller/engine tests do not establish those native interactions. The earlier renderer-dependent PDF display uncertainty remains. No new compression algorithm, customer acceptance or sale is claimed.

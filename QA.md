# Validation, 23 October 2026

- macOS 26.6.1, Python 3.12.14, pypdf 6.10.0, Pillow 12.3.0.
- 11 integration tests passed. See `qa/integration-tests.txt`.
- Actual subprocess queue: 800/800 synthetic PDFs completed, no review entries, 89.002 seconds. One image-heavy chart and 799 small text PDFs, mostly repeated copies. This is not 800 heterogeneous customer documents.
- Hash-verified resume: 800/800 skipped, 7.304 seconds.
- Image sample: 5485463 bytes before, 1146987 after. Pixel resizing and JPEG are lossy; this sample does not establish a general reduction percentage.
- Poppler renders of that sample before/after were inspected: matching page layout, title, bars and chart geometry; expected image colour/detail differences. Poppler emitted local fontconfig cache warnings; both renders completed. No claim of fine scanned-text fidelity follows from this chart.
- Corruption, protected PDFs, real worker timeouts followed by successful retry, existing-output preservation, changed source and tampering, overlap refusal, directory/source symlinks, locking, CSV formula escaping and three-page crop/rotation/text checks passed.
- Windows/Linux runtime, customer OS/documents, extreme memory pressure and abrupt power loss were not tested. A hard shutdown can leave an untracked output requiring review. No malware-sandbox claim.
- No customer files, accounts, payments or uploads are part of these tests. Original source code is MIT; dependencies are separately licensed.

## Additional fine-print sample and independent review

A second synthetic 300-dpi raster page includes 6/8/10/12-point text, document IDs, amounts and a table on a lightly noisy background. Default settings produced 302,437 bytes from 7,742,515 bytes. Before/after were rendered at150dpi and visually read: all displayed sample lines and numbers remained readable, with expected JPEG softening. This single sample does not establish readability for customer documents.

Rasp independently tested the frozen source archive: a bad middle PDF did not stop a following valid file; verified resume preserved outputs; after replacing the bad input, the queue completed. Original hashes were retained. Rasp observed the chart's title absent in one Poppler rendering environment while PDFium rendered the title in both PDFs; this author's Poppler renders also show it in both. Text/font/content checks did not establish title deletion. Treat this as renderer-dependent uncertainty, not proven universal fidelity or universal corruption. Compare outputs in your actual viewer before trusting a batch.

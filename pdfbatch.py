#!/usr/bin/env python3
"""Compress image-heavy PDFs one file at a time, preserving every original."""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

TOOL = "PDF Batch Resume"
SCHEMA = 1
SUCCESS = {"compressed", "kept_original", "resumed"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    fd, name = tempfile.mkstemp(prefix=".pdfbatch-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextlib.contextmanager
def output_lock(folder: Path):
    path = folder / ".pdfbatch.lock"
    if path.is_symlink():
        raise ValueError("Output lock must not be a symbolic link")
    with path.open("a+b") as stream:
        try:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("Another batch is using this output folder") from exc
        try:
            stream.seek(0)
            contents = stream.read()
            if contents not in (b"", b"PDF Batch Resume\n"):
                raise ValueError("Unrecognised existing .pdfbatch.lock; choose another output folder")
            if not contents:
                stream.write(b"PDF Batch Resume\n")
                stream.flush()
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def inventory(folder: Path):
    for parent, directories, filenames in os.walk(folder, followlinks=False):
        directories[:] = sorted(d for d in directories if not (Path(parent) / d).is_symlink())
        for name in sorted(filenames):
            path = Path(parent) / name
            if path.suffix.lower() == ".pdf":
                yield path


def worker(job: dict) -> dict:
    # Parsing/decompression happens in this disposable process, not the batch parent.
    from PIL import Image
    from pypdf import PdfReader, PdfWriter

    source = Path(job["source"])
    temporary = Path(job["temporary"])
    reader = PdfReader(source, strict=False)
    if reader.is_encrypted:
        return {"status": "skipped_protected", "reason": "Encrypted PDF; no password requested or bypassed"}
    root = reader.trailer["/Root"]
    names = root.get("/Names")
    names = names.get_object() if names else {}
    if (root.get("/AcroForm") or root.get("/Perms") or root.get("/OpenAction")
            or root.get("/AA") or names.get("/JavaScript") or names.get("/EmbeddedFiles")):
        return {"status": "skipped_protected", "reason": "Forms, signatures, actions or attachments require a separate workflow"}
    if any(page.get("/Annots") for page in reader.pages):
        return {"status": "skipped_protected", "reason": "Annotations/links present; kept out of this image-document workflow"}
    expected = [(tuple(page.mediabox), tuple(page.cropbox), page.rotation, page.extract_text())
                for page in reader.pages]
    writer = PdfWriter(clone_from=reader)
    replaced = 0
    warnings = []
    handled = set()
    for page in writer.pages:
        if not job["lossless"]:
            for name in page.images.keys():
                try:
                    item = page.images[name]
                    reference = item.indirect_reference
                    if reference is None:
                        warnings.append("Inline image retained unchanged")
                        continue
                    key = (reference.idnum, reference.generation)
                    if key in handled:
                        continue
                    handled.add(key)
                    obj = reference.get_object()
                    image = item.image
                    if obj.get("/SMask") or obj.get("/Mask") or image.mode not in ("RGB", "L"):
                        warnings.append("Transparent, indexed, bilevel or CMYK image retained unchanged")
                        continue
                    image.load()
                    maximum = job["max_edge"]
                    if maximum and max(image.size) > maximum:
                        image = image.copy()
                        image.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
                    item.replace(image, quality=job["quality"])
                    replaced += 1
                except Exception as exc:
                    # Keep the entire original file rather than publishing a partially changed PDF.
                    raise ValueError(f"Image could not be processed: {type(exc).__name__}: {exc}") from exc
        page.compress_content_streams(level=9)
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    writer.write(temporary)
    check = PdfReader(temporary)
    observed = [(tuple(page.mediabox), tuple(page.cropbox), page.rotation, page.extract_text())
                for page in check.pages]
    if observed != expected:
        raise ValueError("Page count, geometry, rotation or extracted text changed; output rejected")
    status = "compressed"
    if temporary.stat().st_size >= source.stat().st_size:
        shutil.copyfile(source, temporary)
        status = "kept_original"
    return {"status": status, "pages": len(reader.pages), "images_reencoded": replaced,
            "warnings": sorted(set(warnings))}


def publish_exclusively(temporary: Path, target: Path) -> None:
    # 'xb' is exclusive on both Windows and POSIX; an existing file is never replaced.
    created = False
    try:
        with target.open("xb") as output:
            created = True
            with temporary.open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise


def spreadsheet_cell(value):
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        return "'" + value
    return value


def run_batch(args, *, on_event=None, stop_requested=None) -> int:
    """Run the same queue for CLI or GUI; callbacks run on the calling thread.

    A requested GUI stop is honoured between PDFs, after the current file and
    its journal entry finish. It never terminates a worker during publication.
    """
    source = Path(args.input).expanduser().resolve(strict=True)
    output = Path(args.output).expanduser().resolve()
    if not source.is_dir():
        raise ValueError("Input must be a folder")
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Input and output must be separate folders, neither inside the other")
    files = list(inventory(source))
    if not files:
        raise ValueError("No PDF files found in the selected input folder")
    if importlib.util.find_spec("pypdf") is None or importlib.util.find_spec("PIL") is None:
        raise ValueError("Install dependencies first: python -m pip install -r requirements.txt")
    output.mkdir(parents=True, exist_ok=True)
    options = {"quality": args.quality, "max_edge": args.max_edge, "lossless": args.lossless}
    with output_lock(output):
        state_file = output / ".pdfbatch-state.json"
        state = {"tool": TOOL, "schema": SCHEMA, "files": {}}
        if state_file.is_symlink():
            raise ValueError("State file must not be a symbolic link")
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
            if state.get("tool") != TOOL or state.get("schema") != SCHEMA or not isinstance(state.get("files"), dict):
                raise ValueError("Unrecognised batch state; choose another output folder")
            if not args.resume:
                raise ValueError("This output contains a previous batch. Use --resume or a new output folder")
        records = []
        started = time.monotonic()
        try:
            for index, path in enumerate(files, 1):
                if stop_requested is not None and stop_requested():
                    raise KeyboardInterrupt
                relative = path.relative_to(source).as_posix()
                if on_event is not None:
                    on_event({"type": "processing", "index": index,
                              "total": len(files), "path": relative})
                record = {"path": relative, "options": options, "input_bytes": 0, "output_bytes": 0}
                temporary = None
                try:
                    if path.is_symlink():
                        raise ValueError("Symbolic-link PDF not followed")
                    record["input_bytes"] = path.stat().st_size
                    record["input_sha256"] = digest(path)
                    target = output / path.relative_to(source)
                    # Check before mkdir: an existing directory symlink must not cause
                    # creation of even empty directories outside the output folder.
                    if not target.parent.resolve().is_relative_to(output):
                        raise ValueError("Output path escapes the selected output folder")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_symlink() or not target.parent.resolve().is_relative_to(output):
                        raise ValueError("Output path escapes the selected output folder")
                    previous = state["files"].get(relative, {})
                    can_resume = (args.resume and previous.get("status") in SUCCESS
                                  and previous.get("input_sha256") == record["input_sha256"]
                                  and previous.get("options") == options)
                    if target.exists():
                        if can_resume and target.is_file() and digest(target) == previous.get("output_sha256"):
                            record.update(status="resumed", output_bytes=target.stat().st_size,
                                          output_sha256=previous["output_sha256"])
                        else:
                            raise FileExistsError("Output already exists but does not match verified resume state; never overwritten")
                    else:
                        fd, name = tempfile.mkstemp(prefix=".pdfbatch-", suffix=".pdf", dir=target.parent)
                        os.close(fd)
                        temporary = Path(name)
                        job = dict(options, source=str(path), temporary=str(temporary))
                        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker"],
                                                 input=json.dumps(job), text=True, capture_output=True,
                                                 timeout=args.timeout, check=False)
                        if process.returncode:
                            raise ValueError(f"PDF worker failed (exit {process.returncode}): {process.stderr[-600:].strip()}")
                        result = json.loads(process.stdout)
                        if result["status"] == "error":
                            raise ValueError(result["reason"])
                        record.update(result)
                        if result["status"] in SUCCESS:
                            if digest(path) != record["input_sha256"]:
                                raise ValueError("Input changed during processing; candidate not published")
                            record.update(output_bytes=temporary.stat().st_size, output_sha256=digest(temporary))
                            publish_exclusively(temporary, target)
                    state["files"][relative] = record
                except subprocess.TimeoutExpired:
                    record.update(status="error", reason=f"Exceeded {args.timeout:g}s per-file timeout; batch continues")
                except Exception as exc:
                    record.update(status="error", reason=f"{type(exc).__name__}: {exc}")
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
                records.append(record)
                # Keep successful records available even if a later individual file fails.
                if record.get("status") not in SUCCESS:
                    old = state["files"].get(relative, {})
                    if old.get("status") not in SUCCESS:
                        state["files"][relative] = record
                atomic_json(state_file, state)
                if on_event is None:
                    print(f"[{index}/{len(files)}] {record['status']}: {relative}", flush=True)
                else:
                    on_event({"type": "progress", "index": index,
                              "total": len(files), "record": dict(record)})
        except KeyboardInterrupt:
            if on_event is None:
                print("Stopped. Completed files are saved. Run the same command with --resume.", file=sys.stderr)
            else:
                on_event({"type": "stopped", "completed_records": len(records),
                          "total": len(files)})
            return 130
        stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        summary_path = output / f"batch-report-{stamp}.json"
        review = [record for record in records if record["status"] not in SUCCESS]
        completed = [record for record in records if record["status"] in SUCCESS]
        summary = {"tool": TOOL, "schema": SCHEMA, "options": options, "files_found": len(files),
                   "completed": len(records) - len(review), "need_review": len(review),
                   "input_bytes": sum(record["input_bytes"] for record in records),
                   "output_bytes": sum(record["output_bytes"] for record in records),
                   "completed_input_bytes": sum(record["input_bytes"] for record in completed),
                   "saved_bytes": sum(record["input_bytes"] - record["output_bytes"] for record in completed),
                   "elapsed_seconds": round(time.monotonic() - started, 3), "files": records}
        atomic_json(summary_path, summary)
        csv_path = summary_path.with_suffix(".csv")
        with csv_path.open("x", encoding="utf-8-sig", newline="") as stream:
            columns = ["path", "status", "input_bytes", "output_bytes", "reason"]
            csv_writer = csv.DictWriter(stream, fieldnames=columns)
            csv_writer.writeheader()
            for record in records:
                csv_writer.writerow({key: spreadsheet_cell(record.get(key, "")) for key in columns})
        if on_event is None:
            print(f"Finished: {summary['completed']}/{len(files)} complete; {len(review)} need review.\nReport: {summary_path}")
        else:
            on_event({"type": "finished", "summary": summary,
                      "report": str(summary_path), "csv": str(csv_path)})
        return 2 if review else 0


def main(argv=None) -> int:
    # Redirected Windows consoles can use legacy encodings (for example cp1252).
    # A filename that cannot be displayed must never stop the remaining queue.
    # Keep the stream's chosen encoding; escape only unrepresentable characters.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    if argv is None and sys.argv[1:] == ["--worker"]:
        try:
            result = worker(json.load(sys.stdin))
        except Exception as exc:
            result = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(result))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Folder containing PDFs (subfolders included)")
    parser.add_argument("output", help="Separate output folder; never inside input")
    parser.add_argument("--resume", action="store_true", help="Verify hashes and skip completed unchanged files")
    parser.add_argument("--quality", type=int, default=85, help="JPEG quality 1-95 (default 85); lossy")
    parser.add_argument("--max-edge", type=int, default=2000, help="Maximum image edge in pixels; 0 disables resize (default 2000)")
    parser.add_argument("--lossless", action="store_true", help="Only compress page streams/deduplicate; do not re-encode images")
    parser.add_argument("--timeout", type=float, default=120, help="Seconds allowed per PDF (default 120)")
    args = parser.parse_args(argv)
    if not 1 <= args.quality <= 95 or args.max_edge < 0 or args.timeout <= 0:
        parser.error("Quality must be 1-95; max-edge >= 0; timeout > 0")
    try:
        return run_batch(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

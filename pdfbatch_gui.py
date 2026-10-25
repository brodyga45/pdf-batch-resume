#!/usr/bin/env python3
"""A desktop entry point for PDF Batch Resume; no web server or PDF uploads."""
from __future__ import annotations

import argparse
from pathlib import Path
import queue
import sys
import threading

import pdfbatch


def make_options(source: str, output: str, mode: str, timeout: str):
    """Convert the visible choices into the existing engine's options."""
    if not source.strip() or not output.strip():
        raise ValueError("Choose both an input folder and a separate output folder.")
    if mode not in ("balanced", "lossless"):
        raise ValueError("Choose an image quality mode.")
    try:
        seconds = float(timeout)
    except ValueError as exc:
        raise ValueError("The per-file timeout must be a number of seconds.") from exc
    import math
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("The per-file timeout must be a positive, finite number.")
    return argparse.Namespace(input=source, output=output,
                              quality=85, max_edge=2000, lossless=mode == "lossless",
                              timeout=seconds, resume=True)


def execute(options, events: queue.Queue, stop: threading.Event):
    """Use structured events, keeping all Tk calls on the window thread."""
    try:
        code = pdfbatch.run_batch(options, on_event=events.put, stop_requested=stop.is_set)
    except Exception as exc:
        events.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        code = 1
    events.put({"type": "exit", "code": code})


def create_window(root):
    # Lazy import preserves the command-line/controller path on Python builds
    # without Tk. Official Windows Python normally includes Tcl/Tk.
    import tkinter as tk
    from tkinter import filedialog, ttk
    from tkinter.scrolledtext import ScrolledText

    class BatchWindow:
        def __init__(self):
            self.events = queue.Queue()
            self.stop = threading.Event()
            self.worker = None
            self.closing = False
            self.last_code = None
            self.source = tk.StringVar()
            self.output = tk.StringVar()
            self.mode = tk.StringVar(value="balanced")
            self.timeout = tk.StringVar(value="120")
            self.status = tk.StringVar(value="Choose folders, then Start / Continue.")
            self.report = tk.StringVar()
            root.title("PDF Batch Resume")
            root.geometry("900x680")
            root.minsize(710, 560)
            root.protocol("WM_DELETE_WINDOW", self.close)
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)
            shell = ttk.Frame(root, padding=22)
            shell.grid(sticky="nsew")
            shell.columnconfigure(1, weight=1)
            shell.rowconfigure(11, weight=1)
            ttk.Label(shell, text="A PDF batch that can continue", font=("TkDefaultFont", 18, "bold")).grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
            ttk.Label(shell, text="Separate copies • one PDF at a time • originals stay unchanged").grid(
                row=1, column=0, columnspan=3, sticky="w", pady=(0, 22))
            self.settings = []
            for row, label, variable, choose in (
                    (2, "Input folder", self.source, self.choose_input),
                    (3, "Output folder", self.output, self.choose_output)):
                ttk.Label(shell, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
                entry = ttk.Entry(shell, textvariable=variable)
                entry.grid(row=row, column=1, sticky="ew", pady=5)
                button = ttk.Button(shell, text="Browse…", command=choose)
                button.grid(row=row, column=2, padx=(8, 0), pady=5)
                self.settings.extend((entry, button))
            ttk.Label(shell, text="Use a separate output folder outside the input folder.").grid(
                row=4, column=1, columnspan=2, sticky="w", pady=(0, 16))
            ttk.Label(shell, text="Image quality").grid(row=5, column=0, sticky="nw", padx=(0, 12))
            choices = ttk.Frame(shell)
            choices.grid(row=5, column=1, columnspan=2, sticky="w")
            for value, text in (("balanced", "Smaller images — JPEG quality 85, longest edge 2000 px (lossy)"),
                                ("lossless", "Keep image pixels — size savings may be small or zero")):
                choice = ttk.Radiobutton(choices, text=text, value=value, variable=self.mode)
                choice.pack(anchor="w", pady=3)
                self.settings.append(choice)
            self.quality_note = ttk.Label(shell,
                text="Try a few copies first. Check small text and diagrams before a large batch.",
                wraplength=620)
            self.quality_note.grid(row=6, column=1, columnspan=2, sticky="w", pady=(4, 14))
            ttk.Label(shell, text="Seconds per PDF").grid(row=7, column=0, sticky="w", padx=(0, 12))
            timeout_entry = ttk.Entry(shell, textvariable=self.timeout, width=10)
            timeout_entry.grid(row=7, column=1, sticky="w")
            self.settings.append(timeout_entry)
            actions = ttk.Frame(shell)
            actions.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(18, 8))
            self.start_button = ttk.Button(actions, text="Start / Continue", command=self.start)
            self.start_button.pack(side="left")
            self.stop_button = ttk.Button(actions, text="Stop after current PDF", command=self.request_stop, state="disabled")
            self.stop_button.pack(side="left", padx=8)
            self.bar = ttk.Progressbar(shell, mode="determinate")
            self.bar.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(0, 7))
            ttk.Label(shell, textvariable=self.status, wraplength=790).grid(
                row=10, column=0, columnspan=3, sticky="w", pady=(0, 8))
            self.log = ScrolledText(shell, height=10, wrap="word", state="disabled", font=("TkFixedFont", 10))
            self.log.grid(row=11, column=0, columnspan=3, sticky="nsew")
            ttk.Label(shell, text="Latest report (also saved as CSV in the output folder)").grid(
                row=12, column=0, columnspan=3, sticky="w", pady=(12, 4))
            ttk.Entry(shell, textvariable=self.report, state="readonly").grid(
                row=13, column=0, columnspan=3, sticky="ew")
            ttk.Label(shell, text="Continue checks source, options and output hashes; existing outputs are never overwritten. "
                      "Encrypted PDFs, forms, signatures and annotations are skipped with a reason.",
                      wraplength=790).grid(row=14, column=0, columnspan=3, sticky="w", pady=(12, 0))
            root.after(60, self.poll)

        def choose_input(self):
            selected = filedialog.askdirectory(parent=root, title="Choose the original PDF folder", mustexist=True)
            if selected:
                self.source.set(selected)
                if not self.output.get():
                    path = Path(selected)
                    self.output.set(str(path.parent / (path.name + " - compressed")))

        def choose_output(self):
            selected = filedialog.askdirectory(parent=root, title="Choose a separate output folder", mustexist=False)
            if selected:
                self.output.set(selected)

        def append(self, text):
            self.log.configure(state="normal")
            self.log.insert("end", text + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")

        def start(self):
            if self.worker is not None:
                return
            try:
                options = make_options(self.source.get(), self.output.get(), self.mode.get(), self.timeout.get())
            except ValueError as exc:
                self.status.set(str(exc))
                return
            self.stop.clear()
            self.report.set("")
            self.last_code = None
            self.bar.configure(value=0, maximum=1)
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")
            for widget in self.settings:
                widget.configure(state="disabled")
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.status.set("Checking folders and starting the queue…")
            self.worker = threading.Thread(target=execute, args=(options, self.events, self.stop), daemon=False)
            self.worker.start()

        def request_stop(self):
            if self.worker is not None:
                self.stop.set()
                self.stop_button.configure(state="disabled")
                self.status.set("Finishing the current PDF, then stopping. Completed work will be saved.")

        def close(self):
            if self.worker is None:
                root.destroy()
            else:
                self.closing = True
                self.request_stop()
                self.status.set("Finishing the current PDF and saving progress, then closing…")

        def handle(self, event):
            kind = event["type"]
            if kind == "progress":
                record = event["record"]
                self.bar.configure(maximum=event["total"], value=event["index"])
                self.append(f"[{event['index']}/{event['total']}] {record['status']}: {record['path']}")
                if record.get("reason"):
                    self.append("    " + record["reason"])
                for warning in record.get("warnings", []):
                    self.append("    " + warning)
                if not self.stop.is_set():
                    self.status.set(f"Processed {event['index']} of {event['total']} PDFs. Originals stay unchanged.")
            elif kind == "finished":
                summary = event["summary"]
                self.report.set(event["report"])
                saved = summary["saved_bytes"] / (1024 * 1024)
                self.status.set(f"Finished: {summary['completed']} of {summary['files_found']} complete; "
                                f"{summary['need_review']} need review. Saved {saved:.2f} MiB on completed files.")
                self.append("JSON report: " + event["report"])
                self.append("CSV report: " + event["csv"])
            elif kind == "stopped":
                self.status.set(f"Stopped after {event['completed_records']} of {event['total']} PDFs. "
                                "Use the same folders and settings, then Start / Continue.")
                self.append("Progress saved in the output folder. A full report is written when the queue finishes.")
            elif kind == "error":
                self.status.set(event["message"])
                self.append(event["message"])
            elif kind == "exit":
                self.last_code = event["code"]
                self.worker = None
                for widget in self.settings:
                    widget.configure(state="normal")
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")

        def poll(self):
            try:
                while True:
                    self.handle(self.events.get_nowait())
            except queue.Empty:
                pass
            if self.closing and self.worker is None:
                root.destroy()
            else:
                root.after(60, self.poll)

    return BatchWindow()


def main():
    try:
        import tkinter as tk
    except ImportError:
        print("This Python installation has no Tcl/Tk GUI support. On Windows, install Python with Tcl/Tk enabled. "
              "The command-line tool pdfbatch.py remains available.", file=sys.stderr)
        return 1
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Cannot open the desktop window: {exc}. The command-line tool pdfbatch.py remains available.", file=sys.stderr)
        return 1
    create_window(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

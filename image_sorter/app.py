"""CustomTkinter GUI for the Image Sorter."""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import __version__, settings, updater
from .bands import DEFAULT_PRESET_KEY, PRESETS, Band, Preset, preset_by_label
from .sorter import (
    CollisionGroup,
    ExecutionResult,
    PlannedFile,
    ScanResult,
    auto_rename_for_uniqueness,
    dedupe_keep_first,
    execute_plan,
    find_collisions,
    scan_source,
)

APP_TITLE = "Image Sorter"
DEFAULT_WORKERS = 4
WORKER_MIN, WORKER_MAX = 1, 16
WORKER_CHOICES = ("1", "2", "4", "6", "8", "12", "16")

# Windows-illegal filename chars and reserved basenames.
_BAD_CHARS = set('<>:"/\\|?*')
_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

# Status state -> (light-mode color, dark-mode color)
_STATUS_COLORS: dict[str, tuple[str, str]] = {
    "idle":      ("gray50", "gray60"),
    "working":   ("#1f6feb", "#58a6ff"),
    "done":      ("#1a7f37", "#3fb950"),
    "cancelled": ("#bf5700", "#d29922"),
    "error":     ("#b42318", "#f85149"),
}


def _validate_folder_name(name: str) -> tuple[bool, str]:
    if not name or not name.strip():
        return False, "Output folder name is required."
    if name.endswith(" ") or name.endswith("."):
        return False, "Name cannot end with a space or a period."
    for c in name:
        if c in _BAD_CHARS:
            return False, 'Name cannot contain any of:  < > : " / \\ | ? *'
        if ord(c) < 32:
            return False, "Name cannot contain control characters."
    base = name.split(".")[0].upper()
    if base in _RESERVED:
        return False, f"'{name}' uses a Windows-reserved name."
    return True, ""


def _format_eta(seconds: float) -> str:
    if seconds < 0 or seconds == float("inf") or seconds != seconds:
        return "--"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


# ---------- Messages from worker thread to UI ----------

class _Msg: pass

class _ScanProgress(_Msg):
    def __init__(self, n: int): self.n = n

class _ScanDone(_Msg):
    def __init__(self, result: ScanResult): self.result = result

class _NeedCollisionChoice(_Msg):
    def __init__(self, groups: list[CollisionGroup]): self.groups = groups

class _ExecProgress(_Msg):
    def __init__(self, i: int, total: int, current: Path):
        self.i, self.total, self.current = i, total, current

class _LogLine(_Msg):
    def __init__(self, line: str): self.line = line

class _ExecDone(_Msg):
    def __init__(
        self,
        result: ExecutionResult,
        scan: ScanResult,
        log_path: Path | None,
        output_root: Path,
        bands: dict[int, Band],
    ):
        self.result = result
        self.scan = scan
        self.log_path = log_path
        self.output_root = output_root
        self.bands = bands

class _WorkerError(_Msg):
    def __init__(self, exc: BaseException): self.exc = exc


# ---------- App ----------

class SorterApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("920x720")
        self.root.minsize(780, 580)

        # state
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.msg_queue: "queue.Queue[_Msg]" = queue.Queue()
        self.collision_response = threading.Event()
        self.collision_choice: str | None = None

        self._log_lines: list[str] = []
        self._eta_samples: deque[tuple[float, int]] = deque(maxlen=200)
        self._last_output_root: Path | None = None
        self._progress_indeterminate = False

        self._stored = settings.load()

        self._build_ui()
        self._prefill_from_settings()

        self.root.after(100, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Kick off the update check shortly after launch so the window paints
        # first; the check itself runs on a background thread and silently
        # no-ops on any error.
        self.root.after(750, self._start_update_check)

    # ---------- UI ----------

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(5, weight=1)  # log row

        # ---- Update-available banner (row 0, ungridded until needed) ----
        self._build_update_banner()

        # ---- Header ----
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=16, pady=(14, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=APP_TITLE, font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Sort multi-band drone imagery into one folder per band.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70"),
        ).grid(row=1, column=0, sticky="w")

        self.appearance_menu = ctk.CTkOptionMenu(
            header,
            values=["System", "Light", "Dark"],
            width=110,
            command=self._on_appearance_change,
        )
        self.appearance_menu.set(self._stored.get("appearance", "System"))
        self.appearance_menu.grid(row=0, column=1, rowspan=2, sticky="e", padx=(8, 0))
        ctk.set_appearance_mode(self.appearance_menu.get())

        # ---- Input card ----
        input_card = self._make_card(self.root, "Input")
        input_card.frame.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        body = input_card.body
        body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Sensor preset").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.preset_menu = ctk.CTkOptionMenu(
            body,
            values=[p.label for p in PRESETS.values()],
            command=self._on_preset_change,
        )
        self.preset_menu.grid(row=0, column=1, sticky="w", padx=6, pady=6)
        ctk.CTkLabel(
            body, text="(determines suffix → band mapping)",
            text_color=("gray45", "gray65"),
        ).grid(row=0, column=2, sticky="w", padx=6, pady=6)

        ctk.CTkLabel(body, text="Source flight folder").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.src_var = tk.StringVar()
        ctk.CTkEntry(body, textvariable=self.src_var).grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(body, text="Browse...", width=100, command=self._pick_source).grid(
            row=1, column=2, padx=6, pady=6
        )

        ctk.CTkLabel(body, text="Output parent folder").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.dst_var = tk.StringVar()
        ctk.CTkEntry(body, textvariable=self.dst_var).grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(body, text="Browse...", width=100, command=self._pick_dest).grid(
            row=2, column=2, padx=6, pady=6
        )

        ctk.CTkLabel(body, text="Output folder name").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        self.name_var = tk.StringVar()
        ctk.CTkEntry(
            body,
            textvariable=self.name_var,
            placeholder_text="e.g. 0708_Nisbet_West_Corn",
        ).grid(row=3, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkLabel(
            body, text="(literal subfolder under parent)", text_color=("gray45", "gray65")
        ).grid(row=3, column=2, sticky="w", padx=6, pady=6)

        # ---- Run card ----
        run_card = self._make_card(self.root, "Run")
        run_card.frame.grid(row=3, column=0, sticky="ew", padx=16, pady=8)
        rbody = run_card.body
        rbody.grid_columnconfigure(3, weight=1)

        self.move_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            rbody,
            text="Move files instead of copying  (destructive — originals deleted)",
            variable=self.move_var,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(2, 4))

        self.include_misc_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            rbody,
            text="Also copy other files (.dat, .csv, GPS logs, etc.) into a Misc folder",
            variable=self.include_misc_var,
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 8))

        ctk.CTkLabel(rbody, text="Copy workers").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.workers_combo = ctk.CTkComboBox(
            rbody, values=list(WORKER_CHOICES), width=80, justify="center"
        )
        self.workers_combo.set(str(DEFAULT_WORKERS))
        self.workers_combo.grid(row=2, column=1, sticky="w", padx=6, pady=6)
        ctk.CTkLabel(
            rbody,
            text="1 = serial · ~4 is a good default · drop to 1-2 for HDD-to-same-HDD · 8+ for network shares",
            text_color=("gray45", "gray65"),
        ).grid(row=2, column=2, columnspan=2, sticky="w", padx=6, pady=6)

        self.start_btn = ctk.CTkButton(rbody, text="Scan & Sort", width=130, command=self._on_start)
        self.start_btn.grid(row=3, column=0, padx=6, pady=(10, 4), sticky="w")
        self.cancel_btn = ctk.CTkButton(
            rbody, text="Cancel", width=100, command=self._on_cancel, state="disabled",
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
        )
        self.cancel_btn.grid(row=3, column=1, padx=6, pady=(10, 4), sticky="w")
        self.open_btn = ctk.CTkButton(
            rbody, text="Open output folder", width=170, command=self._open_output, state="disabled",
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
        )
        self.open_btn.grid(row=3, column=2, padx=6, pady=(10, 4), sticky="w")

        # ---- Progress + status ----
        prog_card = ctk.CTkFrame(self.root, fg_color="transparent")
        prog_card.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 4))
        prog_card.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(prog_card, height=14)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self.status_var = tk.StringVar(value="Idle.")
        self.status_lbl = ctk.CTkLabel(
            prog_card, textvariable=self.status_var, anchor="w",
            text_color=_STATUS_COLORS["idle"],
        )
        self.status_lbl.grid(row=1, column=0, sticky="ew", padx=4)

        # ---- Log card ----
        log_card = self._make_card(self.root, "Log")
        log_card.frame.grid(row=5, column=0, sticky="nsew", padx=16, pady=(8, 16))
        log_card.frame.grid_rowconfigure(1, weight=1)
        log_card.frame.grid_columnconfigure(0, weight=1)
        log_card.body.grid_rowconfigure(0, weight=1)
        log_card.body.grid_columnconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(log_card.body, wrap="none", font=("Consolas", 11))
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _make_card(self, parent, title: str):
        frame = ctk.CTkFrame(parent, corner_radius=10)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame, text=title, font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 2))
        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        body.grid_columnconfigure(0, weight=0)

        class _Card:
            pass
        c = _Card()
        c.frame = frame
        c.body = body
        return c

    # ---------- Update banner ----------

    def _build_update_banner(self) -> None:
        """Create the (initially hidden) 'update available' banner widget."""
        self.update_banner = ctk.CTkFrame(
            self.root,
            corner_radius=8,
            fg_color=("#fff4d6", "#3e3315"),
            border_width=1,
            border_color=("#f0c875", "#7a5d2a"),
        )
        # NOT gridded here; we grid into row 0 only when an update is found.
        inner = ctk.CTkFrame(self.update_banner, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)

        self._update_label = ctk.CTkLabel(
            inner,
            text="",
            anchor="w",
            text_color=("#664d03", "#ffe69c"),
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._update_label.pack(side="left", expand=True, fill="x")

        ctk.CTkButton(
            inner, text="Download", width=110,
            command=self._open_update_url,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            inner, text="Dismiss", width=90,
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            text_color=("gray15", "gray90"),
            command=self._dismiss_update_banner,
        ).pack(side="left", padx=4)

        self._update_info: dict | None = None

    def _show_update_banner(self, info: dict) -> None:
        self._update_info = info
        self._update_label.configure(
            text=(
                f"  Update available: {info['tag_name']}  "
                f"(you have v{__version__}) — click Download for the new EXE."
            )
        )
        self.update_banner.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 0))

    def _open_update_url(self) -> None:
        url = (self._update_info or {}).get("html_url") or updater.RELEASES_PAGE_URL
        try:
            webbrowser.open(url, new=2)
        except Exception:  # noqa: BLE001
            pass

    def _dismiss_update_banner(self) -> None:
        if self._update_info:
            stored = settings.load()
            stored["dismissed_update_version"] = self._update_info["tag_name"]
            settings.save(stored)
        try:
            self.update_banner.grid_forget()
        except tk.TclError:
            pass

    def _start_update_check(self) -> None:
        stored = settings.load()
        if not updater.should_check(stored.get("update_check_at")):
            return

        def callback(info: dict | None) -> None:
            # Worker thread — schedule UI work on the main thread.
            self.root.after(0, self._on_update_check_result, info)

        updater.check_async(callback)

    def _on_update_check_result(self, info: dict | None) -> None:
        # Record the attempt regardless so we don't retry until tomorrow.
        stored = settings.load()
        stored["update_check_at"] = datetime.now().isoformat(timespec="seconds")
        settings.save(stored)

        if info is None:
            return

        dismissed = stored.get("dismissed_update_version", "")
        if dismissed and not updater.is_newer(info["tag_name"], dismissed):
            return

        self._show_update_banner(info)

    # ---------- State helpers ----------

    def _set_status(self, text: str, state: str = "idle") -> None:
        self.status_var.set(text)
        self.status_lbl.configure(text_color=_STATUS_COLORS.get(state, _STATUS_COLORS["idle"]))

    def _prefill_from_settings(self) -> None:
        s = self._stored
        if s.get("last_source"):
            self.src_var.set(s["last_source"])
        if s.get("last_destination"):
            self.dst_var.set(s["last_destination"])
        if isinstance(s.get("last_workers"), int):
            w = max(WORKER_MIN, min(WORKER_MAX, s["last_workers"]))
            self.workers_combo.set(str(w))
        if isinstance(s.get("include_misc"), bool):
            self.include_misc_var.set(s["include_misc"])
        preset_key = s.get("last_preset") or DEFAULT_PRESET_KEY
        preset = PRESETS.get(preset_key) or PRESETS[DEFAULT_PRESET_KEY]
        self.preset_menu.set(preset.label)

    def _save_settings(self) -> None:
        try:
            workers = int(self.workers_combo.get())
        except (tk.TclError, ValueError):
            workers = DEFAULT_WORKERS
        settings.save({
            "last_source": self.src_var.get().strip(),
            "last_destination": self.dst_var.get().strip(),
            "last_workers": workers,
            "last_preset": preset_by_label(self.preset_menu.get()).key,
            "include_misc": bool(self.include_misc_var.get()),
            "appearance": self.appearance_menu.get(),
        })

    def _on_preset_change(self, label: str) -> None:
        # Persist immediately so the choice survives across launches even
        # without a run.
        stored = settings.load()
        stored["last_preset"] = preset_by_label(label).key
        settings.save(stored)

    def _on_appearance_change(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        # Persist on each change so it survives restarts even without a run.
        stored = settings.load()
        stored["appearance"] = mode
        settings.save(stored)

    # ---------- UI actions ----------

    def _pick_source(self) -> None:
        d = filedialog.askdirectory(title="Choose source flight folder")
        if not d:
            return
        self.src_var.set(d)
        if not self.name_var.get().strip():
            self.name_var.set(Path(d).name)

    def _pick_dest(self) -> None:
        d = filedialog.askdirectory(title="Choose output parent folder")
        if d:
            self.dst_var.set(d)

    def _log(self, line: str) -> None:
        self._log_lines.append(line)
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")

    def _set_busy(self, busy: bool) -> None:
        self.start_btn.configure(state=("disabled" if busy else "normal"))
        self.cancel_btn.configure(state=("normal" if busy else "disabled"))
        self.workers_combo.configure(state=("disabled" if busy else "normal"))

    def _on_cancel(self) -> None:
        if messagebox.askyesno("Cancel", "Stop the operation?"):
            self.cancel_event.set()
            self.collision_choice = "cancel"
            self.collision_response.set()
            self._set_status("Cancelling...", "cancelled")

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Quit", "Work is in progress. Cancel and quit?"):
                return
            self.cancel_event.set()
            self.collision_choice = "cancel"
            self.collision_response.set()
        self.root.destroy()

    def _open_output(self) -> None:
        if not self._last_output_root or not self._last_output_root.exists():
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(self._last_output_root))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{self._last_output_root}"')
            else:
                os.system(f'xdg-open "{self._last_output_root}"')
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Open folder", f"Could not open folder:\n{e}")

    def _on_start(self) -> None:
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        name = self.name_var.get()
        if not src or not Path(src).is_dir():
            messagebox.showerror("Invalid input", "Pick a valid source folder.")
            return
        if not dst or not Path(dst).is_dir():
            messagebox.showerror("Invalid input", "Pick a valid output parent folder.")
            return
        ok, err = _validate_folder_name(name)
        if not ok:
            messagebox.showerror("Invalid output folder name", err)
            return

        try:
            workers = int(self.workers_combo.get())
        except (tk.TclError, ValueError):
            workers = DEFAULT_WORKERS
        workers = max(WORKER_MIN, min(WORKER_MAX, workers))

        output_root = Path(dst) / name
        if output_root.exists() and any(output_root.iterdir()):
            if not messagebox.askyesno(
                "Output folder exists",
                f"{output_root}\n\nalready exists and is not empty. Continue?\n\n"
                "Existing files with the same name will be skipped (never overwritten).",
            ):
                return

        if self.move_var.get():
            if not messagebox.askyesno(
                "Confirm MOVE",
                "MOVE deletes each source file after it's transferred.\n\n"
                "If the run is cancelled or fails partway, your source folder will be "
                "partially emptied. It is strongly recommended to test with COPY first.\n\n"
                "Proceed with MOVE?",
            ):
                return

        self._save_settings()

        self.cancel_event.clear()
        self.collision_response.clear()
        self.collision_choice = None
        self._log_lines.clear()
        self._eta_samples.clear()
        self.log_text.delete("1.0", "end")
        self.open_btn.configure(state="disabled")
        self._last_output_root = output_root

        preset = preset_by_label(self.preset_menu.get())
        include_misc = bool(self.include_misc_var.get())

        self._log(f"== Run started {datetime.now().isoformat(timespec='seconds')} ==")
        self._log(f"Preset:   {preset.label}  ({len(preset.bands)} bands)")
        self._log(f"Source:   {src}")
        self._log(f"Output:   {output_root}")
        self._log(f"Mode:     {'MOVE' if self.move_var.get() else 'COPY'}")
        self._log(f"Workers:  {workers}")
        self._log(f"Misc:     {'on (.dat/.csv/etc. -> Misc/)' if include_misc else 'off'}")
        self._log("")

        self._set_busy(True)
        self._set_status("Scanning...", "working")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._progress_indeterminate = True

        self.worker = threading.Thread(
            target=self._worker_main,
            args=(Path(src), output_root, self.move_var.get(), workers, preset, include_misc),
            daemon=True,
        )
        self.worker.start()

    # ---------- Worker thread ----------

    def _worker_main(
        self,
        src: Path,
        output_root: Path,
        move: bool,
        workers: int,
        preset: Preset,
        include_misc: bool,
    ) -> None:
        worker_log: list[str] = []
        bands = preset.bands

        def log(line: str) -> None:
            worker_log.append(line)
            self.msg_queue.put(_LogLine(line))

        try:
            scan = scan_source(
                src,
                output_root,
                bands=bands,
                include_misc=include_misc,
                progress_cb=lambda n: self.msg_queue.put(_ScanProgress(n)),
                cancel_event=self.cancel_event,
            )
            if self.cancel_event.is_set():
                self.msg_queue.put(_ExecDone(ExecutionResult(cancelled=True), scan, None, output_root, bands))
                return
            self.msg_queue.put(_ScanDone(scan))

            if scan.unrecognized_tifs:
                log(f"Unrecognized TIFFs ({len(scan.unrecognized_tifs)}):")
                for p in scan.unrecognized_tifs:
                    log(f"  {p}")

            collisions = find_collisions(scan.files)
            if collisions:
                log(f"Detected {len(collisions)} filename collision(s).")
                self.collision_response.clear()
                self.collision_choice = None
                self.msg_queue.put(_NeedCollisionChoice(collisions))
                self.collision_response.wait()
                choice = self.collision_choice or "cancel"
                log(f"Collision handling chosen: {choice.upper()}")
                if choice == "cancel" or self.cancel_event.is_set():
                    self.msg_queue.put(_ExecDone(ExecutionResult(cancelled=True), scan, None, output_root, bands))
                    return
                if choice == "rename":
                    renamed = auto_rename_for_uniqueness(scan.files)
                    log(f"Renamed {renamed} colliding files.")
                elif choice == "skip":
                    kept, skipped = dedupe_keep_first(scan.files)
                    for pf in skipped:
                        log(f"SKIP (collision, keeping first): {pf.source}")
                    scan.files = kept

            exec_result = execute_plan(
                scan.files,
                move=move,
                workers=workers,
                progress_cb=lambda i, total, cur: self.msg_queue.put(_ExecProgress(i, total, cur)),
                log_cb=log,
                cancel_event=self.cancel_event,
            )

            log_path: Path | None = None
            try:
                output_root.mkdir(parents=True, exist_ok=True)
                log_path = output_root / f"sort_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with log_path.open("w", encoding="utf-8") as f:
                    f.write("\n".join(worker_log))
                    f.write("\n\n--- Summary ---\n")
                    f.write(_summary_text(scan, exec_result, bands))
            except Exception as e:  # noqa: BLE001
                self.msg_queue.put(_LogLine(f"WARN: could not write log file: {e}"))
                log_path = None

            self.msg_queue.put(_ExecDone(exec_result, scan, log_path, output_root, bands))
        except Exception as e:  # noqa: BLE001
            self.msg_queue.put(_WorkerError(e))

    # ---------- Queue pump ----------

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self._handle(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _handle(self, msg: _Msg) -> None:
        if isinstance(msg, _ScanProgress):
            self._set_status(f"Scanning... {msg.n} files seen", "working")
        elif isinstance(msg, _ScanDone):
            self._stop_indeterminate()
            self.progress.configure(mode="determinate")
            self.progress.set(0)
            band_count = sum(1 for pf in msg.result.files if pf.kind == "band")
            misc_count = sum(1 for pf in msg.result.files if pf.kind == "misc")
            misc_part = f", {misc_count} misc files" if misc_count else ""
            non_image_part = (
                f"{len(msg.result.non_image_files)} non-image files skipped"
                if misc_count == 0
                else f"{len(msg.result.non_image_files)} non-image files routed to Misc/"
            )
            self._log(
                f"Scan complete: {band_count} band TIFFs queued{misc_part}, "
                f"{len(msg.result.unrecognized_tifs)} unrecognized TIFFs, "
                f"{non_image_part}."
            )
            self._set_status("Scan done — starting copy...", "working")
            self._eta_samples.clear()
            self._eta_samples.append((time.monotonic(), 0))
        elif isinstance(msg, _NeedCollisionChoice):
            self._prompt_collisions(msg.groups)
        elif isinstance(msg, _ExecProgress):
            if msg.total:
                self.progress.set(msg.i / msg.total)
            self._update_eta_status(msg.i, msg.total, msg.current)
        elif isinstance(msg, _LogLine):
            self._log(msg.line)
        elif isinstance(msg, _ExecDone):
            self._on_exec_done(msg)
        elif isinstance(msg, _WorkerError):
            self._set_busy(False)
            self._stop_indeterminate()
            self._set_status("Error.", "error")
            self._log(f"FATAL: {msg.exc}")
            messagebox.showerror("Error", str(msg.exc))

    def _stop_indeterminate(self) -> None:
        if self._progress_indeterminate:
            try:
                self.progress.stop()
            except Exception:  # noqa: BLE001
                pass
            self._progress_indeterminate = False

    def _update_eta_status(self, done: int, total: int, current: Path) -> None:
        now = time.monotonic()
        self._eta_samples.append((now, done))
        while len(self._eta_samples) >= 2 and (now - self._eta_samples[0][0]) > 5.0:
            self._eta_samples.popleft()
        rate_text = ""
        eta_text = ""
        if len(self._eta_samples) >= 2:
            t0, c0 = self._eta_samples[0]
            t1, c1 = self._eta_samples[-1]
            dt = t1 - t0
            dc = c1 - c0
            if dt > 0 and dc > 0:
                rate = dc / dt
                remaining = max(0, total - done)
                rate_text = f"{rate:.0f} files/sec"
                eta_text = f"ETA {_format_eta(remaining / rate)}"
        pct = (done / total * 100.0) if total else 0.0
        parts = [f"{done}/{total} ({pct:.1f}%)"]
        if rate_text:
            parts.append(rate_text)
        if eta_text:
            parts.append(eta_text)
        parts.append(current.name)
        self._set_status("  ·  ".join(parts), "working")

    def _prompt_collisions(self, groups: list[CollisionGroup]) -> None:
        example = groups[0]
        preview_sources = "\n".join(f"    {s}" for s in example.sources[:3])
        if len(example.sources) > 3:
            preview_sources += f"\n    ...and {len(example.sources) - 3} more"
        body = (
            f"Found {len(groups)} filename collision(s) — multiple source files would "
            f"land at the same destination path.\n\n"
            f"Example collision:\n"
            f"  target: {example.target}\n"
            f"  sources:\n{preview_sources}\n\n"
            "How would you like to handle ALL collisions?\n\n"
            "  Yes    — auto-rename (append parent-folder tag to make unique)\n"
            "  No     — skip duplicates (keep first source for each target)\n"
            "  Cancel — abort the run"
        )
        result = messagebox.askyesnocancel("Filename collisions detected", body)
        if result is None:
            self.collision_choice = "cancel"
        elif result:
            self.collision_choice = "rename"
        else:
            self.collision_choice = "skip"
        self.collision_response.set()

    def _on_exec_done(self, msg: _ExecDone) -> None:
        self._set_busy(False)
        self._stop_indeterminate()
        self.progress.set(1.0)
        summary = _summary_text(msg.scan, msg.result, msg.bands)
        self._log("")
        self._log("--- Summary ---")
        for line in summary.splitlines():
            self._log(line)
        if msg.log_path:
            self._log(f"\nFull log written to: {msg.log_path}")

        self._last_output_root = msg.output_root
        if msg.result.cancelled:
            self._set_status("Cancelled.", "cancelled")
            messagebox.showwarning("Cancelled", "The operation was cancelled.\n\n" + summary)
        elif msg.result.failed:
            self._set_status(f"Done with {len(msg.result.failed)} error(s).", "error")
            messagebox.showwarning("Done with errors", summary)
        else:
            self._set_status("Done.", "done")
            messagebox.showinfo("Done", summary)

        if msg.result.written > 0 and msg.output_root.exists():
            self.open_btn.configure(state="normal")


def _summary_text(scan: ScanResult, result: ExecutionResult, bands: dict[int, Band]) -> str:
    band_written = result.written - result.misc_written
    lines: list[str] = []
    lines.append(f"Files seen in source:  {scan.total_seen}")
    lines.append(f"Band files written:    {band_written}")
    lines.append(f"Misc files written:    {result.misc_written}")
    lines.append(f"Skipped (already in destination): {result.skipped_existing}")
    lines.append(f"Failed:                {len(result.failed)}")
    lines.append(f"Unrecognized TIFFs:    {len(scan.unrecognized_tifs)}")
    lines.append(f"Non-image files in source: {len(scan.non_image_files)}")
    if result.per_band:
        lines.append("")
        lines.append("Written per band:")
        for sfx in sorted(result.per_band):
            band = bands.get(sfx)
            folder = band.folder if band else f"band_{sfx}"
            lines.append(f"  {folder}: {result.per_band[sfx]}")
        if result.misc_written:
            lines.append(f"  Misc: {result.misc_written}")
    if scan.unrecognized_tifs:
        lines.append("")
        lines.append(f"Unrecognized TIFFs (showing up to 20 of {len(scan.unrecognized_tifs)}):")
        for p in scan.unrecognized_tifs[:20]:
            lines.append(f"  {p}")
    if result.failed:
        lines.append("")
        lines.append(f"Failures (showing up to 20 of {len(result.failed)}):")
        for p, err in result.failed[:20]:
            lines.append(f"  {p}: {err}")
    return "\n".join(lines)


def main() -> None:
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    SorterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

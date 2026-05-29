# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

"""Desktop GUI for the Fuzzyficator post-processing scripts."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import queue
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PROGRAM_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else APP_DIR
SETTINGS_PATH = Path.home() / ".fuzzyficator_gui.json"


@dataclass(frozen=True)
class ModeInfo:
    label: str
    script: str
    summary: str
    needs_displacement_map: bool = False
    uses_paint_settings: bool = False


MODES: dict[str, ModeInfo] = {
    "surface": ModeInfo(
        label="Surface Fuzzy Skin",
        script="Fuzzyficator.py",
        summary="Adds fuzzy skin to top surfaces and supported overhang/bridge areas.",
    ),
    "paint": ModeInfo(
        label="Paint-On Fuzzy Skin",
        script="Fuzzyficator_paintOn.py",
        summary="Uses slicer paint markers plus optional XY fuzz controls.",
        uses_paint_settings=True,
    ),
    "pattern": ModeInfo(
        label="Displacement Pattern",
        script="Fuzzyficator_pattern.py",
        summary="Applies a grayscale displacement map to marked fuzzy sections.",
        needs_displacement_map=True,
        uses_paint_settings=True,
    ),
}


class FuzzyficatorGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fuzzyficator")
        self.geometry("1020x760")
        self.minsize(900, 660)

        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.process: subprocess.Popen[str] | None = None
        self.settings_widgets: list[ttk.Widget] = []

        self._build_style()
        self._build_variables()
        self._build_layout()
        self._load_settings()
        self._bind_variable_traces()
        self._on_mode_changed()
        self._update_command_preview()
        self.after(120, self._drain_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Header.TFrame", background="#222831")
        style.configure("Header.TLabel", background="#222831", foreground="#ffffff")
        style.configure("Subtle.TLabel", foreground="#57606a")
        style.configure("Status.TLabel", padding=(10, 6), anchor="w")
        style.configure("Accent.TButton", padding=(16, 8))
        style.configure("Danger.TButton", padding=(16, 8))
        style.configure("TLabelframe", background="#f6f7f9")
        style.configure("TLabelframe.Label", background="#f6f7f9", foreground="#24292f")
        style.configure("TCheckbutton", background="#f6f7f9")
        style.configure("TRadiobutton", background="#f6f7f9")

    def _build_variables(self) -> None:
        self.mode_var = tk.StringVar(value="surface")
        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.in_place_var = tk.BooleanVar(value=False)
        self.backup_var = tk.BooleanVar(value=True)
        self.displacement_map_var = tk.StringVar()

        self.resolution_var = tk.StringVar(value="0.3")
        self.z_min_var = tk.StringVar(value="0.0")
        self.z_max_var = tk.StringVar(value="0.3")
        self.fuzzy_speed_var = tk.StringVar()
        self.bridge_multiplier_var = tk.StringVar(value="3.0")
        self.min_support_distance_var = tk.StringVar(value="0.1")
        self.xy_point_dist_var = tk.StringVar(value="0.3")
        self.xy_thickness_var = tk.StringVar(value="0.3")

        self.connect_walls_var = tk.BooleanVar(value=True)
        self.compensate_extrusion_var = tk.BooleanVar(value=True)
        self.top_surface_var = tk.BooleanVar(value=True)
        self.lower_surface_var = tk.BooleanVar(value=True)
        self.run_mode_var = tk.StringVar(value="force run")

        self.status_var = tk.StringVar(value="Ready")
        self.command_preview_var = tk.StringVar()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(20, 16))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text="Fuzzyficator", style="Header.TLabel", font=("Segoe UI", 20, "bold"))
        title.grid(row=0, column=0, sticky="w")
        subtitle = ttk.Label(
            header,
            text="Desktop post-processing GUI for Fuzzyficator, paint-on fuzz, and displacement maps.",
            style="Header.TLabel",
            font=("Segoe UI", 10),
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        body = ttk.Frame(self, padding=18)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        self._build_mode_panel(body)
        self._build_file_panel(body)
        self._build_settings_panel(body)
        self._build_run_panel(body)
        self._build_status_bar()

    def _build_mode_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Mode", padding=12)
        frame.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0, 12))
        frame.columnconfigure(0, weight=1)

        for index, (mode_key, mode) in enumerate(MODES.items()):
            row = ttk.Frame(frame)
            row.grid(row=index, column=0, sticky="ew", pady=(0 if index == 0 else 8, 0))
            row.columnconfigure(1, weight=1)
            radio = ttk.Radiobutton(row, text=mode.label, value=mode_key, variable=self.mode_var, command=self._on_mode_changed)
            radio.grid(row=0, column=0, sticky="w")
            summary = ttk.Label(row, text=mode.summary, style="Subtle.TLabel")
            summary.grid(row=0, column=1, sticky="w", padx=(14, 0))

    def _build_file_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Files", padding=12)
        frame.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 12))
        frame.columnconfigure(1, weight=1)

        self._path_row(frame, 0, "Input G-code", self.input_path_var, self._browse_input)
        self.output_entry = self._path_row(frame, 1, "Output G-code", self.output_path_var, self._browse_output)

        in_place = ttk.Checkbutton(frame, text="Process input file directly", variable=self.in_place_var, command=self._on_in_place_changed)
        in_place.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.backup_check = ttk.Checkbutton(frame, text="Create timestamped .bak first", variable=self.backup_var)
        self.backup_check.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.displacement_label = ttk.Label(frame, text="Displacement map")
        self.displacement_entry = ttk.Entry(frame, textvariable=self.displacement_map_var)
        self.displacement_button = ttk.Button(frame, text="Browse", command=self._browse_displacement_map)
        self.displacement_label.grid(row=4, column=0, sticky="w", pady=(12, 0))
        self.displacement_entry.grid(row=4, column=1, sticky="ew", padx=8, pady=(12, 0))
        self.displacement_button.grid(row=4, column=2, sticky="e", pady=(12, 0))

    def _path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: Callable[[], None],
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(0, 8))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, sticky="e", pady=(0, 8))
        return entry

    def _build_settings_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Settings", padding=12)
        frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        general = ttk.Frame(frame)
        general.grid(row=0, column=0, columnspan=2, sticky="ew")
        general.columnconfigure(1, weight=1)
        general.columnconfigure(3, weight=1)

        self._number_row(general, 0, 0, "Resolution", self.resolution_var, "mm between interpolated fuzzy points")
        self._number_row(general, 0, 2, "Z min", self.z_min_var, "minimum Z displacement in mm")
        self._number_row(general, 1, 0, "Z max", self.z_max_var, "maximum Z displacement in mm")
        self._number_row(general, 1, 2, "Fuzzy speed", self.fuzzy_speed_var, "optional mm/min override")
        self._number_row(general, 2, 0, "Bridge multiplier", self.bridge_multiplier_var, "overhang extrusion compensation factor")
        self._number_row(general, 2, 2, "Min support gap", self.min_support_distance_var, "minimum distance from support in mm")

        toggles = ttk.Frame(frame)
        toggles.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        for column in range(2):
            toggles.columnconfigure(column, weight=1)

        ttk.Checkbutton(toggles, text="Connect walls", variable=self.connect_walls_var).grid(row=0, column=0, sticky="w", pady=3)
        ttk.Checkbutton(toggles, text="Compensate extrusion", variable=self.compensate_extrusion_var).grid(row=0, column=1, sticky="w", pady=3)
        ttk.Checkbutton(toggles, text="Top surfaces", variable=self.top_surface_var).grid(row=1, column=0, sticky="w", pady=3)
        ttk.Checkbutton(toggles, text="Lower surfaces / overhangs", variable=self.lower_surface_var).grid(row=1, column=1, sticky="w", pady=3)

        run_frame = ttk.Frame(frame)
        run_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Label(run_frame, text="Run behavior").grid(row=0, column=0, sticky="w")
        run_combo = ttk.Combobox(
            run_frame,
            textvariable=self.run_mode_var,
            values=("auto", "force run", "skip processing"),
            state="readonly",
            width=18,
        )
        run_combo.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(
            run_frame,
            text="Auto lets the script decide from G-code settings where supported.",
            style="Subtle.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))

        self.paint_frame = ttk.LabelFrame(frame, text="Paint-On / Pattern XY Settings", padding=12)
        self.paint_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        self.paint_frame.columnconfigure(1, weight=1)
        self.paint_frame.columnconfigure(3, weight=1)
        self._number_row(self.paint_frame, 0, 0, "XY point distance", self.xy_point_dist_var, "paint-on perimeter point spacing")
        self._number_row(self.paint_frame, 0, 2, "XY thickness", self.xy_thickness_var, "paint-on perimeter deviation")

    def _number_row(
        self,
        parent: ttk.Frame,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
        help_text: str,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=6)
        entry = ttk.Entry(parent, textvariable=variable, width=13)
        entry.grid(row=row, column=column + 1, sticky="ew", pady=6)
        entry.bind("<FocusOut>", lambda _event: self._update_command_preview())
        self.settings_widgets.append(entry)
        entry.tooltip_text = help_text  # type: ignore[attr-defined]

    def _build_run_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Run", padding=12)
        frame.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        ttk.Label(frame, text="Command preview").grid(row=0, column=0, sticky="w")
        preview_wrap = ttk.Frame(frame)
        preview_wrap.grid(row=1, column=0, sticky="ew", pady=(6, 10))
        preview_wrap.columnconfigure(0, weight=1)
        self.command_preview = ttk.Entry(preview_wrap, textvariable=self.command_preview_var, state="readonly")
        self.command_preview.grid(row=0, column=0, sticky="ew")
        ttk.Button(preview_wrap, text="Copy", command=self._copy_command).grid(row=0, column=1, padx=(8, 0))

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        button_row.columnconfigure(2, weight=1)
        self.run_button = ttk.Button(button_row, text="Run Fuzzyficator", style="Accent.TButton", command=self._run)
        self.run_button.grid(row=0, column=0, sticky="w")
        self.cancel_button = ttk.Button(button_row, text="Cancel", style="Danger.TButton", command=self._cancel_run, state="disabled")
        self.cancel_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Button(button_row, text="Open Output Folder", command=self._open_output_folder).grid(row=0, column=3, sticky="e")

        log_frame = ttk.Frame(frame)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(
            log_frame,
            height=16,
            wrap="word",
            borderwidth=1,
            relief="solid",
            font=("Consolas", 9),
            foreground="#24292f",
            background="#ffffff",
            insertbackground="#24292f",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set, state="disabled")

    def _build_status_bar(self) -> None:
        status = ttk.Label(self, textvariable=self.status_var, style="Status.TLabel")
        status.grid(row=2, column=0, sticky="ew")

    def _bind_variable_traces(self) -> None:
        variables: list[tk.Variable] = [
            self.mode_var,
            self.input_path_var,
            self.output_path_var,
            self.in_place_var,
            self.backup_var,
            self.displacement_map_var,
            self.resolution_var,
            self.z_min_var,
            self.z_max_var,
            self.fuzzy_speed_var,
            self.bridge_multiplier_var,
            self.min_support_distance_var,
            self.xy_point_dist_var,
            self.xy_thickness_var,
            self.connect_walls_var,
            self.compensate_extrusion_var,
            self.top_surface_var,
            self.lower_surface_var,
            self.run_mode_var,
        ]
        for variable in variables:
            variable.trace_add("write", lambda *_args: self._update_command_preview())

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select G-code file",
            filetypes=(("G-code files", "*.gcode *.gco *.gc"), ("All files", "*.*")),
        )
        if not path:
            return
        self.input_path_var.set(path)
        if not self.in_place_var.get() and not self.output_path_var.get():
            input_path = Path(path)
            self.output_path_var.set(str(input_path.with_name(f"{input_path.stem}_fuzzy{input_path.suffix}")))

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose output G-code file",
            defaultextension=".gcode",
            filetypes=(("G-code files", "*.gcode *.gco *.gc"), ("All files", "*.*")),
        )
        if path:
            self.output_path_var.set(path)

    def _browse_displacement_map(self) -> None:
        path = filedialog.askopenfilename(
            title="Select displacement map",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("All files", "*.*")),
        )
        if path:
            self.displacement_map_var.set(path)

    def _on_mode_changed(self) -> None:
        mode = MODES[self.mode_var.get()]
        if mode.needs_displacement_map:
            self.displacement_label.grid()
            self.displacement_entry.grid()
            self.displacement_button.grid()
        else:
            self.displacement_label.grid_remove()
            self.displacement_entry.grid_remove()
            self.displacement_button.grid_remove()

        if mode.uses_paint_settings:
            self.paint_frame.grid()
        else:
            self.paint_frame.grid_remove()

        self.status_var.set(mode.summary)
        self._update_command_preview()

    def _on_in_place_changed(self) -> None:
        in_place = self.in_place_var.get()
        state = "disabled" if in_place else "normal"
        self.output_entry.configure(state=state)
        self.backup_check.configure(state="normal" if in_place else "disabled")
        self._update_command_preview()

    def _current_mode(self) -> ModeInfo:
        return MODES[self.mode_var.get()]

    def _worker_path(self) -> Path:
        if IS_FROZEN:
            return Path(sys.executable).resolve()
        return APP_DIR / "Fuzzyficator_gui.py"

    def _worker_command_prefix(self) -> list[str]:
        worker_path = self._worker_path()
        if IS_FROZEN:
            return [str(worker_path), "--worker"]
        return [sys.executable, str(worker_path), "--worker"]

    def _target_path_for_preview(self) -> str:
        if self.in_place_var.get():
            return self.input_path_var.get().strip() or "<input.gcode>"
        return self.output_path_var.get().strip() or "<output.gcode>"

    def _build_processor_args(self, target_gcode: str | Path) -> list[str]:
        args = [str(target_gcode)]
        self._append_float_arg(args, "-resolution", self.resolution_var.get())
        self._append_float_arg(args, "-zMin", self.z_min_var.get())
        self._append_float_arg(args, "-zMax", self.z_max_var.get())
        self._append_bool_arg(args, "-connectWalls", self.connect_walls_var.get())
        self._append_bool_arg(args, "-compensateExtrusion", self.compensate_extrusion_var.get())
        self._append_bool_arg(args, "-topSurface", self.top_surface_var.get())
        self._append_bool_arg(args, "-lowerSurface", self.lower_surface_var.get())
        self._append_float_arg(args, "-fuzzySpeed", self.fuzzy_speed_var.get())
        self._append_float_arg(args, "-bridgeCompensationMultiplier", self.bridge_multiplier_var.get())
        self._append_float_arg(args, "-minSupportDistance", self.min_support_distance_var.get())

        if self.run_mode_var.get() == "force run":
            args.extend(["-run", "1"])
        elif self.run_mode_var.get() == "skip processing":
            args.extend(["-run", "0"])

        mode = self._current_mode()
        if mode.uses_paint_settings:
            self._append_float_arg(args, "-xy_point_dist", self.xy_point_dist_var.get())
            self._append_float_arg(args, "-xy_thickness", self.xy_thickness_var.get())

        if mode.needs_displacement_map:
            args.extend(["-displacement_map", self.displacement_map_var.get().strip() or "<map.png>"])

        return args

    def _append_float_arg(self, args: list[str], flag: str, value: str) -> None:
        value = value.strip()
        if value:
            args.extend([flag, value])

    def _append_bool_arg(self, args: list[str], flag: str, enabled: bool) -> None:
        args.extend([flag, "1" if enabled else "0"])

    def _build_command(self, target_gcode: str | Path) -> list[str]:
        return [*self._worker_command_prefix(), self.mode_var.get(), *self._build_processor_args(target_gcode)]

    def _update_command_preview(self) -> None:
        target = self._target_path_for_preview()
        command = self._build_command(target)
        self.command_preview_var.set(subprocess.list2cmdline(command))

    def _copy_command(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.command_preview_var.get())
        self.status_var.set("Command copied to clipboard")

    def _validate_float(self, label: str, value: str, required: bool = False) -> float | None:
        value = value.strip()
        if not value:
            if required:
                raise ValueError(f"{label} is required.")
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number.") from exc

    def _validate_inputs(self) -> tuple[Path, Path]:
        input_path = Path(self.input_path_var.get().strip())
        if not input_path.exists() or not input_path.is_file():
            raise ValueError("Choose a valid input G-code file.")

        worker_path = self._worker_path()
        if not worker_path.exists():
            raise ValueError(f"Missing worker executable or script: {worker_path.name}")

        self._validate_float("Resolution", self.resolution_var.get())
        self._validate_float("Z min", self.z_min_var.get())
        self._validate_float("Z max", self.z_max_var.get())
        self._validate_float("Fuzzy speed", self.fuzzy_speed_var.get())
        self._validate_float("Bridge multiplier", self.bridge_multiplier_var.get())
        self._validate_float("Min support gap", self.min_support_distance_var.get())

        mode = self._current_mode()
        if mode.uses_paint_settings:
            self._validate_float("XY point distance", self.xy_point_dist_var.get())
            self._validate_float("XY thickness", self.xy_thickness_var.get())

        if mode.needs_displacement_map:
            if not IS_FROZEN and any(
                importlib.util.find_spec(import_name) is None for import_name in ("PIL", "numpy")
            ):
                raise ValueError(
                    "Pattern mode requires extra image dependencies. Install them with: "
                    "python -m pip install -r requirements.txt"
                )
            map_path = Path(self.displacement_map_var.get().strip())
            if not map_path.exists() or not map_path.is_file():
                raise ValueError("Choose a valid displacement map image.")

        if self.in_place_var.get():
            return input_path, input_path

        output_text = self.output_path_var.get().strip()
        if not output_text:
            raise ValueError("Choose an output G-code file.")
        output_path = Path(output_text)
        if input_path.resolve() == output_path.resolve():
            raise ValueError("Output must be different from input unless direct in-place processing is enabled.")
        return input_path, output_path

    def _prepare_target_file(self, input_path: Path, target_path: Path) -> None:
        if self.in_place_var.get():
            if self.backup_var.get():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = input_path.with_name(f"{input_path.name}.{timestamp}.bak")
                shutil.copy2(input_path, backup_path)
                self._append_log(f"Created backup: {backup_path}\n")
            return

        if target_path.exists():
            should_overwrite = messagebox.askyesno(
                "Overwrite output?",
                f"{target_path.name} already exists. Replace it?",
                icon="warning",
            )
            if not should_overwrite:
                raise RuntimeError("Run cancelled before overwriting output.")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, target_path)
        self._append_log(f"Copied input to output: {target_path}\n")

    def _run(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        try:
            input_path, target_path = self._validate_inputs()
            self._clear_log()
            self._prepare_target_file(input_path, target_path)
        except Exception as exc:
            messagebox.showerror("Cannot run Fuzzyficator", str(exc))
            self.status_var.set("Ready")
            return

        before_digest = self._file_digest(target_path)
        before_markers = self._count_processing_markers(target_path)
        command = self._build_command(target_path)
        self._save_settings()
        self._set_running_state(True)
        self._append_log(f"Running: {subprocess.list2cmdline(command)}\n\n")

        self.worker = threading.Thread(
            target=self._worker_run,
            args=(command, target_path, before_digest, before_markers),
            daemon=True,
        )
        self.worker.start()

    def _worker_run(
        self,
        command: list[str],
        target_path: Path,
        before_digest: str,
        before_markers: int,
    ) -> None:
        try:
            self.process = subprocess.Popen(
                command,
                cwd=PROGRAM_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(("log", line))
            return_code = self.process.wait()
            if return_code == 0:
                after_digest = self._file_digest(target_path)
                after_markers = self._count_processing_markers(target_path)
                added_markers = after_markers - before_markers
                if added_markers <= 0:
                    self.log_queue.put((
                        "warning",
                        "Completed, but no processed movement markers were added. "
                        "That usually means the selected processor did not find matching slicer markers "
                        "or the run behavior was set to skip processing.",
                    ))
                elif before_digest == after_digest:
                    self.log_queue.put(("warning", "Completed, but the file hash did not change after processing."))
                else:
                    self.log_queue.put((
                        "done",
                        f"Completed successfully: {target_path} ({added_markers} processed movement markers added)",
                    ))
            else:
                self.log_queue.put(("error", f"Processor exited with code {return_code}."))
        except Exception as exc:
            self.log_queue.put(("error", str(exc)))
        finally:
            self.process = None

    def _cancel_run(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._append_log("\nCancellation requested.\n")
            self.status_var.set("Cancelling...")

    def _set_running_state(self, running: bool) -> None:
        self.run_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")
        self.status_var.set("Processing..." if running else "Ready")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                kind, message = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(message)
                elif kind == "done":
                    self._append_log(f"\n{message}\n")
                    self._set_running_state(False)
                    self.status_var.set(message)
                    messagebox.showinfo("Fuzzyficator complete", message)
                elif kind == "warning":
                    self._append_log(f"\nWarning: {message}\n")
                    self._set_running_state(False)
                    self.status_var.set(message)
                    messagebox.showwarning("Fuzzyficator finished without changes", message)
                elif kind == "error":
                    self._append_log(f"\nError: {message}\n")
                    self._set_running_state(False)
                    self.status_var.set(message)
                    messagebox.showerror("Fuzzyficator failed", message)
        except queue.Empty:
            pass
        self.after(120, self._drain_log_queue)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _file_digest(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _count_processing_markers(self, path: Path) -> int:
        count = 0
        with path.open("r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                if line.startswith("; G1 ") or line.startswith(";FuzzySection"):
                    count += 1
        return count

    def _open_output_folder(self) -> None:
        target = self.input_path_var.get().strip() if self.in_place_var.get() else self.output_path_var.get().strip()
        if not target:
            messagebox.showinfo("No output selected", "Choose an output file first.")
            return
        folder = Path(target).expanduser().parent
        if not folder.exists():
            messagebox.showinfo("Folder not found", str(folder))
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(folder)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Cannot open folder", str(exc))

    def _settings_payload(self) -> dict[str, object]:
        return {
            "settings_version": 2,
            "mode": self.mode_var.get(),
            "input_path": self.input_path_var.get(),
            "output_path": self.output_path_var.get(),
            "in_place": self.in_place_var.get(),
            "backup": self.backup_var.get(),
            "displacement_map": self.displacement_map_var.get(),
            "resolution": self.resolution_var.get(),
            "z_min": self.z_min_var.get(),
            "z_max": self.z_max_var.get(),
            "fuzzy_speed": self.fuzzy_speed_var.get(),
            "bridge_multiplier": self.bridge_multiplier_var.get(),
            "min_support_distance": self.min_support_distance_var.get(),
            "xy_point_dist": self.xy_point_dist_var.get(),
            "xy_thickness": self.xy_thickness_var.get(),
            "connect_walls": self.connect_walls_var.get(),
            "compensate_extrusion": self.compensate_extrusion_var.get(),
            "top_surface": self.top_surface_var.get(),
            "lower_surface": self.lower_surface_var.get(),
            "run_mode": self.run_mode_var.get(),
        }

    def _save_settings(self) -> None:
        try:
            SETTINGS_PATH.write_text(json.dumps(self._settings_payload(), indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_settings(self) -> None:
        if not SETTINGS_PATH.exists():
            self._on_in_place_changed()
            return
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._on_in_place_changed()
            return

        self.mode_var.set(str(data.get("mode", self.mode_var.get())) if data.get("mode") in MODES else self.mode_var.get())
        self.input_path_var.set(str(data.get("input_path", "")))
        self.output_path_var.set(str(data.get("output_path", "")))
        self.in_place_var.set(bool(data.get("in_place", False)))
        self.backup_var.set(bool(data.get("backup", True)))
        self.displacement_map_var.set(str(data.get("displacement_map", "")))
        self.resolution_var.set(str(data.get("resolution", "0.3")))
        self.z_min_var.set(str(data.get("z_min", "0.0")))
        self.z_max_var.set(str(data.get("z_max", "0.3")))
        self.fuzzy_speed_var.set(str(data.get("fuzzy_speed", "")))
        self.bridge_multiplier_var.set(str(data.get("bridge_multiplier", "3.0")))
        self.min_support_distance_var.set(str(data.get("min_support_distance", "0.1")))
        self.xy_point_dist_var.set(str(data.get("xy_point_dist", "0.3")))
        self.xy_thickness_var.set(str(data.get("xy_thickness", "0.3")))
        self.connect_walls_var.set(bool(data.get("connect_walls", True)))
        self.compensate_extrusion_var.set(bool(data.get("compensate_extrusion", True)))
        self.top_surface_var.set(bool(data.get("top_surface", True)))
        self.lower_surface_var.set(bool(data.get("lower_surface", True)))
        run_mode = str(data.get("run_mode", "force run"))
        if int(data.get("settings_version", 1)) < 2 and run_mode == "auto":
            run_mode = "force run"
        self.run_mode_var.set(run_mode if run_mode in {"auto", "force run", "skip processing"} else "force run")
        self._on_in_place_changed()

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Quit while running?", "Fuzzyficator is still processing. Stop it and quit?"):
                return
            self.process.terminate()
        self._save_settings()
        self.destroy()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        from Fuzzyficator_worker import main as worker_main

        raise SystemExit(worker_main(sys.argv[2:]))

    app = FuzzyficatorGui()
    app.mainloop()


if __name__ == "__main__":
    main()

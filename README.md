# Fuzzyficator Portable GUI

This is a public fork of [TengerTechnologies/Fuzzyficator](https://github.com/TengerTechnologies/Fuzzyficator) that adds a Windows desktop GUI and a single-file portable executable.

The original project is a G-code post-processing script that adds non-planar fuzzy-skin displacement to top surfaces and overhangs. This fork keeps the original processors and adds a friendlier launcher for people who do not want to run command-line scripts from a slicer.

## Download

Download the portable Windows build from the latest release:

[FuzzyficatorPortable.exe](https://github.com/noahcabral/Fuzzyficator/releases/latest/download/FuzzyficatorPortable.exe)

The portable build is a single `.exe`; no separate Python install or support folder is required.

## What This Fork Adds

- Desktop GUI for the surface, paint-on, and displacement-map processors.
- Safer default workflow that copies the input G-code to a separate output file before processing.
- Optional in-place processing with timestamped backup.
- Command preview and live processing log.
- Processing feedback when no matching movement sections were changed.
- Original G-code line ending preservation for stricter printer/slicer import paths.
- Single-file portable Windows build via PyInstaller.
- ElegooSlicer detection using Orca-style `;TYPE:Top surface` markers.

## Supported Processors

- `Fuzzyficator.py` for top/lower surface fuzzy-skin processing.
- `Fuzzyficator_paintOn.py` for paint-on fuzzy-skin sections.
- `Fuzzyficator_pattern.py` for grayscale displacement-map processing.

## Supported Slicer Markers

The underlying processors support PrusaSlicer, OrcaSlicer, and Bambu Studio style G-code markers from upstream. This fork also recognizes ElegooSlicer G-code and treats it like Orca-style output for top-surface processing.

## Using The GUI From Source

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the GUI:

```powershell
python Fuzzyficator_gui.py
```

On Windows, you can also run:

```powershell
launch_gui.bat
```

## Building

Build the single-file portable EXE:

```powershell
build_portable_exe.bat
```

Output:

```text
dist\FuzzyficatorPortable.exe
```

Build the folder-based app distribution:

```powershell
build_exe.bat
```

Output:

```text
dist\Fuzzyficator\Fuzzyficator.exe
```

## Notes

Fuzzyficator modifies the G-code file it is given. The GUI avoids accidental overwrites by copying your selected input file to the selected output path before running the processor, unless you explicitly enable direct in-place processing.

For a stronger visible effect on very short top-surface strokes, try lowering `Resolution` or disabling `Connect walls`.

## Upstream And License

This fork is based on [TengerTechnologies/Fuzzyficator](https://github.com/TengerTechnologies/Fuzzyficator) by Roman Tenger.

The project is licensed under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE).

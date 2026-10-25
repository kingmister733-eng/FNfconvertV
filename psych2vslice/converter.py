"""Core conversion logic.

Target formats (verified against FunkinCrew/Funkin source, SongData.hx and
SongRegistry.hx): metadata version 2.2.4, chart version 2.0.0.
"""
import json
import os
import re

METADATA_VERSION = "2.2.4"
CHART_VERSION = "2.0.0"
GENERATED_BY = "psych2vslice"
DEFAULT_NOTE_STYLE = "funkin"
KNOWN_DIFFICULTIES = ("easy", "normal", "hard", "erect", "nightmare")
SCRIPT_EXTS = (".lua", ".hx", ".hscript")


class Report:
    """Collects incompatibilities. Each item: (severity, file, message)."""

    def __init__(self):
        self.items = []

    def add(self, severity, file, message):
        item = {"severity": severity, "file": file, "message": message}
        if item not in self.items:
            self.items.append(item)

    def to_dict(self):
        return {"issues": self.items}

    def to_markdown(self):
        lines = ["# Conversion report", ""]
        if not self.items:
            lines.append("No incompatibilities found.")
        for sev in ("manual", "warning", "info"):
            group = [i for i in self.items if i["severity"] == sev]
            if group:
                lines += [f"## {sev} ({len(group)})", ""]
                lines += [f"- `{i['file']}`: {i['message']}" for i in group]
                lines.append("")
        return "\n".join(lines)


def _unwrap(data):
    if isinstance(data, dict) and isinstance(data.get("song"), dict):
        return data["song"]
    return data


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _clean(x):
    """Render floats that are whole numbers as ints for tidy JSON."""
    return int(x) if isinstance(x, float) and x.is_integer() else x


def convert_chart(psych, report=None, name="chart"):
    """Convert a Psych chart dict to (notes, events, time_changes, info)."""
    report = report or Report()
    song = _unwrap(psych)
    if not isinstance(song, dict) or not isinstance(song.get("notes"), list):
        raise ValueError(f"{name}: not a Psych Engine chart (missing 'notes' list)")

    bpm = _num(song.get("bpm"), 100.0)
    time_changes = [{"t": 0, "b": 0, "bpm": _clean(bpm), "n": 4, "d": 4}]
    notes, events = [], []
    section_time, beat = 0.0, 0.0
    last_focus = None
    kinds = set()

    for idx, sec in enumerate(song["notes"]):
        if sec.get("changeBPM") and _num(sec.get("bpm")) > 0 and _num(sec["bpm"]) != bpm:
            bpm = _num(sec["bpm"])
            time_changes.append({"t": _clean(round(section_time, 3)), "b": _clean(beat),
                                 "bpm": _clean(bpm), "n": 4, "d": 4})
        must_hit = bool(sec.get("mustHitSection"))
        if sec.get("gfSection"):
            report.add("warning", name, "gfSection used: camera/notes of GF sections are treated as opponent side")
        focus = 0 if must_hit else 1
        if focus != last_focus:
            events.append({"t": _clean(round(section_time, 3)), "e": "FocusCamera", "v": {"char": focus}})
            last_focus = focus
        if sec.get("altAnim"):
            report.add("warning", name, "altAnim sections are not converted (no V-Slice chart field)")

        for n in sec.get("sectionNotes", []):
            if not isinstance(n, list) or len(n) < 3:
                report.add("warning", name, f"skipped malformed note {n!r}")
                continue
            d = int(n[1])
            if d < 0:
                report.add("warning", name, "skipped note with negative lane")
                continue
            # Psych: lanes 0-3 belong to the section's side; V-Slice: 0-3 player, 4-7 opponent.
            player_lane = (d < 4) == must_hit
            lane = d % 4 + (0 if player_lane else 4)
            out = {"t": _clean(_num(n[0])), "d": lane}
            if _num(n[2]) > 0:
                out["l"] = _clean(_num(n[2]))
            if len(n) > 3 and isinstance(n[3], str) and n[3]:
                out["k"] = n[3]
                kinds.add(n[3])
            notes.append(out)

        section_time += 4 * 60000.0 / bpm  # Psych sections are 4 beats (16 steps)
        beat += 4

    for k in sorted(kinds):
        report.add("manual", name, f"custom note type '{k}' kept as note kind; needs a V-Slice note kind script")

    for ev in song.get("events", []) or []:
        if not (isinstance(ev, list) and len(ev) == 2):
            continue
        for e in ev[1]:
            ename = e[0] if e else "?"
            if ename == "Camera Follow Pos":
                x, y = _num(e[1], None), _num(e[2], None)
                if x is None and y is None:
                    events.append({"t": _clean(_num(ev[0])), "e": "FocusCamera", "v": {"char": 0}})
                else:
                    events.append({"t": _clean(_num(ev[0])), "e": "FocusCamera",
                                   "v": {"char": -1, "x": _clean(x or 0.0), "y": _clean(y or 0.0)}})
                report.add("info", name, "'Camera Follow Pos' converted to FocusCamera (char -1 = absolute position)")
            else:
                report.add("manual", name, f"event '{ename}' has no automatic V-Slice equivalent; dropped")
    events.sort(key=lambda e: e["t"])
    notes.sort(key=lambda n: n["t"])

    info = {
        "bpm": _num(song.get("bpm"), 100.0),
        "speed": _num(song.get("speed"), 1.0),
        "player1": song.get("player1") or "bf",
        "player2": song.get("player2") or "dad",
        "gf": song.get("gfVersion") or song.get("player3") or "gf",
        "stage": song.get("stage") or "mainStage",
        "song": song.get("song") if isinstance(song.get("song"), str) else None,
        "needsVoices": song.get("needsVoices", True),
    }
    if song.get("arrowSkin") or song.get("splashSkin"):
        report.add("warning", name, "custom arrowSkin/splashSkin not converted (V-Slice uses noteStyle)")
    return notes, events, time_changes, info


def build_metadata(song_name, artist, difficulties, info, time_changes, charter=None):
    meta = {
        "version": METADATA_VERSION,
        "songName": song_name,
        "artist": artist,
        "timeFormat": "ms",
        "divisions": 96,
        "looped": False,
        "offsets": {"instrumental": 0, "altInstrumentals": {}, "vocals": {}, "altVocals": {}},
        "playData": {
            "songVariations": [],
            "difficulties": difficulties,
            "characters": {"player": info["player1"], "girlfriend": info["gf"],
                           "opponent": info["player2"], "instrumental": ""},
            "stage": info["stage"],
            "noteStyle": DEFAULT_NOTE_STYLE,
            "ratings": {d: 1 for d in difficulties},
        },
        "generatedBy": GENERATED_BY,
        "timeChanges": time_changes,
    }
    if charter:
        meta["charter"] = charter
    return meta


def _diff_of(filename, slug):
    base = os.path.splitext(filename)[0]
    if base == slug:
        return "normal"
    if base.startswith(slug + "-"):
        return base[len(slug) + 1:].lower()
    return None


def convert_song_dir(src_dir, out_dir, artist="Unknown", report=None, song_name=None):
    """Convert one Psych song folder (data/<slug>/<slug>[-diff].json)."""
    report = report or Report()
    slug = os.path.basename(os.path.normpath(src_dir))
    charts = {}
    for fn in sorted(os.listdir(src_dir)):
        if not fn.lower().endswith(".json"):
            continue
        diff = _diff_of(fn, slug)
        if diff is None:
            continue
        path = os.path.join(src_dir, fn)
        try:
            with open(path, encoding="utf-8-sig") as f:
                charts[diff] = convert_chart(json.load(f), report, name=f"{slug}/{fn}")
        except (ValueError, json.JSONDecodeError) as exc:
            report.add("warning", f"{slug}/{fn}", f"skipped: {exc}")
    if not charts:
        return None
    for fn in sorted(os.listdir(src_dir)):
        if fn.lower().endswith(SCRIPT_EXTS):
            report.add("manual", f"{slug}/{fn}", "script not converted; requires manual adaptation")

    order = [d for d in KNOWN_DIFFICULTIES if d in charts] + sorted(d for d in charts if d not in KNOWN_DIFFICULTIES)
    base = charts.get("normal") or charts[order[0]]
    info = base[3]
    title = song_name or info["song"] or slug.replace("-", " ").title()
    meta = build_metadata(title, artist, order, info, base[2])
    chart = {
        "version": CHART_VERSION,
        "scrollSpeed": {d: _clean(charts[d][3]["speed"]) for d in order},
        "events": base[1],
        "notes": {d: charts[d][0] for d in order},
        "generatedBy": GENERATED_BY,
    }
    for d in order:
        if charts[d][2] != base[2]:
            report.add("warning", f"{slug}", f"difficulty '{d}' has different BPM changes; metadata uses '{'normal' if 'normal' in charts else order[0]}'")
        if charts[d][1] != base[1]:
            report.add("warning", f"{slug}", f"difficulty '{d}' has different events; V-Slice has one shared event list")
    dest = os.path.join(out_dir, slug)
    os.makedirs(dest, exist_ok=True)
    for name, obj in ((f"{slug}-metadata.json", meta), (f"{slug}-chart.json", chart)):
        with open(os.path.join(dest, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
    if not info["needsVoices"]:
        report.add("info", slug, "needsVoices=false: do not provide a vocals file")
    report.add("info", slug, "artist not stored in Psych charts; set via --artist or edit metadata")
    report.add("manual", slug, "character IDs/stage IDs are copied as-is; matching V-Slice character/stage data must exist")
    return dest


def convert_mod(mod_dir, out_dir, artist="Unknown"):
    """Convert every song in <mod>/data/*; returns (converted_dirs, Report)."""
    report = Report()
    data = os.path.join(mod_dir, "data")
    done = []
    if not os.path.isdir(data):
        raise ValueError(f"{mod_dir}: no 'data' folder found")
    for entry in sorted(os.listdir(data)):
        p = os.path.join(data, entry)
        if os.path.isdir(p):
            r = convert_song_dir(p, os.path.join(out_dir, "data", "songs"), artist, report)
            if r:
                done.append(r)
    for sub in ("scripts", "custom_events", "custom_notetypes", "stages", "characters"):
        p = os.path.join(mod_dir, sub)
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for fn in sorted(files):
                    rel = os.path.relpath(os.path.join(root, fn), mod_dir)
                    if fn.lower().endswith(SCRIPT_EXTS):
                        report.add("manual", rel, "script not converted; requires manual adaptation")
                    elif sub in ("stages", "characters") and fn.lower().endswith(".json"):
                        report.add("manual", rel, f"Psych {sub[:-1]} JSON not converted yet (planned)")
    return done, report

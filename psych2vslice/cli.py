import argparse
import json
import os

from .converter import convert_mod, convert_song_dir, Report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="psych2vslice", description="Convert Psych Engine songs to V-Slice JSON.")
    ap.add_argument("input", help="Psych mod folder (with data/), or a single song folder with --song")
    ap.add_argument("output", help="output folder")
    ap.add_argument("--song", action="store_true", help="input is one song folder (data/<name>)")
    ap.add_argument("--artist", default="Unknown")
    args = ap.parse_args(argv)

    if args.song:
        report = Report()
        done = [convert_song_dir(args.input, os.path.join(args.output, "data", "songs"), args.artist, report)]
        done = [d for d in done if d]
    else:
        done, report = convert_mod(args.input, args.output, args.artist)
    os.makedirs(args.output, exist_ok=True)
    with open(os.path.join(args.output, "conversion_report.md"), "w", encoding="utf-8") as f:
        f.write(report.to_markdown())
    with open(os.path.join(args.output, "conversion_report.json"), "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"Converted {len(done)} song(s); {len(report.items)} report item(s) -> {args.output}/conversion_report.md")
    return 0 if done else 1

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from psych2vslice import convert_chart, convert_mod  # noqa: E402
from psych2vslice.cli import main  # noqa: E402

CHART = {"song": {
    "song": "Test Song", "bpm": 120, "speed": 2.5, "needsVoices": True,
    "player1": "bf", "player2": "pico", "gfVersion": "gf", "stage": "stage",
    "notes": [
        {"mustHitSection": True, "sectionNotes": [[0, 0, 0], [500, 5, 250, "Hurt Note"]]},
        {"mustHitSection": False, "changeBPM": True, "bpm": 60, "sectionNotes": [[2000, 1, 0], [2500, 6, 0]]},
    ],
    "events": [[1000, [["Camera Follow Pos", "10", "20"], ["Screen Shake", "1, 0.1", ""], ["Play Animation", "hey", "Boyfriend"]]]],
}}


class ConverterTest(unittest.TestCase):
    def test_chart(self):
        notes, events, tcs, info = convert_chart(CHART)
        # section 1 mustHit: lane0 -> player 0; lane5 -> opponent lane 5
        self.assertEqual(notes[0], {"t": 0, "d": 0})
        self.assertEqual(notes[1], {"t": 500, "d": 5, "l": 250, "k": "Hurt Note"})
        # section 2 not mustHit: lane1 -> opponent 5; lane6 -> player 2
        self.assertEqual(notes[2]["d"], 5)
        self.assertEqual(notes[3]["d"], 2)
        # 4 beats at 120bpm = 2000ms -> BPM change at 2000ms, beat 4
        self.assertEqual(tcs[1], {"t": 2000, "b": 4, "bpm": 60, "n": 4, "d": 4})
        kinds = [(e["t"], e["e"], e["v"]) for e in events]
        self.assertIn((0, "FocusCamera", {"char": 0}), kinds)
        self.assertIn((2000, "FocusCamera", {"char": 1}), kinds)
        self.assertIn((1000, "FocusCamera", {"char": -1, "x": 10, "y": 20}), kinds)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            convert_chart({"foo": 1})

    def test_mod_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = os.path.join(tmp, "mod"), os.path.join(tmp, "out")
            sd = os.path.join(src, "data", "test-song")
            os.makedirs(sd)
            os.makedirs(os.path.join(src, "scripts"))
            for fn in ("test-song.json", "test-song-hard.json"):
                with open(os.path.join(sd, fn), "w") as f:
                    json.dump(CHART, f)
            ad = os.path.join(src, "songs", "test-song")
            os.makedirs(ad)
            for fn in ("Inst.ogg", "Voices.ogg", "Voices-player.ogg", "extra.mp3"):
                open(os.path.join(ad, fn), "wb").write(b"x")
            open(os.path.join(sd, "script.lua"), "w").close()
            open(os.path.join(src, "scripts", "x.hx"), "w").close()
            self.assertEqual(main([src, out, "--artist", "Me"]), 0)
            d = os.path.join(out, "data", "songs", "test-song")
            meta = json.load(open(os.path.join(d, "test-song-metadata.json")))
            chart = json.load(open(os.path.join(d, "test-song-chart.json")))
            self.assertEqual(meta["version"], "2.2.4")
            self.assertEqual(meta["artist"], "Me")
            self.assertEqual(meta["playData"]["difficulties"], ["normal", "hard"])
            self.assertEqual(meta["playData"]["characters"]["opponent"], "pico")
            self.assertEqual(chart["version"], "2.0.0")
            self.assertEqual(chart["scrollSpeed"], {"normal": 2.5, "hard": 2.5})
            self.assertEqual(set(chart["notes"]), {"normal", "hard"})
            rep = open(os.path.join(out, "conversion_report.md")).read()
            ao = os.path.join(out, "songs", "test-song")
            self.assertEqual(sorted(os.listdir(ao)), ["Inst.ogg", "Voices-bf.ogg", "Voices.ogg"])
            self.assertIn("extra.mp3", rep)
            self.assertTrue(any(e["e"] == "PlayAnimation" and e["v"] == {"target": "bf", "anim": "hey", "force": True} for e in chart["events"]))
            self.assertIn("script.lua", rep)
            self.assertIn("scripts/x.hx", rep)
            self.assertIn("Screen Shake", rep)
            self.assertIn("Hurt Note", rep)


if __name__ == "__main__":
    unittest.main()

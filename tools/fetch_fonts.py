"""Fetch the bundled faces (Latin subsets, woff2) and their OFL licences from
Google Fonts into fonts/, with fonts.json saying what each file is. Run from
the repo root: python tools/fetch_fonts.py"""

import json
import re
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
OUT = Path(__file__).resolve().parent.parent / "fonts"
# group, CSS2 family spec, google/fonts licence folder
FAMILIES = [
    ("jost", "Jost:wght@300..800", "jost"),
    ("anton", "Anton", "anton"),
    ("inter_tight", "Inter+Tight:wght@400..900", "intertight"),
    ("plex_mono", "IBM+Plex+Mono:wght@400;500", "ibmplexmono"),
    ("poiret", "Poiret+One", "poiretone"),
    ("cormorant", "Cormorant+Garamond:ital,wght@0,600;1,500", "cormorantgaramond"),
    ("alfa_slab", "Alfa+Slab+One", "alfaslabone"),
    ("bungee", "Bungee", "bungee"),
]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    manifest = {}
    for group, spec, lic in FAMILIES:
        css = get(
            f"https://fonts.googleapis.com/css2?family={spec}&display=swap"
        ).decode()
        for sub, block in re.findall(
            r"/\* ([\w-]+) \*/\s*(@font-face \{.*?\})", css, re.S
        ):
            if sub != "latin":
                continue
            fam = re.search(r"font-family: '([^']+)'", block).group(1)
            style = re.search(r"font-style: (\w+)", block).group(1)
            weight = re.search(r"font-weight: ([\d ]+)", block).group(1).strip()
            url = re.search(r"url\((https://[^)]+)\)", block).group(1)
            rng = re.search(r"unicode-range: ([^;]+);", block).group(1)
            name = f"{group}-{style}-{weight.replace(' ', '_')}.woff2"
            (OUT / name).write_bytes(get(url))
            manifest[name] = {
                "family": fam,
                "weight": weight,
                "style": style,
                "range": rng,
                "group": group,
            }
        (OUT / f"LICENSE-{lic}.txt").write_bytes(
            get(
                f"https://raw.githubusercontent.com/google/fonts/main/ofl/{lic}/OFL.txt"
            )
        )
    (OUT / "fonts.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(len(manifest), "faces")


if __name__ == "__main__":
    main()

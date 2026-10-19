"""Poster widget.

A framed print for the wall, a new one each day (or hour, or week), in one of
fourteen styles of three kinds:

  * drawn   - Bauhaus patterns, Swiss, Constructivist, ridgelines, Memphis,
              mid-century sunburst. Drawn in the render browser from a seed;
              no network, no key, nothing to pay.
  * museum  - a public-domain painting or woodblock print from the Art
              Institute of Chicago's open-access collection, hung with its
              label. Keyless.
  * painted - an AI picture of a subject (a bird, a place, a plant) made once
              through fal.ai on Tesserae's Artwork API, with the poster's
              words set over it in real fonts: the model is never asked for
              lettering. The small print comes from Wikipedia; a woodblock's
              Japanese name from Wikipedia's Japanese article title.

Every lettering face is bundled (fonts/, SIL Open Font License) and sent as
a data URI; the Japanese label's face is fetched from Google Fonts cut down to
the characters it needs, and kept.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLUGIN_ID = "poster"
UA = "tesserae-poster/0.1 (+https://github.com/dmellok/tesserae-widget-poster)"
TIMEOUT_S = 8

try:
    from app import artwork  # Tesserae 0.463+: the pictures a widget makes and keeps
    from app import fal as _fal
except ImportError:  # an older Tesserae: drawn and museum posters still work
    artwork = None  # type: ignore[assignment]
    _fal = None  # type: ignore[assignment]

NEEDS_HOST = "AI posters need Tesserae 0.463 or later; this server is older."

# ----------------------------------------------------------------------
# Styles
# ----------------------------------------------------------------------

# id -> label, kind, font groups
STYLES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "ausstellung": ("Ausstellung: Bauhaus patterns", "drawn", ("jost",)),
    "swiss": ("Swiss: big type and circles", "drawn", ("inter_tight", "plex_mono")),
    "constructivist": (
        "Constructivist: red and black diagonals",
        "drawn",
        ("anton", "jost"),
    ),
    "ridgeline": (
        "Ridgeline: stacked waves on black",
        "drawn",
        ("inter_tight", "plex_mono"),
    ),
    "memphis": ("Memphis: confetti shapes", "drawn", ("bungee", "jost")),
    "sunburst": ("Sunburst: mid-century sun and hills", "drawn", ("alfa_slab", "jost")),
    "gallery": ("Gallery print: modern masters", "museum", ("inter_tight",)),
    "ukiyoe": ("Gallery print: Japanese woodblocks", "museum", ("inter_tight",)),
    "woodblock": ("Woodblock: AI ink print, Japanese label", "painted", ("plex_mono",)),
    "travel": ("Travel poster: AI screen print", "painted", ("anton", "plex_mono")),
    "deco": ("Art deco: AI national-park poster", "painted", ("poiret", "jost")),
    "riso": ("Risograph: AI two-colour print", "painted", ("anton", "plex_mono")),
    "botanical": ("Botanical plate: AI", "painted", ("cormorant", "plex_mono")),
    "linocut": (
        "Linocut: AI black ink and one colour",
        "painted",
        ("alfa_slab", "plex_mono"),
    ),
}
MIXES = {
    "mix_free": ("Mix: a different free style each time", ("drawn", "museum")),
    "mix_all": ("Mix: any style, AI included", ("drawn", "museum", "painted")),
}

# What each painted style asks the model for. {subject} is the subject's
# name with its Wikipedia description; the picture never carries words.
PROMPTS = {
    "woodblock": (
        "Japanese woodblock print, fine ink line illustration with hatching on warm aged "
        "cream paper: {subject}. Muted greens, indigo, cream, black, a touch of vermilion. "
        "The subject sits a little left of centre with generous empty paper around it and the "
        "right sixth of the sheet left completely empty."
    ),
    "travel": (
        "Vintage travel poster illustration, screen printed in flat inks: {subject}, a "
        "landmark scene with a large low sun or moon behind and horizontal scanline fades. "
        "Flat deep green, rust red, ochre, cream and a black outline, warm paper grain. "
        "The scene is a vignette on plain cream paper that fills to the edges."
    ),
    "deco": (
        "1930s art deco national park poster, WPA screen print style: {subject}. Bold "
        "simplified shapes, layered silhouettes of the land, a dramatic graded sky, flat "
        "colours in deep teal, burnt orange, gold, cream and navy. The scene fills the whole "
        "canvas edge to edge: no border, no margin, no white or cream edge, no inner frame."
    ),
    "riso": (
        "Risograph print in two inks, fluorescent pink and teal blue, on off-white paper: "
        "{subject}. Bold simple shapes, halftone dots, visible grain and slight "
        "misregistration where the inks overlap. Subject large in the upper two thirds; "
        "the lower third mostly plain paper with a little halftone texture."
    ),
    "botanical": (
        "Antique botanical plate, hand-coloured copperplate engraving: {subject}, one "
        "specimen showing leaves, flower and seed or fruit, with a small dissected detail. "
        "Fine line work, soft watercolour washes, on plain aged cream paper with wide empty "
        "margins all round."
    ),
    "linocut": (
        "Linocut relief print: {subject}. Bold carved black ink with gouge marks, and a "
        "single accent colour of burnt orange in a few areas, on cream paper. Strong "
        "silhouette, centred, with an even cream margin around the block."
    ),
}
# Part of every picture's key: raise it when the prompts change so posters
# are painted afresh instead of the old pictures being reused.
PROMPT_V = 1
NO_WORDS = (
    " No text, no letters, no numbers, no signature, no seal, no watermark, no frame."
)

# Built-in subjects when the cell gives none: a line is subject | label | year.
SUBJECTS = {
    "woodblock": [
        "Laughing kookaburra",
        "Red-crowned crane",
        "Common kingfisher",
        "Mandarin duck",
        "Japanese macaque",
        "Grey heron",
        "Red fox",
        "Koi",
        "Platypus",
        "Green sea turtle",
        "Snow leopard",
        "Barn swallow",
        "Common octopus",
        "Japanese raccoon dog",
    ],
    "travel": [
        "Aireys Inlet | Split Point | 1891",
        "Kyoto",
        "Lisbon",
        "Hobart",
        "Reykjavík",
        "Valparaíso",
        "Queenstown, New Zealand",
        "Santorini",
        "Banff, Alberta",
        "Cinque Terre",
        "Byron Bay",
        "Marrakesh",
        "Kotor",
        "Wilsons Promontory",
    ],
    "deco": [
        "Grampians National Park",
        "Yosemite National Park",
        "Cradle Mountain-Lake St Clair National Park",
        "Banff National Park",
        "Torres del Paine National Park",
        "Fiordland National Park",
        "Zion National Park",
        "Lake District",
        "Plitvice Lakes National Park",
        "Mount Fuji",
        "Grand Canyon National Park",
        "Freycinet National Park",
    ],
    "riso": [
        "Tram",
        "Espresso",
        "Record player",
        "Lighthouse",
        "Ferris wheel",
        "Typewriter",
        "Cassette tape",
        "Hot air balloon",
        "Sailboat",
        "Cactus",
        "Monstera deliciosa",
        "Penny-farthing",
    ],
    "botanical": [
        "Banksia serrata",
        "Telopea speciosissima",
        "Eucalyptus globulus",
        "Strelitzia reginae",
        "Protea cynaroides",
        "Nelumbo nucifera",
        "Ginkgo biloba",
        "Camellia sinensis",
        "Digitalis purpurea",
        "Passiflora caerulea",
        "Helianthus annuus",
        "Iris germanica",
        "Magnolia grandiflora",
        "Anigozanthos manglesii",
    ],
    "linocut": [
        "Barn owl",
        "Atlantic puffin",
        "Common raven",
        "Black swan",
        "Common wombat",
        "Short-beaked echidna",
        "Orca",
        "Lucanus cervus",
        "Luna moth",
        "Grey wolf",
        "American bison",
        "European hare",
        "Tiger",
    ],
}

# Where the picture sits on a painted poster, as shares of the poster's width
# and height, upright and lying down. The client lays the words around it.
REGION = {
    "woodblock": {"p": (1.0, 1.0), "l": (1.0, 1.0)},
    "travel": {"p": (1.0, 0.66), "l": (0.6, 1.0)},
    "deco": {"p": (1.0, 0.74), "l": (0.62, 1.0)},
    "riso": {"p": (1.0, 1.0), "l": (1.0, 1.0)},
    "botanical": {"p": (0.84, 0.7), "l": (0.5, 0.86)},
    "linocut": {"p": (0.86, 0.68), "l": (0.56, 0.84)},
}
ASPECTS = [
    ("9:16", 9 / 16),
    ("2:3", 2 / 3),
    ("3:4", 3 / 4),
    ("1:1", 1.0),
    ("4:3", 4 / 3),
    ("3:2", 3 / 2),
    ("16:9", 16 / 9),
]

# Museum presets: the artists a style draws from, searched in the Art
# Institute of Chicago's public-domain works.
MUSEUM = {
    "gallery": [
        "Vasily Kandinsky",
        "Piet Mondrian",
        "Paul Cézanne",
        "Georges Seurat",
        "Vincent van Gogh",
        "Paul Gauguin",
        "Claude Monet",
        "Juan Gris",
        "Franz Marc",
        "Henri de Toulouse-Lautrec",
        "Gustave Caillebotte",
        "Odilon Redon",
    ],
    "ukiyoe": [
        "Utagawa Hiroshige",
        "Katsushika Hokusai",
        "Utagawa Kuniyoshi",
        "Kitagawa Utamaro",
        "Keisai Eisen",
        "Utagawa Kunisada",
    ],
}
AIC_SEARCH = "https://api.artic.edu/api/v1/artworks/search"
AIC_IIIF = "https://www.artic.edu/iiif/2/{id}/full/{w},/0/default.jpg"

CHANGES = {"daily", "hourly", "weekly", "render"}
MODELS = {"nano_banana_t2i", "flux_schnell"}
WEEKDAY_KANJI = "月火水木金土日"

_LOCK = threading.Lock()


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "x"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data: Any) -> None:
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


def _get(
    url: str, *, headers: dict[str, str] | None = None, timeout: float = TIMEOUT_S
) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return bytes(resp.read())


def _hash(*parts: Any) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16)


def _bucket(change: str, now: datetime) -> tuple[str, int]:
    """The period a poster belongs to, as a label and a running number."""
    day = now.toordinal()
    if change == "hourly":
        return now.strftime("%Y-%m-%dT%H"), day * 24 + now.hour
    if change == "weekly":
        y, w, _ = now.isocalendar()
        return f"{y}-W{w:02d}", day // 7
    if change == "render":
        n = int(time.time() // 60)
        return str(n), n
    return now.strftime("%Y-%m-%d"), day


def _tokens(text: str, now: datetime) -> str:
    rep = {
        "{weekday}": now.strftime("%A"),
        "{day}": str(now.day),
        "{month}": now.strftime("%B"),
        "{monthnum}": f"{now.month:02d}",
        "{year}": str(now.year),
    }
    for k, v in rep.items():
        text = text.replace(k, v)
    return text


DRAWN_TEXT = {
    "ausstellung": ("Ausstellung", "{year}"),
    "swiss": ("{weekday}", "{day} {month} {year}"),
    "constructivist": ("{weekday}", "{day}.{monthnum}.{year}"),
    "ridgeline": ("{weekday}", "{day} {month} {year}"),
    "memphis": ("{weekday}", "{day} {month}"),
    "sunburst": ("{weekday}", "{day} {month} {year}"),
}


def font_css(groups: tuple[str, ...]) -> str:
    """@font-face rules for the bundled faces in ``groups``, as data URIs."""
    manifest = _read_json(HERE / "fonts" / "fonts.json", {})
    rules = []
    for file, face in manifest.items():
        if face.get("group") not in groups:
            continue
        try:
            data = base64.b64encode((HERE / "fonts" / file).read_bytes()).decode()
        except OSError:
            continue
        rules.append(
            f"@font-face{{font-family:'{face['family']}';font-style:{face['style']};"
            f"font-weight:{face['weight']};font-display:block;"
            f"src:url(data:font/woff2;base64,{data}) format('woff2');unicode-range:{face['range']};}}"
        )
    return "".join(rules)


def cjk_font_css(text: str, data_dir: Path) -> str:
    """Shippori Mincho cut down to ``text`` from Google Fonts, kept on disk."""
    chars = "".join(sorted(set(text)))
    if not chars:
        return ""
    store = (
        data_dir
        / "fonts"
        / f"mincho-{hashlib.sha1(chars.encode()).hexdigest()[:16]}.bin"
    )
    raw = b""
    if store.exists():
        with contextlib.suppress(OSError):
            raw = store.read_bytes()
    if not raw:
        try:
            css = _get(
                "https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@800&text="
                + urllib.parse.quote(chars),
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/126 Safari/537.36"
                },
            ).decode("utf-8", "replace")
            m = re.search(r"url\((https://[^)]+)\)", css)
            raw = _get(m.group(1)) if m else b""
        except (OSError, urllib.error.URLError, ValueError):
            raw = b""
        if raw:
            with contextlib.suppress(OSError):
                store.parent.mkdir(parents=True, exist_ok=True)
                store.write_bytes(raw)
    if not raw:
        return ""
    fmt = "woff2" if raw[:4] == b"wOF2" else "truetype"
    data = base64.b64encode(raw).decode()
    return (
        "@font-face{font-family:'Shippori Mincho';font-weight:800;font-display:block;"
        f"src:url(data:font/{fmt};base64,{data}) format('{fmt}');}}"
    )


# ----------------------------------------------------------------------
# Words: Wikipedia
# ----------------------------------------------------------------------

WIKI_TTL_S = 30 * 86400
WIKI_MISS_S = 86400


def wiki(subject: str, data_dir: Path) -> dict[str, str]:
    """A subject's Wikipedia title, short description, opening sentences and
    Japanese title, kept a month."""
    path = data_dir / "wiki.json"
    with _LOCK:
        cache = _read_json(path, {})
    hit = cache.get(subject)
    now = time.time()
    if isinstance(hit, dict) and now - float(hit.get("t") or 0) < (
        WIKI_TTL_S if hit.get("title") else WIKI_MISS_S
    ):
        return hit
    out: dict[str, Any] = {"t": now, "title": "", "desc": "", "extract": "", "ja": ""}
    try:
        s = json.loads(
            _get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(subject.replace(" ", "_"))
            )
        )
        out["title"] = str(s.get("title") or "")
        out["desc"] = str(s.get("description") or "")
        out["extract"] = str(s.get("extract") or "")
    except (OSError, urllib.error.URLError, ValueError):
        pass
    if out["title"]:
        with contextlib.suppress(OSError, urllib.error.URLError, ValueError, KeyError):
            q = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
                {
                    "action": "query",
                    "prop": "langlinks",
                    "lllang": "ja",
                    "titles": out["title"],
                    "format": "json",
                    "redirects": 1,
                }
            )
            pages = json.loads(_get(q))["query"]["pages"]
            for pg in pages.values():
                for ll in pg.get("langlinks") or []:
                    out["ja"] = re.sub(r"\s*\(.*?\)\s*", "", str(ll.get("*") or ""))
    with _LOCK:
        cache = _read_json(path, {})
        cache[subject] = out
        _write_json(path, cache)
    return out


def blurb(extract: str, limit: int = 230) -> str:
    """The opening sentences of an extract, whole sentences, within ``limit``."""
    text = re.sub(r"\s*\([^()]*\)", "", extract).strip()
    text = re.sub(r"\s+", " ", text)
    out = ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if len(out) + len(sent) + 1 > limit:
            break
        out = f"{out} {sent}".strip()
    if not out and text:
        out = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return out


def common_name(extract: str) -> str:
    """The common name an article's opening gives a species ("commonly known
    as the old man banksia"), if it gives one."""
    m = re.search(
        r"(?:commonly|also|usually) (?:known|called) as (?:the |an? )?([^,;.()]+)",
        extract,
    )
    return m.group(1).strip() if m else ""


def words_for(
    style: str, row: dict[str, str], data_dir: Path, facts: bool
) -> dict[str, str]:
    """Everything a painted poster prints about one subject."""
    subject = row["subject"]
    info = wiki(subject, data_dir)
    return {
        "name": subject,
        "label": row.get("label") or "",
        "year": row.get("year") or "",
        "desc": info.get("desc") or "",
        "facts": blurb(info.get("extract") or "") if facts else "",
        "ja": row.get("label")
        if style == "woodblock" and row.get("label")
        else info.get("ja") or "",
        "common": common_name(info.get("extract") or "")
        if style == "botanical"
        else "",
        "source": "Wikipedia" if facts and info.get("extract") else "",
    }


def parse_subjects(text: str) -> list[dict[str, str]]:
    rows = []
    for line in str(text or "").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if not parts or not parts[0] or parts[0].startswith("#"):
            continue
        rows.append(
            {
                "subject": parts[0],
                "label": parts[1] if len(parts) > 1 else "",
                "year": parts[2] if len(parts) > 2 else "",
            }
        )
    return rows


# ----------------------------------------------------------------------
# Museum prints: the Art Institute of Chicago
# ----------------------------------------------------------------------

SEARCH_TTL_S = 30 * 86400


def _aic_headers() -> dict[str, str]:
    # The image host refuses a request without the AIC-User-Agent header
    # their API documentation asks every client to send.
    return {"AIC-User-Agent": UA}


def museum_search(query: str, data_dir: Path) -> list[dict[str, Any]]:
    path = data_dir / "museum" / f"search-{_slug(query)}.json"
    hit = _read_json(path, None)
    if isinstance(hit, dict) and time.time() - float(hit.get("t") or 0) < SEARCH_TTL_S:
        return list(hit.get("rows") or [])
    url = (
        AIC_SEARCH
        + "?"
        + urllib.parse.urlencode(
            {
                "q": query,
                "query[term][is_public_domain]": "true",
                "fields": "id,title,artist_title,artist_display,date_display,image_id,thumbnail,medium_display",
                "limit": "40",
            }
        )
    )
    try:
        got = json.loads(_get(url, headers=_aic_headers()))
    except (OSError, urllib.error.URLError, ValueError):
        return list(hit.get("rows") or []) if isinstance(hit, dict) else []
    rows = []
    for a in got.get("data") or []:
        if not a.get("image_id"):
            continue
        th = a.get("thumbnail") or {}
        rows.append(
            {
                "id": a.get("id"),
                "title": a.get("title") or "",
                "artist": a.get("artist_title") or "",
                "artist_display": a.get("artist_display") or "",
                "date": a.get("date_display") or "",
                "medium": a.get("medium_display") or "",
                "image_id": a["image_id"],
                "w": int(th.get("width") or 0),
                "h": int(th.get("height") or 0),
            }
        )
    _write_json(path, {"t": time.time(), "rows": rows})
    return rows


def museum_image(row: dict[str, Any], data_dir: Path, px: int) -> tuple[bytes, bool]:
    """The work's picture, kept on disk, and whether the museum refused it
    (some works listed as public domain have their image withheld)."""
    path = data_dir / "museum" / f"{row['image_id']}.jpg"
    if path.exists():
        with contextlib.suppress(OSError):
            return path.read_bytes(), False
    raw, refused = b"", False
    for w in (1686, 843):
        try:
            raw = _get(
                AIC_IIIF.format(id=row["image_id"], w=w),
                headers=_aic_headers(),
                timeout=20,
            )
        except urllib.error.HTTPError as err:
            raw, refused = b"", err.code in (403, 404)
            continue
        except (OSError, urllib.error.URLError):
            return b"", False
        if raw[:2] == b"\xff\xd8":
            refused = False
            break
        raw = b""
    if raw:
        with contextlib.suppress(OSError):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    return raw, refused


def _shrink(raw: bytes, px: int) -> bytes:
    """A JPEG no longer than ``px`` on its long edge, when Pillow is there."""
    try:
        from PIL import Image
    except ImportError:
        return raw
    try:
        im = Image.open(io.BytesIO(raw))
        if max(im.size) <= px:
            return raw
        im.thumbnail((px, px))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=86)
        return buf.getvalue()
    except Exception:
        return raw


def museum_candidates(
    style: str, query: str, n: int, portrait: bool, data_dir: Path
) -> list[dict[str, Any]]:
    """The works for period ``n``, best first: the preset's artists in turn (or
    the cell's own search), works of the poster's shape first, a different
    starting work each period. Works whose image the museum refused are left
    out."""
    bad = set(_read_json(data_dir / "museum" / "refused.json", []))
    queries = [query] if query else MUSEUM.get(style) or MUSEUM["gallery"]
    out: list[dict[str, Any]] = []
    for step in range(len(queries)):
        q = queries[(n + step) % len(queries)]
        rows = [r for r in museum_search(q, data_dir) if r["image_id"] not in bad]
        if not query:
            # a preset names an artist: keep their own works, not works about them
            last = q.split()[-1].lower()
            rows = [r for r in rows if last in str(r["artist"]).lower()] or rows
        if not rows:
            continue
        shaped = [
            r for r in rows if r["w"] and r["h"] and ((r["h"] >= r["w"]) == portrait)
        ]
        rest = [r for r in rows if r not in shaped]
        for pool in (shaped, rest):
            if pool:
                k = _hash(style, q, n) % len(pool)
                out.extend(pool[k:] + pool[:k])
        if len(out) >= 6:
            break
    return out


def museum_refused(row: dict[str, Any], data_dir: Path) -> None:
    path = data_dir / "museum" / "refused.json"
    with _LOCK:
        bad = list(_read_json(path, []))
        if row["image_id"] not in bad:
            bad.append(row["image_id"])
            _write_json(path, bad[-500:])


# ----------------------------------------------------------------------
# AI posters: the Artwork API
# ----------------------------------------------------------------------


# Styles whose picture fills its box: a model that letterboxes one leaves
# bars the poster would show, so they are cut off before it is kept.
FULL_BLEED = {"deco", "riso", "woodblock"}


def trim_bars(raw: bytes, tol: int = 14) -> bytes:
    """Cut flat bars off a picture's edges: strips of one light (white,
    cream) or dark colour, the same all the way in. A gradient sky or a plain
    picture is left alone."""
    try:
        from PIL import Image
    except ImportError:
        return raw
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return raw
    w, h = im.size

    def strip(side: int, x0: int, y0: int, x1: int, y1: int) -> Any:
        return im.crop(
            (
                (x0, y0, x0 + 1, y1),
                (x1 - 1, y0, x1, y1),
                (x0, y0, x1, y0 + 1),
                (x0, y1 - 1, x1, y1),
            )[side]
        )

    def flat(st: Any) -> tuple[float, ...] | None:
        lo, hi = zip(*st.getextrema())
        if max(hi[i] - lo[i] for i in range(3)) > tol:
            return None
        return tuple((lo[i] + hi[i]) / 2 for i in range(3))

    box = [0, 0, w, h]
    for side in range(4):
        x0, y0, x1, y1 = box
        edge = flat(strip(side, x0, y0, x1, y1))
        if edge is None or not (min(edge) > 200 or max(edge) < 40):
            continue
        while True:
            if (x1 - x0) <= w * 0.3 or (y1 - y0) <= h * 0.3:
                return raw  # flat to the middle: a plain picture, not bars
            c = flat(strip(side, x0, y0, x1, y1))
            if c is None or max(abs(c[i] - edge[i]) for i in range(3)) > tol:
                break
            if side == 0:
                x0 += 1
            elif side == 1:
                x1 -= 1
            elif side == 2:
                y0 += 1
            else:
                y1 -= 1
        box = [x0, y0, x1, y1]
    if box == [0, 0, w, h]:
        return raw
    # a bar ends in a soft edge: take a little more
    pad = max(2, round(min(w, h) * 0.006))
    x0, y0, x1, y1 = box
    x0 = x0 + pad if x0 else 0
    y0 = y0 + pad if y0 else 0
    x1 = x1 - pad if x1 < w else w
    y1 = y1 - pad if y1 < h else h
    buf = io.BytesIO()
    im.crop((x0, y0, x1, y1)).save(buf, "JPEG", quality=92)
    return buf.getvalue()


def make(job: Any) -> tuple[bytes, dict[str, Any]]:
    """One painted poster picture, from words alone."""
    p = job.payload
    style = str(p.get("style") or "")
    if style not in PROMPTS:
        raise artwork.ArtworkError(f"no such painted style: {style}")
    subject = str(p.get("subject") or "").strip()
    desc = str(p.get("desc") or "").strip()
    what = (
        f"{subject} ({desc})"
        if desc and desc.lower() not in subject.lower()
        else subject
    )
    aspect = str(p.get("aspect") or "3:4")
    prompt = (
        PROMPTS[style].format(subject=what)
        + f" Composed for a {aspect} canvas, using all of it."
        + NO_WORDS
    )
    model = str(p.get("model") or "nano_banana_t2i")
    model = model if model in MODELS else "nano_banana_t2i"
    raw = job.fal.generate(model, prompt, aspect=aspect)
    if style in FULL_BLEED:
        raw = trim_bars(raw)
    label = _fal.label_of(model) if _fal is not None else model
    return raw, {
        "credit": f"AI picture ({label} on fal.ai)",
        "style": style,
        "subject": subject,
        "prompt": prompt,
    }


ART: Any = (
    artwork.Collection(
        PLUGIN_ID,
        "posters",
        make=make,
        label="Poster",
        title="AI posters",
        facet="style",
        facet_label=lambda s: STYLES.get(s, (s,))[0],
        default_cents=100,
    )
    if artwork is not None
    else None
)


def aspect_for(style: str, w: int, h: int) -> tuple[str, str]:
    """The picture's aspect for a painted style on a w x h poster, snapped to
    the shapes the models take, and the orientation it was made for."""
    orient = "l" if w > h * 1.05 else "p"
    fw, fh = REGION[style][orient]
    ratio = (w * fw) / max(1.0, h * fh)
    name = min(ASPECTS, key=lambda a: abs(a[1] - ratio))[0]
    return name, orient


def _latest(style: str, aspect: str, data_dir: Path, but: str = "") -> str:
    """The newest kept picture of this style and shape, for while the
    period's own is being painted."""
    folder = data_dir / "posters"
    tail = f"--{aspect.replace(':', 'x')}"
    best, when = "", 0.0
    with contextlib.suppress(OSError):
        for f in folder.iterdir():
            if f.suffix.lower() not in (
                ".jpg",
                ".jpeg",
                ".png",
            ) or not f.stem.startswith(f"{style}--"):
                continue
            if not f.stem.endswith(tail) or f.stem == but:
                continue
            m = f.stat().st_mtime
            if m > when:
                best, when = f.stem, m
    return best


# ----------------------------------------------------------------------
# fetch
# ----------------------------------------------------------------------


def _choose_style(options: dict[str, Any], n: int, cell: str) -> str:
    style = str(options.get("style") or "ausstellung")
    if style in STYLES:
        return style
    kinds = MIXES.get(style, MIXES["mix_free"])[1]
    pool = [s for s, (_, k, _) in STYLES.items() if k in kinds]
    # a shuffled order per cell, walked one step a period, so neighbours differ
    order = sorted(pool, key=lambda s: _hash(cell, s))
    return order[n % len(order)]


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    data_dir = Path(ctx.get("data_dir") or HERE / "data")
    w = int(ctx.get("cell_w") or ctx.get("panel_w") or 600)
    h = int(ctx.get("cell_h") or ctx.get("panel_h") or 800)
    portrait = h >= w
    now = datetime.now()
    change = str(options.get("change") or "daily")
    change = change if change in CHANGES else "daily"
    label, n = _bucket(change, now)
    cell = str(ctx.get("cell_id") or "")
    style = _choose_style(options, n, cell)
    name, kind, groups = STYLES[style]
    out: dict[str, Any] = {
        "style": style,
        "kind": kind,
        "period": label,
        "seed": _hash(style, label, options.get("seed_salt") or ""),
        "w": w,
        "h": h,
        "date": {
            "weekday": now.strftime("%A"),
            "day": now.day,
            "month": now.strftime("%B"),
            "year": now.year,
            "doy": now.timetuple().tm_yday,
            "week": now.isocalendar()[1],
            "kanji": WEEKDAY_KANJI[now.weekday()] + "曜",
        },
        "notices": [],
    }
    css = [font_css(groups)]

    if kind == "drawn":
        t, s = DRAWN_TEXT[style]
        out["title"] = _tokens(str(options.get("title") or "").strip() or t, now)
        out["sub"] = _tokens(str(options.get("subtitle") or "").strip() or s, now)

    elif kind == "museum":
        query = str(options.get("museum_query") or "").strip()
        row, raw = None, b""
        for cand in museum_candidates(style, query, n, portrait, data_dir)[:4]:
            raw, refused = museum_image(cand, data_dir, max(w, h))
            if raw:
                row = cand
                break
            if not refused:
                break
            museum_refused(cand, data_dir)
        if row and raw:
            out["pic"] = (
                "data:image/jpeg;base64,"
                + base64.b64encode(_shrink(raw, max(w, h, 600))).decode()
            )
            out["art"] = {
                "artist": row["artist"] or row["artist_display"].split("\n")[0],
                "title": row["title"],
                "date": row["date"],
                "medium": row["medium"],
                "credit": "The Art Institute of Chicago · public domain",
            }
        else:
            out["notices"].append(
                "The museum could not be reached; trying again on the next render."
            )

    else:  # painted
        rows = parse_subjects(str(options.get("subjects") or "")) or parse_subjects(
            "\n".join(SUBJECTS[style])
        )
        pick = rows[(n + _hash(style, cell) % len(rows)) % len(rows)]
        subject = pick["subject"]
        info = wiki(subject, data_dir)
        show_facts = str(options.get("facts", "true")).lower() not in (
            "false",
            "0",
            "off",
            "",
        )
        out["subject"] = words_for(style, pick, data_dir, show_facts)
        aspect, orient = aspect_for(style, w, h)
        out["region"] = REGION[style][orient]
        if style == "woodblock":
            css.append(
                cjk_font_css(out["subject"]["ja"] + out["date"]["kanji"], data_dir)
            )
        if ART is None:
            out["notices"].append(NEEDS_HOST)
        else:
            model = str(options.get("model") or "nano_banana_t2i")
            model = model if model in MODELS else "nano_banana_t2i"
            key = f"{style}--{_slug(subject)}--{'f' if model == 'flux_schnell' else 'n'}{PROMPT_V}--{aspect.replace(':', 'x')}"
            art = ART.open(ctx, settings, subject=f"{cell or 'cell'}")
            got = art.request(
                key,
                {
                    "style": style,
                    "subject": subject,
                    "desc": info.get("desc") or "",
                    "aspect": aspect,
                    "model": model,
                },
                title=f"{subject} ({name})",
            )
            show = key if got.ready else _latest(style, aspect, data_dir, but=key)
            if show:
                out["pic"] = art.url(show, px=min(1600, max(w, h)), levels="colour")
                meta = ART.meta(show, data_dir)
                out["credit"] = str(meta.get("credit") or "AI picture (fal.ai)")
                if show != key:
                    # the words follow the picture on show, not the one still painting
                    held = str(meta.get("subject") or "")
                    if held:
                        row = next(
                            (r for r in rows if r["subject"] == held), {"subject": held}
                        )
                        out["subject"] = {
                            **words_for(style, row, data_dir, show_facts),
                            "painting": subject,
                        }
            art.finish(ctx, facet=style)
            out["notices"].extend(art.notes())
            out["status"] = art.status()
            out.update(art.live())
    out["font_css"] = "".join(css)
    return out

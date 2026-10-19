"""Smoke tests for the poster widget, no network. Run from the repo root with
the Tesserae checkout on the path: PYTHONPATH=../tesserae pytest tests"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load(name: str = "poster_server"):
    spec = importlib.util.spec_from_file_location(name, ROOT / "server.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


S = load()
MANIFEST = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
CLIENT = (ROOT / "client.js").read_text(encoding="utf-8")


def ctx(tmp: Path, w: int = 600, h: int = 800, **kw):
    return {
        "data_dir": str(tmp),
        "cell_w": w,
        "cell_h": h,
        "cell_id": "c1",
        "settled": True,
        **kw,
    }


def jpeg(w: int = 40, h: int = 60, colour=(120, 80, 40)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(url, **kw):
        raise urllib.error.URLError("no network in tests")

    monkeypatch.setattr(S, "_get", refuse)


# ------------------------------------------------------------- the styles


def test_every_style_is_offered_and_drawn():
    choices = {
        c["value"]
        for o in MANIFEST["cell_options"]
        if o["name"] == "style"
        for c in o["choices"]
    }
    assert set(S.STYLES) | set(S.MIXES) == choices
    drawn = re.search(r"const STYLES = \{([^}]*)\}", CLIENT).group(1)
    for style in S.STYLES:
        assert re.search(rf"\b{style}\b", drawn), style


def test_at_least_fourteen_styles_of_three_kinds():
    kinds = {k for _, k, _ in S.STYLES.values()}
    assert kinds == {"drawn", "museum", "painted"}
    assert len(S.STYLES) >= 14


def test_painted_styles_have_prompts_subjects_and_regions():
    painted = {s for s, (_, k, _) in S.STYLES.items() if k == "painted"}
    assert painted == set(S.PROMPTS) == set(S.SUBJECTS) == set(S.REGION)


def test_bundled_fonts_cover_every_group():
    manifest = json.loads((ROOT / "fonts" / "fonts.json").read_text(encoding="utf-8"))
    groups = {f["group"] for f in manifest.values()}
    for _, _, need in S.STYLES.values():
        assert set(need) <= groups
    for file in manifest:
        assert (ROOT / "fonts" / file).stat().st_size > 1000


# ------------------------------------------------------------------ drawn


def test_drawn_poster_has_title_tokens_and_fonts(tmp_path):
    d = S.fetch({"style": "swiss", "title": "{weekday} {year}"}, {}, ctx=ctx(tmp_path))
    assert d["kind"] == "drawn"
    assert "{" not in d["title"] and "{" not in d["sub"]
    assert "Inter Tight" in d["font_css"] and "IBM Plex Mono" in d["font_css"]
    assert isinstance(d["seed"], int)


def test_same_period_same_seed_new_period_new_seed(tmp_path):
    a = S.fetch({"style": "memphis"}, {}, ctx=ctx(tmp_path))
    b = S.fetch({"style": "memphis"}, {}, ctx=ctx(tmp_path))
    assert a["seed"] == b["seed"]
    from datetime import datetime

    l1, n1 = S._bucket("daily", datetime(2026, 10, 20, 9))
    l2, n2 = S._bucket("daily", datetime(2026, 10, 21, 9))
    assert l1 != l2 and n2 == n1 + 1


def test_mix_walks_the_free_styles(tmp_path):
    seen = {S._choose_style({"style": "mix_free"}, n, "c1") for n in range(40)}
    free = {s for s, (_, k, _) in S.STYLES.items() if k in ("drawn", "museum")}
    assert seen == free


# ----------------------------------------------------------------- museum


SEARCH = {
    "data": [
        {
            "id": 1,
            "title": "Refused",
            "artist_title": "Piet Mondrian",
            "image_id": "bad",
            "thumbnail": {"width": 600, "height": 800},
            "date_display": "1921",
        },
        {
            "id": 2,
            "title": "Composition",
            "artist_title": "Piet Mondrian",
            "image_id": "good",
            "thumbnail": {"width": 800, "height": 600},
            "date_display": "1922",
            "medium_display": "Oil on canvas",
        },
    ]
}


def test_museum_skips_a_refused_image_and_remembers_it(tmp_path, monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(url)
        if "api.artic.edu" in url:
            return json.dumps(SEARCH).encode()
        if "/bad/" in url:
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        return jpeg()

    monkeypatch.setattr(S, "_get", fake)
    d = S.fetch({"style": "gallery", "museum_query": "Mondrian"}, {}, ctx=ctx(tmp_path))
    assert d["pic"].startswith("data:image/jpeg;base64,")
    assert d["art"]["title"] == "Composition"
    assert "bad" in json.loads((tmp_path / "museum" / "refused.json").read_text())
    # kept: the next render needs no network for the picture
    monkeypatch.setattr(S, "_get", lambda url, **kw: json.dumps(SEARCH).encode())
    again = S.fetch(
        {"style": "gallery", "museum_query": "Mondrian"}, {}, ctx=ctx(tmp_path)
    )
    assert again["pic"] == d["pic"]


def test_museum_offline_says_so(tmp_path):
    d = S.fetch({"style": "ukiyoe"}, {}, ctx=ctx(tmp_path))
    assert "pic" not in d
    assert d["notices"]


# ---------------------------------------------------------------- painted


def test_subject_lines_and_words():
    rows = S.parse_subjects("Aireys Inlet | Split Point | 1891\n# a note\n\nKyoto")
    assert rows == [
        {"subject": "Aireys Inlet", "label": "Split Point", "year": "1891"},
        {"subject": "Kyoto", "label": "", "year": ""},
    ]
    assert S.blurb("One. Two two. " + "x" * 400) == "One. Two two."
    assert (
        S.common_name(
            "Banksia serrata, commonly known as the old man banksia, is a tree."
        )
        == "old man banksia"
    )


def test_aspect_follows_the_picture_box():
    assert S.aspect_for("woodblock", 600, 800) == ("3:4", "p")
    assert S.aspect_for("woodblock", 800, 480) == ("16:9", "l")
    assert S.aspect_for("travel", 600, 800)[0] == "1:1"


def test_painted_without_a_key_says_what_it_needs(tmp_path, monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    if S.ART is None:
        pytest.skip("needs the Tesserae checkout on the path")
    monkeypatch.setattr(S._fal, "resolve_key", lambda settings=None: "")
    d = S.fetch({"style": "travel", "subjects": "Kyoto"}, {}, ctx=ctx(tmp_path))
    assert d["kind"] == "painted" and "pic" not in d
    assert any("fal.ai key" in n for n in d["notices"])
    assert d["subject"]["name"] == "Kyoto"


def test_painted_on_an_older_host(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "app", None)
    old = load("poster_server_old")
    monkeypatch.setattr(old, "_get", S._get)
    assert old.ART is None
    d = old.fetch({"style": "riso"}, {}, ctx=ctx(tmp_path))
    assert old.NEEDS_HOST in d["notices"]


def test_make_asks_for_no_lettering(tmp_path):
    if S.ART is None:
        pytest.skip("needs the Tesserae checkout on the path")
    asked = {}

    def generate(model, prompt, **kw):
        asked.update(model=model, prompt=prompt, **kw)
        return jpeg(64, 64)

    job = SimpleNamespace(
        payload={
            "style": "linocut",
            "subject": "Barn owl",
            "desc": "Species of bird",
            "aspect": "1:1",
            "model": "flux_schnell",
        },
        fal=SimpleNamespace(generate=generate),
    )
    raw, meta = S.make(job)
    assert raw[:2] == b"\xff\xd8"
    assert (
        "No text, no letters" in asked["prompt"]
        and "Barn owl (Species of bird)" in asked["prompt"]
    )
    assert asked["model"] == "flux_schnell" and asked["aspect"] == "1:1"
    assert meta["subject"] == "Barn owl"


def test_trim_cuts_letterbox_bars_only():
    from PIL import Image

    im = Image.new("RGB", (300, 300), (254, 254, 254))
    for x in range(80, 220):
        for y in range(300):
            im.putpixel((x, y), (20 + (y % 50), 60 + (x % 30), 90))
    sky = Image.new("RGB", (200, 200))
    for y in range(200):
        for x in range(200):
            sky.putpixel((x, y), (y, y, 120))
    sbuf = io.BytesIO()
    sky.save(sbuf, "PNG")
    assert S.trim_bars(sbuf.getvalue()) == sbuf.getvalue()
    buf = io.BytesIO()
    im.save(buf, "PNG")
    out = Image.open(io.BytesIO(S.trim_bars(buf.getvalue())))
    assert out.size[0] < 150 and out.size[1] == 300
    plain = jpeg(100, 100)
    assert (
        S.trim_bars(plain) == plain
        or Image.open(io.BytesIO(S.trim_bars(plain))).size[0] >= 50
    )


def test_words_follow_the_picture_on_show(tmp_path, monkeypatch):
    """While a period's picture is painted the last one shows, with its own words."""
    if S.ART is None:
        pytest.skip("needs the Tesserae checkout on the path")
    monkeypatch.setattr(S._fal, "resolve_key", lambda settings=None: "")
    folder = tmp_path / "posters"
    folder.mkdir()
    (folder / "riso--sailboat--n1--3x4.jpg").write_bytes(jpeg(60, 80))
    (folder / "riso--sailboat--n1--3x4.json").write_text(
        json.dumps({"subject": "Sailboat", "credit": "AI picture"})
    )
    d = S.fetch({"style": "riso", "subjects": "Espresso"}, {}, ctx=ctx(tmp_path))
    assert d["pic"]
    assert d["subject"]["name"] == "Sailboat" and d["subject"]["painting"] == "Espresso"

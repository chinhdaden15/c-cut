"""Bản đồ ĐƯỜNG PHỐ thật cho Text to Video / Voice to Motion — học từ thailinhprod/map-route-video (MIT).

Dữ liệu (miễn phí, ghi nguồn trên video):
  - nền: vector tile OpenFreeMap (OpenMapTiles, © OpenStreetMap contributors) — tự giải mã .pbf, vẽ bằng OpenCV / Pillow
  - toạ độ: Photon (photon.komoot.io, dữ liệu OSM) — nghỉ ≥ 1,5s giữa các lần gọi, có bộ nhớ đệm
  - tuyến + km + phút: OSRM (router.project-osrm.org) — thời gian là ƯỚC TÍNH khi đường thông thoáng, ghi rõ trên video

  python -m thagent.v2m geocode "<tên địa điểm>"                         → lon,lat (thử thêm “, Thủ Đức” / “, TP.HCM” nếu sai)
  python -m thagent.v2m osrm <dự-án> <lon,lat> <lon,lat> <tên>           → assets_web/route_<tên>.geojson (km, phút) — vẽ: s.route(...)
  python -m thagent.v2m streetmap <dự-án> <lon0,lat0,lon1,lat1> [dark|light] [tên]
                                                                         → assets_web/map_<tên>.png + .json (khung toạ độ)
Trong builder: K.street_map("assets_web/map_<tên>.png") (nền, nằm dưới ghim / tuyến / callout), rồi s.look(box), s.route(...),
s.pin(...), s.callout(...) như bản đồ thường. Ảnh vệ tinh: KHÔNG tự ghép tile của dịch vụ khác (điều khoản cấm) — chỉ dùng ảnh
người dùng có quyền.
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np

UA = {"User-Agent": "C-Cut map (video tool)"}
TILEJSON = "https://tiles.openfreemap.org/planet"
CREDIT = "Bản đồ © OpenStreetMap contributors · OpenFreeMap · Tuyến OSRM"

STYLES = {   # BGR được đổi khi vẽ; giữ hex cho dễ đọc
    "dark": dict(land="#0B1220", water="#123447", water_edge="#1E5A73", park="#10251B", building="#162133",
                 minor="#1E2A3B", major="#2C3D55", motor="#3F5675", rail="#24324A", place="#9FB0C6", halo="#0B1220"),
    "light": dict(land="#F3F0EA", water="#A9D3E6", water_edge="#8FC0D8", park="#CFE8C7", building="#E2DDD5",
                  minor="#FFFFFF", major="#FFFFFF", motor="#FFD27A", rail="#C9C2B8", place="#4B5563", halo="#F3F0EA",
                  casing="#CFC8BD"),
}


def _cache_dir() -> Path:
    from ..paths import ROOT
    d = ROOT / "cache" / "osm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url: str, timeout: int = 40) -> bytes:
    last = None
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except Exception as e:      # mạng chập chờn → thử lại
            last = e
            time.sleep(1.5 * (i + 1))
    raise SystemExit(f"LỖI mạng: {url.split('?')[0]} ({last})")


# ------------------------------------------------------------------ giải mã vector tile (protobuf, không cần thư viện)
def _varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s
        if c < 0x80:
            return r, i
        s += 7


def _fields(b):
    i, n = 0, len(b)
    while i < n:
        k, i = _varint(b, i)
        f, w = k >> 3, k & 7
        if w == 0:
            v, i = _varint(b, i)
        elif w == 2:
            ln, i = _varint(b, i)
            v = b[i:i + ln]; i += ln
        elif w == 1:
            v = b[i:i + 8]; i += 8
        elif w == 5:
            v = b[i:i + 4]; i += 4
        else:
            raise ValueError("wire type")
        yield f, w, v


def _packed(b):
    out, i = [], 0
    while i < len(b):
        v, i = _varint(b, i)
        out.append(v)
    return out


def _value(b):
    import struct
    for f, w, v in _fields(b):
        if f == 1:
            return v.decode("utf-8", "ignore")
        if f == 2:
            return struct.unpack("<f", v)[0]
        if f == 3:
            return struct.unpack("<d", v)[0]
        if f in (4, 5):
            return v
        if f == 6:
            return (v >> 1) ^ -(v & 1)
        if f == 7:
            return bool(v)
    return None


def _geom(cmds, gtype):
    """→ danh sách đường / vòng [(x, y), …] theo toạ độ tile (extent)."""
    x = y = 0
    i, parts, cur = 0, [], []
    while i < len(cmds):
        c = cmds[i]; i += 1
        cid, cnt = c & 7, c >> 3
        if cid in (1, 2):
            for _ in range(cnt):
                dx, dy = cmds[i], cmds[i + 1]; i += 2
                x += (dx >> 1) ^ -(dx & 1)
                y += (dy >> 1) ^ -(dy & 1)
                if cid == 1:
                    if cur:
                        parts.append(cur)
                    cur = [(x, y)]
                else:
                    cur.append((x, y))
        elif cid == 7 and cur:
            cur.append(cur[0])
    if cur:
        parts.append(cur)
    return parts


def decode(pbf: bytes) -> dict:
    """{layer: [(gtype, props, parts)]}, extent"""
    out = {}
    for f, w, layer in _fields(pbf):
        if f != 3:
            continue
        name, ext, keys, vals, feats = "", 4096, [], [], []
        for f2, w2, v in _fields(layer):
            if f2 == 1:
                name = v.decode()
            elif f2 == 5:
                ext = v
            elif f2 == 3:
                keys.append(v.decode())
            elif f2 == 4:
                vals.append(_value(v))
            elif f2 == 2:
                feats.append(v)
        rows = []
        for fb in feats:
            tags, gtype, geom = [], 0, []
            for f3, w3, v in _fields(fb):
                if f3 == 2:
                    tags = _packed(v)
                elif f3 == 3:
                    gtype = v
                elif f3 == 4:
                    geom = _packed(v)
            props = {keys[tags[k]]: vals[tags[k + 1]] for k in range(0, len(tags) - 1, 2)
                     if tags[k] < len(keys) and tags[k + 1] < len(vals)}
            rows.append((gtype, props, _geom(geom, gtype)))
        out[name] = (ext, rows)
    return out


# ------------------------------------------------------------------ toạ độ Web Mercator
def _tile_xy(lon, lat, z):
    n = 2 ** z
    r = math.radians(lat)
    return (lon + 180) / 360 * n, (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n


def _tmpl() -> str:
    f = _cache_dir() / "tilejson.json"
    if f.exists() and time.time() - f.stat().st_mtime < 3 * 86400:
        return json.loads(f.read_text())["tiles"][0]
    tj = json.loads(_get(TILEJSON))
    f.write_text(json.dumps(tj))
    return tj["tiles"][0]


def _tile(z, x, y) -> bytes:
    f = _cache_dir() / f"{z}_{x}_{y}.pbf"
    if f.exists():
        return f.read_bytes()
    b = _get(_tmpl().replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)))
    if b[:2] == b"\x1f\x8b":
        import gzip
        b = gzip.decompress(b)
    f.write_bytes(b)
    return b


def _hex(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def render(bbox, style="dark", px_w=2600, z=None) -> tuple[np.ndarray, list[tuple[str, float, float, int]]]:
    """bbox (lon0, lat0, lon1, lat1) → ảnh BGR + nhãn địa danh [(tên, px, py, cấp)]."""
    lon0, lat0, lon1, lat1 = bbox
    span = max(lon1 - lon0, 1e-4)
    z = z or max(10, min(14, int(math.log2(360 / span * px_w / 512 / 1.5))))
    fx0, fy0 = _tile_xy(lon0, lat1, z)
    fx1, fy1 = _tile_xy(lon1, lat0, z)
    sc = px_w / (fx1 - fx0)                         # px / tile
    px_h = int(round((fy1 - fy0) * sc))
    st = {k: (_hex(v) if isinstance(v, str) else v) for k, v in STYLES[style].items()}
    img = np.zeros((px_h, px_w, 3), np.uint8)
    img[:] = st["land"]
    layers = {k: [] for k in ("water", "park", "building", "minor", "major", "motor", "rail")}
    places = []
    tiles = [(x, y) for x in range(int(fx0), int(fx1) + 1) for y in range(int(fy0), int(fy1) + 1)]
    if len(tiles) > 140:
        raise SystemExit(f"khung quá rộng ({len(tiles)} tile ở z{z}) — thu nhỏ khung hoặc dùng bản đồ tỉnh (K.provinces)")
    for tx, ty in tiles:
        dec = decode(_tile(z, tx, ty))

        def conv(ext, pts):
            return np.array([[((tx + px / ext) - fx0) * sc, ((ty + py / ext) - fy0) * sc] for px, py in pts], np.float32)
        for lname, (ext, rows) in dec.items():
            for gtype, pr, parts in rows:
                cls = str(pr.get("class", ""))
                if lname == "water" and gtype == 3:
                    layers["water"].append([conv(ext, p) for p in parts])
                elif lname == "landcover" and cls in ("grass", "wood", "farmland") and gtype == 3 or \
                        lname == "park" and gtype == 3:
                    layers["park"].append([conv(ext, p) for p in parts])
                elif lname == "building" and gtype == 3 and z >= 14:
                    layers["building"].append([conv(ext, p) for p in parts])
                elif lname == "waterway" and gtype == 2:
                    layers["water"].append(("line", [conv(ext, p) for p in parts], 3 if cls == "river" else 1))
                elif lname == "transportation" and gtype == 2:
                    k = "motor" if cls in ("motorway", "trunk") else "major" if cls in ("primary", "secondary", "tertiary") \
                        else "rail" if cls in ("rail", "transit") else "minor" if cls in ("minor", "service", "track") else None
                    if k:
                        layers[k].append([conv(ext, p) for p in parts])
                elif lname == "place" and gtype == 1 and parts:
                    nm = pr.get("name:vi") or pr.get("name") or ""
                    rank = {"city": 0, "town": 1, "suburb": 2, "quarter": 3, "village": 3, "neighbourhood": 4}.get(cls, 5)
                    if nm and rank <= 4 and not nm.lower().startswith(("khu phố", "ấp ", "tổ ")):
                        p = conv(ext, parts[0])[0]
                        if 0 <= p[0] < px_w and 0 <= p[1] < px_h:
                            places.append((nm, float(p[0]), float(p[1]), rank))
    S = px_w / 2600

    def fill(polys, col):
        for rings in polys:
            if isinstance(rings, tuple):
                continue
            cv2.fillPoly(img, [np.round(r).astype(np.int32) for r in rings], col, cv2.LINE_AA)
    fill(layers["park"], st["park"])
    fill(layers["water"], st["water"])
    for it in layers["water"]:
        if isinstance(it, tuple):
            for ln in it[1]:
                cv2.polylines(img, [np.round(ln).astype(np.int32)], False, st["water"], max(2, int(it[2] * 4 * S)), cv2.LINE_AA)
    fill(layers["building"], st["building"])
    for k, w in (("rail", 2), ("minor", 2), ("major", 5), ("motor", 9)):
        for parts in layers[k]:
            pts = [np.round(p).astype(np.int32) for p in parts]
            if st.get("casing") and k != "rail":
                cv2.polylines(img, pts, False, _hex(STYLES[style]["casing"]), max(1, int((w + 3) * S)), cv2.LINE_AA)
            cv2.polylines(img, pts, False, st[k], max(1, int(w * S)), cv2.LINE_AA)
    return img, sorted(places, key=lambda p: p[3])


def _labels(img, places, style, px_w):
    """tên phường / khu (tiếng Việt có dấu) bằng Pillow, có viền nền cho dễ đọc, không đè nhau."""
    from PIL import Image, ImageDraw
    from . import draw as D
    st = STYLES[style]
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    dr = ImageDraw.Draw(pil)
    S = px_w / 2600
    taken = []
    for nm, x, y, rank in places[:40]:
        size = int((44 if rank <= 1 else 36 if rank == 2 else 30) * S * 1.9)
        f = D.font("semi" if rank > 1 else "bold", size)
        t = nm.upper() if rank <= 2 else nm
        bb = dr.textbbox((0, 0), t, font=f)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        box = (x - w / 2 - 8, y - h / 2 - 8, x + w / 2 + 8, y + h / 2 + 8)
        if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in taken):
            continue
        taken.append(box)
        dr.text((x - w / 2, y - h / 2), t, font=f, fill=st["place"], stroke_width=max(2, int(4 * S)), stroke_fill=st["halo"])
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def _portrait(bbox, ratio=2.1):
    """khung dọc 9:16: nới vĩ độ để bản đồ phủ kín khung khi camera đứng ở khung này (không lộ dải đen trên / dưới)."""
    lon0, lat0, lon1, lat1 = bbox
    x0, y0 = _tile_xy(lon0, lat1, 0)
    x1, y1 = _tile_xy(lon1, lat0, 0)
    need = (x1 - x0) * ratio
    if y1 - y0 >= need:
        return bbox
    cy = (y0 + y1) / 2
    lat = lambda y: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y))))
    return [lon0, round(lat(cy + need / 2), 6), lon1, round(lat(cy - need / 2), 6)]


def streetmap(pdir, bbox, style="dark", name="khuvuc", px_w=2600, portrait=True) -> Path:
    pdir = Path(pdir)
    if portrait:
        bbox = _portrait(bbox)
    img, places = render(bbox, style, px_w)
    img = _labels(img, places, style, px_w)
    out = pdir / "assets_web" / f"map_{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    meta = {"bbox": list(bbox), "style": style, "w": img.shape[1], "h": img.shape[0], "credit": CREDIT}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False))
    src = pdir / "assets_web" / "illus_sources.json"
    d = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
    d[out.name] = "https://openfreemap.org — © OpenStreetMap contributors"
    src.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ------------------------------------------------------------------ toạ độ + tuyến
def geocode(q: str, near=(106.70, 10.78)) -> list[dict]:
    f = _cache_dir() / "geocode.json"
    cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if q in cache:
        return cache[q]
    time.sleep(1.5)
    url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": q, "limit": 5, "lon": near[0], "lat": near[1]})
    res = []
    for ft in json.loads(_get(url)).get("features", []):
        p = ft.get("properties", {})
        lon, lat = ft["geometry"]["coordinates"]
        res.append({"name": p.get("name"), "where": ", ".join(str(p[k]) for k in ("street", "district", "city", "state") if p.get(k)),
                    "kind": p.get("osm_value"), "lonlat": [round(lon, 6), round(lat, 6)]})
    cache[q] = res
    f.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def osrm(pdir, a, b, name="tuyen") -> dict:
    url = (f"https://router.project-osrm.org/route/v1/driving/{a[0]},{a[1]};{b[0]},{b[1]}"
           "?overview=full&geometries=geojson")
    r = json.loads(_get(url))
    if r.get("code") != "Ok":
        raise SystemExit(f"OSRM không tìm được tuyến: {r.get('code')}")
    rt = r["routes"][0]
    coords = rt["geometry"]["coordinates"]
    if len(coords) > 300:
        step = len(coords) / 300
        coords = [coords[int(i * step)] for i in range(300)] + [coords[-1]]
    km, mins = rt["distance"] / 1000, rt["duration"] / 60
    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {
        "name": name, "km": round(km, 1), "phut": round(mins), "nguon": "OSRM · © OpenStreetMap contributors",
        "ghi_chu": "thời gian ước tính khi đường thông thoáng"}, "geometry": {"type": "LineString", "coordinates": coords}}]}
    out = Path(pdir) / "assets_web" / f"route_{name}.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gj), encoding="utf-8")
    return {"file": str(out), "km": round(km, 1), "phut": round(mins), "box": _box(coords)}


def _box(coords, pad=0.15):
    xs, ys = [c[0] for c in coords], [c[1] for c in coords]
    dx, dy = (max(xs) - min(xs)) * pad + 0.002, (max(ys) - min(ys)) * pad + 0.002
    return [round(min(xs) - dx, 5), round(min(ys) - dy, 5), round(max(xs) + dx, 5), round(max(ys) + dy, 5)]

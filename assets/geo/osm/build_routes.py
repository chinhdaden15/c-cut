"""Ghép các way OSM (motorways.json, bridge.json, river.json) thành tuyến liền mạch theo chiều đi → routes_south.geojson.
Chỉ dùng hình học OSM; không tự nối các điểm bằng đường thẳng (khoảng hở được ghi lại để kiểm tra)."""
import json, math, sys
from pathlib import Path
D = Path(__file__).parent
m = json.loads((D / "motorways.json").read_text())
b = json.loads((D / "bridge.json").read_text())
rv = json.loads((D / "river.json").read_text())
ways = [e for e in m["elements"] + b["elements"] if e["type"] == "way"]
uniq = {}
for w in ways:
    uniq[w["id"]] = w
ways = list(uniq.values())

def km(a, c):
    return math.hypot((a[0] - c[0]) * 111.32 * math.cos(math.radians(10.5)), (a[1] - c[1]) * 110.57)

def pts(w):
    return [(g["lon"], g["lat"]) for g in w["geometry"]]

import heapq


def graph(names):
    """đồ thị có hướng từ các way OSM (nút trùng toạ độ = nút chung); way khác tên tuyến bị phạt ×6 để bám đúng tuyến."""
    G = {}
    for w in ways:
        hw = w["tags"].get("highway", "")
        p = [(round(x, 7), round(y, 7)) for x, y in pts(w)]
        pen = 1.0 if w["tags"].get("name", "") in names else 6.0
        oneway = w["tags"].get("oneway", "yes" if hw in ("motorway", "motorway_link") else "no")
        pairs = list(zip(p, p[1:]))
        if oneway == "-1":
            pairs = [(c, a_) for a_, c in pairs]
        for a_, c in pairs:
            G.setdefault(a_, []).append((c, km(a_, c) * pen))
            if oneway == "no":
                G.setdefault(c, []).append((a_, km(a_, c) * pen))
    return G


def chain(sel, start, end, names):
    G = graph(names)
    nodes = list(G.keys())
    # nhiều điểm xuất phát/đích quanh mốc (hai chiều xe chạy là 2 way khác nhau) → chọn cặp đi được theo đúng chiều
    srcs = [n for n in nodes if km(n, start) < 0.8] or [min(nodes, key=lambda n: km(n, start))]
    tgts = {n for n in nodes if km(n, end) < 0.8} or {min(nodes, key=lambda n: km(n, end))}
    dist, prev, pq = {}, {}, []
    for n in srcs:
        dist[n] = km(n, start) * 3
        heapq.heappush(pq, (dist[n], n))
    t0 = None
    while pq:
        d, u = heapq.heappop(pq)
        if u in tgts:
            t0 = u
            break
        if d > dist.get(u, 1e18):
            continue
        for v, w_ in G.get(u, []):
            nd = d + w_
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    if t0 is None:   # tuyến OSM dừng trước mốc → dừng ở nút đi tới được gần mốc nhất (≤3 km), ghi khoảng chênh
        t0 = min(dist, key=lambda n: km(n, end))
        if km(t0, end) > 3:
            raise SystemExit(f"không tìm được đường liền mạch {start}→{end}")
    line, u = [t0], t0
    while u in prev:
        u = prev[u]; line.append(u)
    s0 = u
    line.reverse()
    gaps = [round(km(a_, c), 2) for a_, c in zip(line, line[1:]) if km(a_, c) > 1.0]   # đoạn dài >1 km giữa hai nút liền kề
    return line, gaps, round(km(s0, start), 2), round(km(t0, end), 2)


def by_name(*keys):
    return [w for w in ways if any(k == w["tags"].get("name", "") for k in keys)]

ROUTES = [  # id, tên hiển thị, các tên OSM, điểm đầu (theo chiều đi), điểm cuối
    ("mt_ct", "Cao tốc Mỹ Thuận – Cần Thơ", ["Đường cao tốc Mỹ Thuận - Cần Thơ"], (105.8336, 10.0739), (105.9060, 10.2560)),
    ("mt2", "Cầu Mỹ Thuận 2", ["Cầu Mỹ Thuận 2"], (105.9093, 10.2674), (105.9040, 10.2836)),
    ("tl_mt", "Cao tốc Trung Lương – Mỹ Thuận", ["Đường cao tốc Trung Lương - Mỹ Thuận"], (105.9040, 10.2840), (106.3088, 10.4386)),
    ("hcm_tl", "Cao tốc TP.HCM – Trung Lương", ["Đường cao tốc Thành phố Hồ Chí Minh – Trung Lương", "Cao tốc Thành phố Hồ Chí Minh – Trung Lương"],
     (106.3088, 10.4386), (106.5689, 10.6849)),
    ("bl_lt", "Cao tốc Bến Lức – Long Thành", ["Đường cao tốc Bến Lức - Long Thành", "Cầu Bình Khánh", "Cầu Phước Khánh"], (106.547253, 10.6716651), (107.0237, 10.6743)),
    ("hcm_lt_dg", "Cao tốc TP.HCM – Long Thành – Dầu Giây", ["Đường cao tốc Thành phố Hồ Chí Minh – Long Thành – Dầu Giây",
     "Đường cao tốc Thành phố Hồ Chí Minh - Long Thành - Dầu Giây", "Cầu Long Thành"], (106.7581, 10.7944), (107.1654, 10.9338)),
]
feats, report = [], {}
for rid, title, names, s, e in ROUTES:
    line, gaps, ds, de = chain(None, s, e, set(names))
    L = sum(km(line[k], line[k + 1]) for k in range(len(line) - 1))
    report[rid] = {"points": len(line), "km": round(L, 1), "long_segments_km": gaps, "snap_start_km": ds, "snap_end_km": de,
                   "start": line[0], "end": line[-1]}
    feats.append({"type": "Feature", "properties": {"id": rid, "name": title, "source": "OpenStreetMap", "osm_names": names},
                  "geometry": {"type": "LineString", "coordinates": line}})
river = [pts(w) for w in rv["elements"]]
feats.append({"type": "Feature", "properties": {"id": "song_tien", "name": "Sông Tiền", "source": "OpenStreetMap"},
              "geometry": {"type": "MultiLineString", "coordinates": river}})
ts = m.get("osm3s", {}).get("timestamp_osm_base")
(D / "routes_south.geojson").write_text(json.dumps({"type": "FeatureCollection", "osm_timestamp": ts, "features": feats}, ensure_ascii=False))
print(json.dumps(report, ensure_ascii=False, indent=1), ts)

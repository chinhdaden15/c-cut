# Bản đồ: dữ liệu, lớp, mức chi tiết theo zoom

## 1. Dữ liệu (bắt buộc có nguồn, kiểm tra trước khi dựng)

| Lớp | Nguồn đã dùng được | Ghi chú |
|---|---|---|
| Quốc gia thế giới | Natural Earth 1:50m (`assets/geo/ne_50m_admin_0_countries.geojson`, public domain) | 1:50m lược bỏ đảo nhỏ |
| Ranh giới tỉnh VN hiện hành | `assets/geo/vn34/*.geojson` từ github.com/thanglequoc/vietnamese-provinces-database (MIT) | ghi ngày export + nghị quyết; không trộn ranh giới trước/sau sắp xếp |
| Đường, cầu, nút giao, sông | OpenStreetMap qua Overpass (ODbL, ghi “© OpenStreetMap contributors”); gửi kèm User-Agent | lưu snapshot JSON + timestamp |
| Toạ độ đô thị | OSM node `place=city`, hoặc Natural Earth populated places | không dùng tâm tỉnh thay cho địa điểm |

- Tuyến đường: ghép bằng **tìm đường trên đồ thị nút OSM** đúng chiều lưu thông (`assets/geo/osm/build_routes.py`). Không nối các điểm bằng đường thẳng/cong tùy ý. Ghi lại chỗ tuyến OSM dừng trước mốc.
- Nút giao: chỉ đánh dấu `highway=motorway_junction` (tên ở `ref`) nằm trên tuyến. **Hai đường cắt nhau không phải nút giao chuyển tuyến.** Không cho chấm sáng chuyển tuyến khi chưa xác minh nút giao khai thác.
- Trạng thái khai thác (thông xe, đang xây) phải có nguồn báo chí/chính thức có ngày.
- Không dùng AI sinh ảnh để đoán bản đồ.

## 2. Lớp và component

| Loại | Dùng cho |
|---|---|
| `map` | nền quốc gia (Natural Earth), lặp 3 bản ngang để camera đi qua Thái Bình Dương |
| `region` | tô sáng quốc gia (ISO3); tô `VNM` luôn kèm điểm đảo Hoàng Sa, Trường Sa |
| `geo` | ranh giới hành chính từ GeoJSON (`fill_by` theo tên) |
| `geoline` | tuyến thật vẽ dần (`progress`), `head` chấm sáng đầu nét, `dash` nét đứt, `opacity` để giảm nhấn |
| `routelabel` | tên tuyến = **callout** neo vào điểm `at` (0–1) trên chính hình học tuyến |
| `callout` | theo bộ callout tham khảo: dấu neo nhỏ (thoi/chấm) đúng điểm → thân mảnh vẽ ra trước → nhãn ở đầu thân hiện sau. `style: tag` (thẻ tối viền màu nhấn, cho nhãn quan trọng) / `plain` (chữ trơn, nhãn phụ); `sub` = dòng nhỏ trên tên; tự chọn hướng + độ dài thân để **không che tuyến** và không chạm chữ/tiêu đề |
| nhãn `text` với `fixed: true` | giữ cỡ chữ trên màn hình khi zoom; độ lệch con tính bằng px màn hình |
| `geo_xy(lon, lat, copy)` | đổi kinh/vĩ → toạ độ thế giới (dùng chung một phép chiếu Mercator cho mọi lớp) |

## 3. Mức chi tiết (LOD) theo zoom camera

Mọi nhãn bản đồ có `lod: [zmin, zmax]` (zoom camera); renderer làm mờ dần ±18% quanh ngưỡng (thang log) → không nhấp nháy. Ẩn nhãn **không** thay đổi dữ liệu địa lý (vùng/đảo vẫn vẽ).

Với MAP_W = 4000 (Việt Nam ~ zoom 2–5 khi xem cả nước, khu vực tỉnh ~ zoom 40–300):

| Mức | Zoom tham khảo | Hiện |
|---|---|---|
| A. Cận địa phương | ≥ 60 | tuyến, nút giao, địa danh đang được nói tới |
| B. Quốc gia | 2 – 60 | tên quốc gia, tỉnh liên quan, nhãn Hoàng Sa – Trường Sa (khi thể hiện Việt Nam) |
| C. Châu lục | 0,6 – 2 | chỉ quốc gia/vùng đang liên quan đến lời đọc |
| D. Thế giới | < 0,6 | chỉ chủ thể chính của câu chuyện |

- Hoàng Sa – Trường Sa: khi thể hiện Việt Nam ở cấp quốc gia (mức B), vẽ điểm đảo cùng màu lãnh thổ + nhãn chữ trơn “QĐ. Hoàng Sa / (Việt Nam)”, “QĐ. Trường Sa / (Việt Nam)”. Zoom ra châu lục/thế giới: **cả nhãn và điểm đảo mờ dần rồi ẩn** (`lod: [1.7, null]` cho nhãn, `islands_lod` mặc định [1.6, null] cho điểm đảo) — không phóng chấm đảo quá cỡ ở tỷ lệ nhỏ. Không đổi toạ độ/dữ liệu.
- Nhãn quan trọng ưu tiên; nhãn phụ ẩn trước. Thử vị trí thay thế, dùng đường dẫn nhãn khi gần điểm khác.

## 3a. Quy tắc bắt buộc

1. **Tên quốc gia/lãnh thổ/tỉnh phải nằm TRỌN trong chính lãnh thổ đó**, không lấn sang lãnh thổ khác. Khai báo `inside: {"iso": "VNM"}` (Natural Earth) hoặc `inside: {"src": "<geojson>", "name": "<tên>"}`. Renderer dò vị trí trong lãnh thổ gần điểm mong muốn, thử xếp 2 dòng rồi thu nhỏ tới cỡ đọc được (`min_size`, mặc định 22px); không vừa → ẩn nhãn (không bao giờ tràn ra ngoài). Tên lãnh thổ giữ màu chữ trắng (bóng mềm) như mẫu đã duyệt — không đổi sang chữ tối kể cả khi nằm trên vùng tô.
   Vị trí nhãn/callout được **tính một lần rồi khoá** (gắn chặt vào bản đồ như mẫu Người Quan Sát): renderer xem trước nhiều thời điểm trong khoảng hiển thị, chọn vị trí trống ở nhiều thời điểm nhất rồi giữ nguyên cho cả video; zoom ra không còn vừa thì mờ đi, không dời chỗ. Ngoại lệ: nhãn quần đảo đặt cạnh cụm đảo (chữ không thể nằm trong đảo nhỏ).
2. **Chữ, shape, callout, pin trên bản đồ KHÔNG phóng to/thu nhỏ theo zoom** — chỉ bám đúng vị trí. Timeline có bản đồ: renderer tự đặt `fixed` cho text/icon/circle/rect/callout/list/counter trong không gian bản đồ (tắt bằng `theme.map_fixed: false`).

## 3b. Nhãn và callout — “tinh tế, đơn giản”

- **Callout chỉ dùng cho đối tượng nhỏ cần nổi bật**: tên đường/tuyến, dự án, cây cầu, nút giao, công trình, điểm cụ thể. **Không** dùng callout cho quốc gia, lãnh thổ, vùng, tỉnh, hải đảo/quần đảo — những nhãn đó luôn là chữ.
- Nhãn địa danh/quốc gia/quần đảo: **chữ trơn** (trắng hoặc màu nhấn, bóng mềm), KHÔNG hộp, KHÔNG callout. Ví dụ đạt: “VIỆT NAM” trắng đậm phía trên lãnh thổ; “QĐ. Hoàng Sa / (Việt Nam)” vàng, đặt bên cạnh cụm đảo. Chỉ thêm `lod` để ẩn khi zoom ra.
- Chỉ đối tượng **quan trọng của câu đang đọc** mới được làm nổi (callout `tag`). Đối tượng phụ dùng callout `plain` nhỏ, hoặc không ghi nhãn.
- Tuyệt đối không để nhãn che đoạn đường đang nói: đặt callout ra xa, thân mảnh chỉ về điểm neo trên tuyến. Renderer kiểm tra vùng nét tuyến đã vẽ (`route_mask`) và vùng tiêu đề màn hình trước khi chọn vị trí.
- Không gom nhiều thẻ thành một cụm: một cảnh tối đa 2 callout `tag` cùng lúc; phần còn lại `plain` hoặc ẩn.
- Chỉ sửa những gì được yêu cầu: khi người dùng góp ý một cảnh/một loại nhãn, không đổi kiểu các nhãn khác.

## 4. Nhấn và giảm nhấn tuyến

- Tuyến đang giải thích: màu nhấn, nét 6–8px, glow tiết chế (≤ 0,4), có thể có chấm sáng đầu nét (ghi “minh họa hướng di chuyển, không phải dữ liệu lưu lượng”).
- Tuyến đã giới thiệu: `animate opacity → 0,45` khi tuyến mới xuất hiện.
- Hai tuyến cùng khu vực phải khác nhau ở ít nhất **hai** thuộc tính: màu + nét (liền/đứt) hoặc màu + độ dày.
- Mỗi tuyến có đúng một `routelabel` (callout) gắn vào chính nó; không đặt tên tuyến bằng chữ tự do trên bản đồ. Tuyến giảm nhấn: mờ thân/neo, chữ callout vẫn ≥ 85% độ đọc.
- Chú giải cuối (legend): mẫu nét + tên, cỡ ≥ 30px, đặt trong `plate`.

## 5. Tô lãnh thổ, màu, dẫn mắt (v1.2.2 — bắt buộc)

**Tô dần, không bật một mảng màu ngay**: `s.region(iso, t)` → viền vẽ dần/sáng lên (nhận diện hình) → màu lan từ tâm ra bằng mask đúng ranh giới
(không tràn sang nước khác/ra biển, đủ mọi polygon và đảo, hết animation thì đầy đủ) → giữ rõ để đọc nhãn. Thời lượng tô tự theo cảnh (0,7–1,3s), khởi đầu đúng lúc voice nhắc tên.

**Màu**: mỗi quốc gia cần phân biệt một màu riêng (`K.color(iso)`, gán theo thứ tự xuất hiện → nhất quán cả video và cả hai tỷ lệ). Nước liền kề (Trung Quốc – Ấn Độ) luôn khác màu;
chỉ dùng chung màu khi chủ đích gom nhóm và đã nói rõ. Màu tô đậm vừa để chữ trắng đọc rõ; nước nền giảm bão hoà/tương phản.

**Tên quốc gia/lãnh thổ**: chữ trắng, viền tối mảnh (`s.place`, nằm TRONG lãnh thổ bằng `inside`), không dùng chữ vàng/ngà trên nền vàng. Nhãn chi tiết ẩn khi zoom ra (`lod`), không giữ mọi tên trên bản đồ thế giới.

**Dẫn mắt**: khi lời chuyển chú ý tới một nơi → tô vùng / viền nhấn / `s.halo(lonlat, t)` / marker, và giảm nhấn phần còn lại (`dim=` hoặc `s.focus(region, t)`).
Camera và hiệu ứng nhấn cùng hướng tới một chủ thể. Tô lãnh thổ = ranh giới thật; halo = tín hiệu chú ý (vòng gợn), không được giống ranh giới.
Không thêm tuyến/mũi tên dòng chảy khi nội dung không có quan hệ đó.

**Ý không gắn vị trí**: chuyển sang cảnh đồ họa riêng — `s.backdrop()` cho một cảnh, `K.map_until(t)` khi phần còn lại của video không cần bản đồ. Không giữ bản đồ làm nền vô nghĩa.
Cảnh kết: diễn tiến tổng kết (các ý hiện lần lượt, đổi trạng thái/gom lại) rồi giữ một bố cục hoàn chỉnh đủ đọc.

**Một thế giới trong khung**: renderer chỉ vẽ một bản lặp khi cả vòng thế giới hẹp hơn khung, và `Frame.fit_geo` không lùi xa hơn mức một vòng thế giới phủ kín bề ngang
→ không bao giờ thấy một quốc gia hai lần (lỗi cũ ở bản ngang 16:9 lúc zoom ra thế giới).

**Kiểm riêng hai tỷ lệ**: camera và bố cục tính riêng cho 9:16 và 16:9 (Frame). Xem ảnh tĩnh tại: bắt đầu/kết thúc tô lãnh thổ, lúc camera xoay/chuyển vùng, lúc zoom ra thế giới, các cảnh cuối;
soát nhãn trùng, mất tương phản, xoay theo nền, quốc gia lặp.

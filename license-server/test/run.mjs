// Kiểm máy chủ bản quyền chạy cục bộ (npm run dev). BASE, ADMIN_TOKEN, SEPAY_API_KEY, PUBLIC_KEY_HEX lấy từ biến môi trường.
import { createPublicKey, verify } from "node:crypto";
const B = process.env.BASE || "http://127.0.0.1:8787", A = process.env.ADMIN_TOKEN, S = process.env.SEPAY_API_KEY;
const PUB = createPublicKey({ key: Buffer.concat([Buffer.from("302a300506032b6570032100", "hex"), Buffer.from(process.env.PUBLIC_KEY_HEX, "hex")]), format: "der", type: "spki" });
let pass = 0, fail = 0;
const t = (name, cond, extra = "") => { cond ? pass++ : fail++; console.log(`${cond ? "PASS" : "FAIL"}  ${name}${cond ? "" : "  " + JSON.stringify(extra)}`); };
const post = (p, b, h = {}) => fetch(B + p, { method: "POST", headers: { "content-type": "application/json", ...h }, body: JSON.stringify(b) }).then(async (r) => ({ http: r.status, ...(await r.json()) }));
const get = (p, h = {}) => fetch(B + p, { headers: h }).then(async (r) => ({ http: r.status, ...(await r.json()) }));
const adm = (p, b) => b ? post("/admin/api/" + p, b, { authorization: "Bearer " + A }) : get("/admin/api/" + p, { authorization: "Bearer " + A });
const dec = (tok) => { const [b, s] = tok.split("."); const body = Buffer.from(b, "base64url");
  return { ok: verify(null, body, PUB, Buffer.from(s, "base64url")), p: JSON.parse(body) }; };
const D1 = "a".repeat(64), D2 = "b".repeat(64), run = Date.now().toString(36);

t("admin sai mật khẩu bị chặn", (await get("/admin/api/overview", { authorization: "Bearer sai" })).http === 401);
t("chưa đặt giá → chưa mở bán", (await get("/v1/products")).products.length === 0);
await adm("settings", { bank: "VCB", account: "0123456789", account_name: "TEST", trial_limit: 2 });
for (const [id, name, price, sort] of [["review-editor", "Skill Review", 300000, 1], ["voice-to-motion", "Skill Voice to Motion", 250000, 2], ["all", "Combo toàn bộ skill", 450000, 9]])
  await adm("product", { id, name, price, sort });
t("đặt giá → 3 sản phẩm mở bán", (await get("/v1/products")).products.length === 3);

// dùng thử
const p = (n) => `${run}-p${n}`;
let r = await post("/v1/trial", { device: D1, skill: "review-editor", project: p(1), os: "mac", app: "1.7.0" });
t("lượt thử 1 + giấy phép thử có chữ ký đúng dự án", r.ok && r.used === 1 && dec(r.grant).ok && dec(r.grant).p.t === "trial" && dec(r.grant).p.project === p(1), r);
r = await post("/v1/trial", { device: D1, skill: "review-editor", project: p(1) });
t("chạy lại cùng dự án không trừ thêm", r.ok && r.used === 1 && r.already, r);
t("lượt thử 2", (await post("/v1/trial", { device: D1, skill: "review-editor", project: p(2) })).used === 2);
r = await post("/v1/trial", { device: D1, skill: "review-editor", project: p(3) });
t("lượt 3 bị chặn (hết thử), không có giấy phép", !r.ok && r.used === 2 && !r.grant, r);
t("skill khác có lượt thử riêng", (await post("/v1/trial", { device: D1, skill: "voice-to-motion", project: p(4) })).ok);
t("máy khác có lượt thử riêng", (await post("/v1/trial", { device: D2, skill: "review-editor", project: p(5) })).ok);
t("tham số sai bị từ chối", (await post("/v1/trial", { device: "xyz", skill: "review-editor", project: "p" })).http === 400);

// mã tay (fanpage) + kích hoạt 1 máy
const k1 = (await adm("license", { product: "review-editor", note: "khách fanpage" })).key;
t("tạo mã tay", /^CC-[A-Z2-9]{5}-[A-Z2-9]{5}-[A-Z2-9]{5}$/.test(k1), k1);
r = await post("/v1/activate", { key: k1.toLowerCase(), device: D1 });
const tk = r.ok && dec(r.token);
t("kích hoạt + mã ký đúng, gắn đúng máy", r.ok && tk.ok && tk.p.t === "lic" && tk.p.device === D1 && tk.p.product === "review-editor", r);
t("mã tạo tay mặc định loại Bán", (await adm("overview")).licenses.find((l) => l.key === k1).kind === "sale");
const g = await adm("license", { product: "all", note: "tặng anh A", kind: "gift" });
t("tạo mã Tặng", g.kind === "gift" && (await adm("overview")).licenses.find((l) => l.key === g.key).kind === "gift");
t("kích hoạt lại cùng máy vẫn được", (await post("/v1/activate", { key: k1, device: D1 })).ok);
r = await post("/v1/activate", { key: k1, device: D2 });
t("máy khác dùng cùng mã bị chặn", !r.ok && r.http === 409, r);
t("mã sai bị chặn", (await post("/v1/activate", { key: "CC-AAAAA-AAAAA-AAAAA", device: D1 })).http === 404);
t("sửa nội dung mã → chữ ký sai", !dec(`${Buffer.from(JSON.stringify({ ...tk.p, product: "all" })).toString("base64url")}.${(await post("/v1/activate", { key: k1, device: D1 })).token.split(".")[1]}`).ok);
r = await post("/v1/status", { device: D1 });
t("status trả mã đã mua + lượt thử (cài lại app khôi phục được)", r.tokens.length === 1 && r.trials["review-editor"] === 2 && r.trial_limit === 2, r);

// thu hồi / gỡ máy
await adm("license/revoke", { key: k1 });
r = await post("/v1/status", { device: D1, nonce: "n1" });
t("thu hồi → status không còn mã, báo thu hồi", r.tokens.length === 0 && r.revoked.includes(k1), r);
let st = dec(r.state);
t("trạng thái đã ký: đúng máy + nonce, không còn mã bị thu hồi", st.ok && st.p.t === "st" && st.p.device === D1 && st.p.nonce === "n1" && !st.p.keys.includes(k1), st);
await adm("license/restore", { key: k1 });
t("khôi phục → trạng thái ký có lại mã", dec((await post("/v1/status", { device: D1, nonce: "n2" })).state).p.keys.includes(k1));
await adm("license/unbind", { key: k1 });
st = dec((await post("/v1/status", { device: D1, nonce: "n3" })).state);
t("gỡ khỏi máy → trạng thái ký của máy cũ không còn mã", st.ok && !st.p.keys.includes(k1), st);
t("gỡ khỏi máy → máy mới kích hoạt được", (await post("/v1/activate", { key: k1, device: D2 })).ok);

// khoá máy
await adm("device/block", { id: D2, blocked: true });
t("máy bị khoá: không dùng thử, không kích hoạt", (await post("/v1/trial", { device: D2, skill: "voice-to-motion", project: p(6) })).http === 403
  && (await post("/v1/status", { device: D2 })).blocked);
await adm("device/block", { id: D2, blocked: false });
await adm("device/reset-trial", { id: D1, skill: "review-editor" });
t("cấp lại lượt thử", (await post("/v1/trial", { device: D1, skill: "review-editor", project: p(7) })).used === 1);

// mua trong app: đơn có mã máy → tiền về → tự kích hoạt
let o = await post("/v1/order", { product: "all", contact: "test@example.com", device: D1 });
t("tạo đơn: QR VietQR đúng số tiền + nội dung", o.ok && o.amount === 450000 && o.qr.includes("VCB-0123456789") && o.qr.includes(o.code), o);
t("đơn chờ tiền", (await get("/v1/order/" + o.id)).status === "pending");
t("webhook sai khoá bị chặn", (await post("/v1/webhook/sepay", { id: 1 }, { authorization: "Apikey sai" })).http === 401);
const hook = (id, amount, content) => post("/v1/webhook/sepay", { id, gateway: "Vietcombank", transferType: "in", transferAmount: amount,
  content, accountNumber: "0123456789", code: null, referenceCode: "FT" + id }, { authorization: "Apikey " + S });
await hook(`${run}1`, 100000, `CHUYEN TIEN ${o.code}`);
t("chuyển thiếu tiền → chưa cấp mã", (await get("/v1/order/" + o.id)).status === "pending");
await hook(`${run}2`, 450000, `MBVCB.123.${o.code.toLowerCase()}.CT tu 0123`);
r = await get("/v1/order/" + o.id);
t("tiền về đủ → cấp mã + tự kích hoạt cho máy mua (combo)", r.status === "paid" && r.key && dec(r.token).p.product === "all" && dec(r.token).p.device === D1, r);
await hook(`${run}2`, 450000, `${o.code}`);
t("mã mua qua QR có loại order", (await adm("overview")).licenses.find((l) => l.order_id === o.id).kind === "order");
t("webhook gửi lại không cấp mã thứ 2", (await adm("overview")).licenses.filter((l) => l.order_id === o.id).length === 1);

// mua trên web (không có mã máy) → khách tự nhập mã
o = await post("/v1/order", { product: "voice-to-motion", contact: "0900000000" });
await hook(`${run}3`, 250000, `${o.code} chuyen khoan`);
r = await get("/v1/order/" + o.id);
t("đơn web: có mã, chưa gắn máy (không kèm token)", r.status === "paid" && r.key && !r.token, r);
t("khách nhập mã vào app → kích hoạt", (await post("/v1/activate", { key: r.key, device: D2 })).ok);

// ghi sai nội dung CK → chủ app xác nhận tay
o = await post("/v1/order", { product: "review-editor" });
await hook(`${run}4`, 300000, "chuyen khoan mua skill");
t("CK sai nội dung → đơn vẫn chờ, giao dịch được ghi lại", (await get("/v1/order/" + o.id)).status === "pending"
  && (await adm("overview")).payments.some((x) => x.id === `sepay:${run}4` && !x.order_id));
r = await adm("order/paid", { id: o.id });
t("xác nhận tay → cấp mã", r.ok && (await get("/v1/order/" + o.id)).key === r.key);
t("trang mua + trang quản lý mở được", (await fetch(B + "/mua")).ok && (await fetch(B + "/admin")).ok);

console.log(`\n${pass}/${pass + fail} PASS`);
process.exit(fail ? 1 : 0);

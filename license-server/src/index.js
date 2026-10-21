// Máy chủ bản quyền skill C-Cut — Cloudflare Worker + D1.
// App: /v1/status, /v1/trial, /v1/activate. Mua (trong nước, chuyển khoản QR): /v1/products, /v1/order, /mua.
// Ngân hàng báo tiền về (SePay): /v1/webhook/sepay. Quản lý: /admin (ADMIN_TOKEN).
// Bí mật: ADMIN_TOKEN, SEPAY_API_KEY, SIGNING_KEY (Ed25519 PKCS8 base64 — app giữ khoá công khai để kiểm mã offline).
import { BUY_HTML, ADMIN_HTML, GUIDE_HTML } from "./pages.js";

const now = () => Math.floor(Date.now() / 1000);
const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "content-type, authorization",
  "access-control-allow-methods": "GET, POST, OPTIONS" };
const json = (d, status = 200) => new Response(JSON.stringify(d), { status, headers: { "content-type": "application/json; charset=utf-8", ...CORS } });
const err = (msg, status = 400, extra = {}) => json({ ok: false, error: msg, ...extra }, status);
const html = (s) => new Response(s, { headers: { "content-type": "text/html; charset=utf-8" } });
const DEV_RE = /^[a-f0-9]{32,64}$/;
const ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";       // bỏ O/0/I/1 dễ nhầm

function rand(n) {
  const b = crypto.getRandomValues(new Uint8Array(n));
  return Array.from(b, (x) => ALPHA[x % ALPHA.length]).join("");
}
const newKey = () => `CC-${rand(5)}-${rand(5)}-${rand(5)}`;
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function setting(env, k, dflt = null) {
  const r = await env.DB.prepare("SELECT v FROM settings WHERE k = ?").bind(k).first();
  return r ? r.v : dflt;
}

let _signKey;
async function sign(env, payload) {
  if (!_signKey) {
    const der = Uint8Array.from(atob(env.SIGNING_KEY), (c) => c.charCodeAt(0));
    _signKey = await crypto.subtle.importKey("pkcs8", der, { name: "Ed25519" }, false, ["sign"]);
  }
  const body = new TextEncoder().encode(JSON.stringify(payload));
  const sig = await crypto.subtle.sign({ name: "Ed25519" }, _signKey, body);
  return `${b64u(body)}.${b64u(sig)}`;
}
const token = (env, lic) => sign(env, { v: 1, t: "lic", key: lic.key, product: lic.product, device: lic.device, iat: lic.activated || now() });

async function seen(env, device, info = {}) {
  const t = now();
  await env.DB.prepare(`INSERT INTO devices (id, os, app, first_seen, last_seen) VALUES (?1, ?2, ?3, ?4, ?4)
      ON CONFLICT(id) DO UPDATE SET last_seen = ?4, os = COALESCE(?2, os), app = COALESCE(?3, app)`)
    .bind(device, info.os || null, info.app || null, t).run();
  return env.DB.prepare("SELECT * FROM devices WHERE id = ?").bind(device).first();
}

async function deviceTokens(env, device) {
  const { results } = await env.DB.prepare("SELECT * FROM licenses WHERE device = ? AND revoked = 0").bind(device).all();
  return Promise.all(results.map((l) => token(env, l)));
}

// ---------------- app ----------------
async function status(env, body) {
  if (!DEV_RE.test(body.device || "")) return err("mã thiết bị không hợp lệ");
  const dev = await seen(env, body.device, body);
  const { results } = await env.DB.prepare("SELECT skill, COUNT(*) n FROM trial_uses WHERE device = ? GROUP BY skill").bind(body.device).all();
  const revoked = (await env.DB.prepare("SELECT key FROM licenses WHERE device = ? AND revoked = 1").bind(body.device).all()).results.map((r) => r.key);
  const keys = dev.blocked ? [] : (await env.DB.prepare("SELECT key FROM licenses WHERE device = ? AND revoked = 0").bind(body.device).all()).results.map((r) => r.key);
  // danh sách mã CÒN HIỆU LỰC của máy, ký kèm nonce app gửi → app bỏ mã đã thu hồi / gỡ khỏi máy, không giả hay phát lại được phản hồi cũ
  const state = await sign(env, { v: 1, t: "st", device: body.device, nonce: String(body.nonce || "").slice(0, 64), keys, blocked: !!dev.blocked, iat: now() });
  return json({ ok: true, blocked: !!dev.blocked, trial_limit: Number(await setting(env, "trial_limit", "2")),
    trials: Object.fromEntries(results.map((r) => [r.skill, r.n])), tokens: dev.blocked ? [] : await deviceTokens(env, body.device), revoked, state });
}

async function trial(env, body) {
  const { device, skill, project } = body;
  if (!DEV_RE.test(device || "") || !/^[\w-]{1,64}$/.test(skill || "") || !/^[\w.-]{1,128}$/.test(project || "")) return err("thiếu/sai tham số");
  const dev = await seen(env, device, body);
  if (dev.blocked) return err("máy này đã bị khoá", 403, { blocked: true });
  const limit = Number(await setting(env, "trial_limit", "2"));
  const had = await env.DB.prepare("SELECT 1 FROM trial_uses WHERE device = ? AND skill = ? AND project = ?").bind(device, skill, project).first();
  const used = (await env.DB.prepare("SELECT COUNT(*) n FROM trial_uses WHERE device = ? AND skill = ?").bind(device, skill).first()).n;
  const grant = () => sign(env, { v: 1, t: "trial", device, skill, project, iat: now() });   // app kiểm chữ ký → không giả được lượt thử
  if (had) return json({ ok: true, used, limit, already: true, grant: await grant() });
  if (used >= limit) return json({ ok: false, used, limit, error: "hết lượt dùng thử" });
  await env.DB.prepare("INSERT INTO trial_uses (device, skill, project, at) VALUES (?, ?, ?, ?)").bind(device, skill, project, now()).run();
  return json({ ok: true, used: used + 1, limit, grant: await grant() });
}

async function activate(env, body) {
  const key = String(body.key || "").trim().toUpperCase();
  if (!DEV_RE.test(body.device || "")) return err("mã thiết bị không hợp lệ");
  const dev = await seen(env, body.device, body);
  if (dev.blocked) return err("máy này đã bị khoá", 403);
  const lic = await env.DB.prepare("SELECT * FROM licenses WHERE key = ?").bind(key).first();
  if (!lic) return err("mã bản quyền không đúng", 404);
  if (lic.revoked) return err("mã bản quyền đã bị thu hồi", 403);
  if (lic.device && lic.device !== body.device) return err("mã này đã kích hoạt trên máy khác — mỗi mã dùng cho 1 máy", 409);
  if (!lic.device) {
    lic.device = body.device; lic.activated = now();
    await env.DB.prepare("UPDATE licenses SET device = ?, activated = ? WHERE key = ? AND device IS NULL").bind(lic.device, lic.activated, key).run();
  }
  const name = (await env.DB.prepare("SELECT name FROM products WHERE id = ?").bind(lic.product).first())?.name || lic.product;
  return json({ ok: true, product: lic.product, name, token: await token(env, lic) });
}

// ---------------- mua ----------------
async function products(env) {
  const { results } = await env.DB.prepare("SELECT id, name, price FROM products WHERE active = 1 AND price > 0 ORDER BY sort").all();
  return json({ ok: true, products: results });
}

async function bankInfo(env) {
  return { bank: await setting(env, "bank"), account: await setting(env, "account"), account_name: await setting(env, "account_name") };
}
function qrUrl(b, amount, code) {
  return `https://img.vietqr.io/image/${encodeURIComponent(b.bank)}-${encodeURIComponent(b.account)}-compact2.png?amount=${amount}`
    + `&addInfo=${encodeURIComponent(code)}&accountName=${encodeURIComponent(b.account_name || "")}`;
}

async function createOrder(env, body) {
  const p = await env.DB.prepare("SELECT * FROM products WHERE id = ? AND active = 1 AND price > 0").bind(body.product || "").first();
  if (!p) return err("sản phẩm chưa mở bán");
  const b = await bankInfo(env);
  if (!b.bank || !b.account) return err("chưa cấu hình tài khoản nhận tiền", 503);
  const device = DEV_RE.test(body.device || "") ? body.device : null;
  const id = crypto.randomUUID(), code = `CCUT${rand(6)}`;
  await env.DB.prepare("INSERT INTO orders (id, code, product, amount, contact, device, created) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .bind(id, code, p.id, p.price, String(body.contact || "").slice(0, 120) || null, device, now()).run();
  return json({ ok: true, id, code, amount: p.price, product: p.id, name: p.name, ...b, qr: qrUrl(b, p.price, code) });
}

async function getOrder(env, id) {
  const o = await env.DB.prepare("SELECT * FROM orders WHERE id = ?").bind(id).first();
  if (!o) return err("không có đơn này", 404);
  const out = { ok: true, status: o.status, code: o.code, amount: o.amount, product: o.product };
  if (o.status === "paid" && o.license) {
    const lic = await env.DB.prepare("SELECT * FROM licenses WHERE key = ?").bind(o.license).first();
    out.key = lic.key;
    if (lic.device && lic.device === o.device && !lic.revoked) out.token = await token(env, lic);
  }
  return json(out);
}

async function markPaid(env, o, paymentId) {
  const key = newKey(), t = now();
  // đơn tạo từ app (có mã máy) → kích hoạt luôn cho máy đó; đơn từ web → khách nhập mã vào app
  await env.DB.batch([
    env.DB.prepare("INSERT INTO licenses (key, product, device, created, activated, order_id, kind) VALUES (?, ?, ?, ?, ?, ?, 'order')")
      .bind(key, o.product, o.device, t, o.device ? t : null, o.id),
    env.DB.prepare("UPDATE orders SET status = 'paid', paid = ?, license = ?, payment = ? WHERE id = ? AND status = 'pending'")
      .bind(t, key, paymentId, o.id),
  ]);
  return key;
}

async function sepay(env, req) {
  const auth = req.headers.get("authorization") || "";
  if (!env.SEPAY_API_KEY || auth !== `Apikey ${env.SEPAY_API_KEY}`) return err("unauthorized", 401);
  const d = await req.json();
  if (d.transferType && d.transferType !== "in") return json({ success: true });
  const pid = `sepay:${d.id}`;
  if (await env.DB.prepare("SELECT 1 FROM payments WHERE id = ?").bind(pid).first()) return json({ success: true });  // gửi lại → bỏ qua
  const text = `${d.code || ""} ${d.content || ""} ${d.description || ""}`.toUpperCase();
  const m = text.match(/CCUT[A-Z0-9]{6}/);
  const o = m && await env.DB.prepare("SELECT * FROM orders WHERE code = ? AND status = 'pending'").bind(m[0]).first();
  const amount = Number(d.transferAmount || 0);
  await env.DB.prepare("INSERT INTO payments (id, amount, content, at, order_id, raw) VALUES (?, ?, ?, ?, ?, ?)")
    .bind(pid, amount, String(d.content || "").slice(0, 300), now(), o && amount >= o.amount ? o.id : null, JSON.stringify(d).slice(0, 2000)).run();
  if (o && amount >= o.amount) await markPaid(env, o, pid);
  return json({ success: true });
}

// ---------------- quản lý ----------------
async function admin(env, req, path) {
  if (!env.ADMIN_TOKEN || req.headers.get("authorization") !== `Bearer ${env.ADMIN_TOKEN}`) return err("sai mật khẩu quản lý", 401);
  const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
  const all = async (sql, ...a) => (await env.DB.prepare(sql).bind(...a).all()).results;
  if (path === "overview") {
    return json({ ok: true,
      products: await all("SELECT * FROM products ORDER BY sort"),
      settings: Object.fromEntries((await all("SELECT k, v FROM settings")).map((r) => [r.k, r.v])),
      devices: await all(`SELECT d.*, (SELECT GROUP_CONCAT(skill || ':' || n) FROM (SELECT skill, COUNT(*) n FROM trial_uses t WHERE t.device = d.id GROUP BY skill)) trials
                          FROM devices d ORDER BY last_seen DESC LIMIT 500`),
      licenses: await all("SELECT * FROM licenses ORDER BY created DESC LIMIT 500"),
      orders: await all("SELECT * FROM orders ORDER BY created DESC LIMIT 300"),
      payments: await all("SELECT id, amount, content, at, order_id FROM payments ORDER BY at DESC LIMIT 100") });
  }
  if (path === "license") {           // tạo mã tay: bán (fanpage) hoặc tặng
    if (!await env.DB.prepare("SELECT 1 FROM products WHERE id = ?").bind(body.product || "").first()) return err("sai sản phẩm");
    const key = newKey(), kind = body.kind === "gift" ? "gift" : "sale";
    await env.DB.prepare("INSERT INTO licenses (key, product, created, note, kind) VALUES (?, ?, ?, ?, ?)").bind(key, body.product, now(), body.note || null, kind).run();
    return json({ ok: true, key, kind });
  }
  if (path === "license/revoke" || path === "license/restore") {
    await env.DB.prepare("UPDATE licenses SET revoked = ? WHERE key = ?").bind(path.endsWith("revoke") ? 1 : 0, body.key).run();
    return json({ ok: true });
  }
  if (path === "license/unbind") {     // đặc cách chuyển máy
    await env.DB.prepare("UPDATE licenses SET device = NULL, activated = NULL WHERE key = ?").bind(body.key).run();
    return json({ ok: true });
  }
  if (path === "device/block") {
    await env.DB.prepare("UPDATE devices SET blocked = ?, note = COALESCE(?, note) WHERE id = ?").bind(body.blocked ? 1 : 0, body.note || null, body.id).run();
    return json({ ok: true });
  }
  if (path === "device/reset-trial") {
    await env.DB.prepare("DELETE FROM trial_uses WHERE device = ? AND (?2 IS NULL OR skill = ?2)").bind(body.id, body.skill || null).run();
    return json({ ok: true });
  }
  if (path === "product") {
    await env.DB.prepare(`INSERT INTO products (id, name, price, active, sort) VALUES (?1, ?2, ?3, ?4, ?5)
        ON CONFLICT(id) DO UPDATE SET name = ?2, price = ?3, active = ?4, sort = ?5`)
      .bind(body.id, body.name, Math.max(0, Math.round(Number(body.price) || 0)), body.active === false ? 0 : 1, Number(body.sort) || 0).run();
    return json({ ok: true });
  }
  if (path === "settings") {
    for (const k of ["bank", "account", "account_name", "trial_limit"]) {
      if (body[k] !== undefined) await env.DB.prepare("INSERT INTO settings (k, v) VALUES (?1, ?2) ON CONFLICT(k) DO UPDATE SET v = ?2").bind(k, String(body[k]).trim()).run();
    }
    return json({ ok: true });
  }
  if (path === "order/paid") {          // xác nhận tay khi tiền về mà webhook không khớp (ghi sai nội dung CK)
    const o = await env.DB.prepare("SELECT * FROM orders WHERE id = ? AND status = 'pending'").bind(body.id).first();
    if (!o) return err("đơn không ở trạng thái chờ");
    return json({ ok: true, key: await markPaid(env, o, "manual") });
  }
  return err("không có lệnh này", 404);
}

async function video(req, env) {
  // tài nguyên tĩnh không trả 206 → tự cắt đoạn theo Range (Safari/iOS bắt buộc khi phát video)
  const r = await env.ASSETS.fetch(new Request(new URL(req.url).toString()));
  if (!r.ok) return r;
  const type = r.headers.get("content-type") || "video/mp4";
  const base = { "content-type": type, "accept-ranges": "bytes", "cache-control": "public, max-age=86400" };
  const m = /bytes=(\d*)-(\d*)/.exec(req.headers.get("range") || "");
  if (!m) return new Response(r.body, { headers: { ...base, "content-length": r.headers.get("content-length") || "" } });
  const buf = await r.arrayBuffer(), n = buf.byteLength;
  let a = m[1] === "" ? n - Number(m[2]) : Number(m[1]);
  let b = m[1] === "" || m[2] === "" ? n - 1 : Math.min(Number(m[2]), n - 1);
  if (!(a >= 0 && a <= b && a < n)) return new Response(null, { status: 416, headers: { ...base, "content-range": `bytes */${n}` } });
  return new Response(buf.slice(a, b + 1), { status: 206, headers: { ...base, "content-range": `bytes ${a}-${b}/${n}`, "content-length": String(b - a + 1) } });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url), p = url.pathname;
    if (p.startsWith("/video/") && env.ASSETS) return await video(req, env);
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    try {
      if (p === "/" || p === "/mua") return html(BUY_HTML);
      if (p === "/huong-dan" || p === "/huong-dan/") return html(GUIDE_HTML);
      if (p === "/admin") return html(ADMIN_HTML);
      if (p.startsWith("/admin/api/")) return await admin(env, req, p.slice(11));
      if (p === "/v1/products") return await products(env);
      if (p.startsWith("/v1/order/") && req.method === "GET") return await getOrder(env, p.slice(10));
      if (p === "/v1/webhook/sepay" && req.method === "POST") return await sepay(env, req);
      if (req.method === "POST") {
        const body = await req.json().catch(() => ({}));
        if (p === "/v1/status") return await status(env, body);
        if (p === "/v1/trial") return await trial(env, body);
        if (p === "/v1/activate") return await activate(env, body);
        if (p === "/v1/order") return await createOrder(env, body);
      }
      return err("không tìm thấy", 404);
    } catch (e) {
      return err("lỗi máy chủ: " + (e && e.message), 500);
    }
  },
};

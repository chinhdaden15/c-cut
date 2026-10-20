// Tạo cặp khoá ký mã bản quyền (Ed25519). Khoá BÍ MẬT → `npx wrangler secret put SIGNING_KEY` (không đưa vào repo);
// khoá CÔNG KHAI (hex) → thagent/license.py PUBLIC_KEY.   node scripts/keygen.mjs [file_lưu_khoá_bí_mật]
import { generateKeyPairSync } from "node:crypto";
import { writeFileSync } from "node:fs";
const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const priv = privateKey.export({ type: "pkcs8", format: "der" }).toString("base64");
const pub = publicKey.export({ type: "spki", format: "der" }).subarray(-32).toString("hex");
if (process.argv[2]) writeFileSync(process.argv[2], JSON.stringify({ SIGNING_KEY: priv, PUBLIC_KEY_HEX: pub }, null, 1), { mode: 0o600 });
console.log(JSON.stringify({ SIGNING_KEY: process.argv[2] ? "(đã lưu vào " + process.argv[2] + ")" : priv, PUBLIC_KEY_HEX: pub }));

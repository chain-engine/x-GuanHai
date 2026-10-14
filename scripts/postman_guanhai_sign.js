// ============================================================================
// GuanHai-1 签名 - Postman 预请求脚本
// 自动计算并写入 X-App-Id / X-App-Date / X-App-Authorization 三个请求头
// ============================================================================
// 使用步骤：
//   1. Postman 中新建 Collection（或选中已有 Collection）
//   2. 在 Collection 的 Variables 中添加变量：APP_ID = app、APP_KEY = gk_admin_change_me
//      （不配置也可以，脚本下方有默认值兜底）
//   3. 把本脚本完整粘贴到 Collection 的 "Pre-request Script" 标签页
//   4. 新建任意请求（URL 用完整地址，如 http://127.0.0.1:8000/api/v1/rag/query），
//      Body 选 raw + JSON，发送即可，无需手填任何鉴权头
// 说明：
//   - 签名头 300 秒过期，过期重发请求即可（脚本每次请求都会重算）
//   - 签名依赖 body 原文，脚本直接读取 pm.request.body.raw，与发送字节一致
// ============================================================================

// 1) AppId / AppKey：优先取变量，缺省用种子应用默认值
const APP_ID = pm.variables.get("APP_ID") || "app";
const APP_KEY = pm.variables.get("APP_KEY") || "gk_admin_change_me";

// 2) URI 归一：path 去除尾部斜杠，保留 query（与 src/core/signature.py 同源）
const urlStr = pm.request.url.toString();
let pathname = "";
let search = "";
try {
  const u = new URL(urlStr);
  pathname = u.pathname;
  search = u.search;
} catch (e) {
  pathname = urlStr.split("?")[0] || "/";
  search = urlStr.includes("?") ? "?" + urlStr.split("?")[1] : "";
}
const uri = pathname.replace(/\/+$/, "") || "/" + (search || "");

// 3) body 原文哈希（空 body 时协议要求为空串）
const rawBody = pm.request.body && pm.request.body.raw ? pm.request.body.raw : "";
const bodyHash = rawBody === "" ? "" : CryptoJS.SHA256(rawBody).toString(CryptoJS.enc.Hex);

// 4) 当前时间 RFC1123 GMT（如 Wed, 14 Oct 2026 04:28:38 GMT）
const date = new Date().toUTCString();

// 5) 签名串 + HMAC-SHA256 签名值
const signingString =
  "GuanHai-1" + pm.request.method.toUpperCase() + uri + "application/json" + date + bodyHash;
const sig = CryptoJS.HmacSHA256(signingString, APP_KEY).toString(CryptoJS.enc.Hex);

// 6) 写入三个请求头（先清除旧值再写入，避免重复头）
["X-App-Id", "X-App-Date", "X-App-Authorization"].forEach((h) => {
  if (pm.request.headers.has(h)) pm.request.headers.remove(h);
});
pm.request.headers.add({ key: "X-App-Id", value: APP_ID });
pm.request.headers.add({ key: "X-App-Date", value: date });
pm.request.headers.add({ key: "X-App-Authorization", value: `GuanHai-1 ${APP_ID}:${sig}` });

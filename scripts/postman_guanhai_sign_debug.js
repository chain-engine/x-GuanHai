// ============================================================================
// GuanHai-1 签名认证（打印调试版）
// 方法 / 完整URL / 签名URI / Date / body原文 / SHA256(body) / 签名串 / 签名值 / 实际请求头
// ============================================================================

// ---------- 1. 取 AppId / AppKey ----------
const appId = pm.collectionVariables.get("appId");
const appKey = pm.collectionVariables.get("appKey");
if (!appId || !appKey) {
    console.warn("[GuanHai-1] 未配置 appId/appKey，跳过签名");
    return;
}

// ---------- 2. 公开接口免签 ----------
const resolvedPath = pm.variables.replaceIn(pm.request.url.getPath());
const publicPaths = ["/api/v1/health", "/api/v1/version", "/api/v1/status"];
if (publicPaths.some((p) => resolvedPath.startsWith(p))) {
    console.log("[GuanHai-1] 公开接口，跳过签名：", resolvedPath);
    return;
}

// ---------- 3. 组装签名要素 ----------
const method = pm.request.method;
const queryStr = pm.variables.replaceIn(pm.request.url.getQueryString() || "");
const uri = resolvedPath + (queryStr ? "?" + queryStr : ""); // 签名用 URI：path 去尾斜杠 + query
const contentType = "application/json";
const date = new Date().toUTCString(); // RFC1123 GMT

// body SHA256（raw JSON 模式才参与签名；formdata 不参与）
let rawBody = "";
let bodyHash = "";
if (pm.request.body && pm.request.body.mode === "raw") {
    rawBody = pm.request.body.raw || "";
    bodyHash = rawBody ? CryptoJS.SHA256(rawBody).toString(CryptoJS.enc.Hex) : "";
}

// ---------- 4. 计算签名 ----------
const signingString = "GuanHai-1" + method + uri + contentType + date + bodyHash;
const signature = CryptoJS.HmacSHA256(signingString, appKey).toString(CryptoJS.enc.Hex);

// ---------- 5. 写入请求头 ----------
pm.request.headers.upsert({ key: "X-App-Id", value: appId });
pm.request.headers.upsert({ key: "X-App-Date", value: date });
pm.request.headers.upsert({ key: "X-App-Authorization", value: "GuanHai-1 " + appId + ":" + signature });
if (!pm.request.body || pm.request.body.mode !== "formdata") {
    pm.request.headers.upsert({ key: "Content-Type", value: "application/json" });
}

// ---------- 6. 打印关键信息（打开 Postman 左下角 Console 查看） ----------
console.log("================= GuanHai-1 签名过程 =================");
console.log("[1] 请求方法       :", method);
console.log("[2] 完整URL        :", pm.variables.replaceIn(pm.request.url.toString()));
console.log("[3] 签名URI        :", uri);
console.log("[4] X-App-Date     :", date);
console.log("[5] body 原文      :", rawBody || "(空)");
console.log("[6] SHA256(body)   :", bodyHash || "(空)");
console.log("[7] 签名串         :", signingString);
console.log("[8] 签名值         :", signature);
console.log("[9] 实际请求头     :");
console.log("      X-App-Id            :", appId);
console.log("      X-App-Date          :", date);
console.log("      X-App-Authorization :", "GuanHai-1 " + appId + ":" + signature);
console.log("======================================================");

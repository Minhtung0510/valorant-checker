/**
 * Valorant Auth - Batch Mode
 * 
 * Cách dùng: node scripts/riot-auth.js batch
 * 
 * Nhập danh sách username:password (mỗi dòng 1 account)
 * Script sẽ tự động:
 * 1. Mở trình duyệt cho từng account
 * 2. Chờ đăng nhập, capture token
 * 3. Lưu tất cả token vào file
 * 
 * Output: tokens_YYYYMMDD_HHMMSS.txt
 */

const http = require("http");
const { exec } = require("child_process");
const readline = require("readline");
const fs = require("fs");
const path = require("path");
const url = require("url");
const crypto = require("crypto");

function openBrowser(urlStr) {
  switch (process.platform) {
    case "win32":
      exec(`start "" "${urlStr}"`);
      break;
    case "darwin":
      exec(`open "${urlStr}"`);
      break;
    default:
      exec(`xdg-open "${urlStr}"`);
  }
}

function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer);
    });
  });
}

function waitForToken(port, timeout = 120000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      server.close();
      reject(new Error("timeout"));
    }, timeout);

    const server = http.createServer((req, res) => {
      const fullUrl = `http://localhost:${port}${req.url}`;
      const parsed = url.parse(fullUrl, true);
      const hash = parsed.hash || "";

      if (!hash.includes("access_token")) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(`<!DOCTYPE html>
          <html><head><meta charset="utf-8"><title>Đang chờ...</title></head>
          <body style="background:#0f1923;color:#ece8e1;font-family:Segoe UI,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center">
            <div>
              <div style="font-size:3em">⏳</div>
              <h2 style="color:#ff4655">Đang chờ đăng nhập...</h2>
              <p style="color:#8b978f">Vui lòng đăng nhập trên trình duyệt rồi đợi.</p>
            </div>
          </body></html>`);
        return;
      }

      clearTimeout(timer);

      const fragment = hash.startsWith("#") ? hash.slice(1) : hash;
      const params = new URLSearchParams(fragment);
      const accessToken = params.get("access_token");
      const expiresIn = params.get("expires_in");
      const idToken = params.get("id_token");

      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(`<!DOCTYPE html>
        <html><head><meta charset="utf-8"><title>Thành công</title></head>
        <body style="background:#0f1923;color:#ece8e1;font-family:Segoe UI,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center">
          <div>
            <div style="font-size:3em">✅</div>
            <h2 style="color:#4caf50">Token đã được lấy!</h2>
            <p style="color:#8b978f">Có thể đóng tab này.</p>
          </div>
        </body></html>`);

      setTimeout(() => {
        server.close();
        resolve({ accessToken, expiresIn, idToken });
      }, 500);
    });

    server.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });

    server.listen(port, () => {
      // Server ready
    });
  });
}

function findFreePort(startFrom = 52274) {
  return new Promise((resolve, reject) => {
    const tryPort = (port) => {
      const s = http.createServer();
      s.once("error", () => {
        if (port > 60000) { reject(new Error("No free port found")); return; }
        tryPort(port + 1);
      });
      s.once("listening", () => {
        s.close(() => resolve(port));
      });
      s.listen(port, "127.0.0.1");
    };
    tryPort(startFrom);
  });
}

async function processAccount(username, index, total) {
  console.log(`\n${index}/${total} — Đang mở trình duyệt cho: ${username}`);
  const port = await findFreePort();
  const redirectUri = `http://localhost:${port}/redirect`;
  const authUrl =
    `https://auth.riotgames.com/authorize` +
    `?redirect_uri=${encodeURIComponent(redirectUri)}` +
    `&client_id=riot-client` +
    `&response_type=token%20id_token` +
    `&nonce=${crypto.randomUUID()}` +
    `&scope=openid%20link%20ban%20lol_region%20account`;

  openBrowser(authUrl);
  console.log(`   Mở: ${authUrl.slice(0, 80)}...`);

  try {
    const result = await waitForToken(port);
    console.log(`   ✅ Token nhận được (${result.accessToken.slice(0, 40)}...)`);
    return {
      username,
      redirectUrl: `http://localhost/redirect#access_token=${result.accessToken}`,
      accessToken: result.accessToken,
      expiresIn: result.expiresIn,
    };
  } catch (err) {
    if (err.message === "timeout") {
      console.log(`   ⏰ Hết thời gian chờ (2 phút).`);
    } else {
      console.log(`   ❌ Lỗi: ${err.message}`);
    }
    return {
      username,
      error: err.message === "timeout" ? "Hết thời gian chờ (2 phút)" : err.message,
    };
  }
}

async function batchMode() {
  console.log("═══════════════════════════════════════════");
  console.log("   Valorant Auth - Batch Login             ");
  console.log("═══════════════════════════════════════════\n");

  const input = await ask("Paste danh sách username:password (mỗi dòng 1, xong nhấn Enter rồi Ctrl+C hoặc Enter trắng để kết thúc):\n> ");

  const lines = input.split("\n").filter((l) => l.trim());
  if (lines.length === 0) {
    console.log("Không có tài khoản nào. Thoát.");
    return;
  }

  const credentials = [];
  for (const line of lines) {
    const idx = line.indexOf(":");
    if (idx > 0) {
      credentials.push(line.trim());
    } else {
      console.log(`⚠ Bỏ qua dòng không hợp lệ: ${line}`);
    }
  }

  if (credentials.length === 0) {
    console.log("Không có tài khoản hợp lệ. Thoát.");
    return;
  }

  console.log(`\n📋 Tổng cộng: ${credentials.length} tài khoản\n`);

  const results = [];
  for (let i = 0; i < credentials.length; i++) {
    const result = await processAccount(credentials[i], i + 1, credentials.length);
    results.push(result);
  }

  // Save results
  const now = new Date();
  const timestamp = now.toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const successResults = results.filter((r) => r.accessToken);
  const failedResults = results.filter((r) => r.error);

  // Save tokens file
  const tokensContent = [
    `# Valorant Auth Results - ${now.toLocaleString("vi-VN")}`,
    `# Success: ${successResults.length} / ${credentials.length}`,
    ``,
    ...successResults.map((r, i) => [
      `# Account ${i + 1}: ${r.username}`,
      r.redirectUrl,
      ``,
    ].join("\n")),
  ].join("\n");

  const tokensPath = path.join(__dirname, `tokens_${timestamp}.txt`);
  fs.writeFileSync(tokensPath, tokensContent, "utf8");

  // Save JSON report
  const reportPath = path.join(__dirname, `report_${timestamp}.json`);
  fs.writeFileSync(reportPath, JSON.stringify({
    timestamp: now.toISOString(),
    total: credentials.length,
    success: successResults.length,
    failed: failedResults.length,
    results,
  }, null, 2), "utf8");

  console.log(`\n═══════════════════════════════════════════`);
  console.log(`   Kết quả`);
  console.log(`═══════════════════════════════════════════`);
  console.log(`\n✅ Thành công: ${successResults.length}`);
  console.log(`❌ Thất bại: ${failedResults.length}`);
  console.log(`\n📁 File đã lưu:`);
  console.log(`   - Tokens: ${tokensPath}`);
  console.log(`   - Report: ${reportPath}`);

  if (failedResults.length > 0) {
    console.log(`\n⚠ Các tài khoản thất bại:`);
    for (const r of failedResults) {
      console.log(`   - ${r.username}: ${r.error}`);
    }
  }

  console.log(`\n💡 Copy nội dung file tokens_${timestamp}.txt và paste vào Bulk Checker.`);
}

async function singleMode() {
  const port = await findFreePort();
  const redirectUri = `http://localhost:${port}/redirect`;
  const authUrl =
    `https://auth.riotgames.com/authorize` +
    `?redirect_uri=${encodeURIComponent(redirectUri)}` +
    `&client_id=riot-client` +
    `&response_type=token%20id_token` +
    `&nonce=${crypto.randomUUID()}` +
    `&scope=openid%20link%20ban%20lol_region%20account`;

  console.log("═══════════════════════════════════════════");
  console.log("   Valorant Auth - Lấy Token 1 Account    ");
  console.log("═══════════════════════════════════════════\n");
  console.log("🔗 Mở trình duyệt đăng nhập...\n");
  openBrowser(authUrl);
  console.log("⏳ Đang chờ đăng nhập (2 phút timeout)...\n");

  try {
    const result = await waitForToken(port);
    console.log("✅ Token nhận được!\n");
    console.log("───────────────────────────────────────────");
    console.log("Redirect URL để check account:");
    console.log(`http://localhost/redirect#access_token=${result.accessToken}`);
    console.log("───────────────────────────────────────────\n");

    // Save to file
    const now = new Date();
    const timestamp = now.toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const filePath = path.join(__dirname, `token_${timestamp}.txt`);
    fs.writeFileSync(filePath, `http://localhost/redirect#access_token=${result.accessToken}`, "utf8");
    console.log(`📁 Token đã lưu vào: ${filePath}`);
    console.log(`\n💡 Copy dòng trên và paste vào tool Bulk Checker.\n`);
  } catch (err) {
    console.error("❌ Lỗi:", err.message);
    process.exit(1);
  }
}

const mode = process.argv[2]?.toLowerCase();
if (mode === "batch" || mode === "b") {
  batchMode();
} else {
  singleMode();
}

const { Client, LocalAuth } = require("whatsapp-web.js");
const http = require("http");
const axios = require("axios");

const PYTHON_URL = process.env.CLAWBLINK_WHATSAPP_PYTHON_URL || "http://127.0.0.1:8070";
const SEND_PORT = Number(process.env.CLAWBLINK_WHATSAPP_SEND_PORT || 8071);

console.log("Starting ClawBlink WhatsApp bridge...");
console.log(`  Python bridge endpoint: ${PYTHON_URL}/whatsapp/incoming`);
console.log(`  Node send server:       http://127.0.0.1:${SEND_PORT}/send`);

const client = new Client({
  authStrategy: new LocalAuth({ clientId: "clawblink" }),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  },
});

client.on("ready", () => {
  console.log("WhatsApp client is ready. Listening for messages...");
});

client.on("message", async (message) => {
  try {
    const from = message.from; // e.g. '1234567890@c.us'
    const body = message.body || "";

    if (!body.trim()) return;

    await axios.post(`${PYTHON_URL}/whatsapp/incoming`, {
      from,
      body,
    });
  } catch (err) {
    console.error("Error forwarding message to Python bridge:", err.message || err);
  }
});

client.on("auth_failure", (msg) => {
  console.error("Authentication failure:", msg);
});

client.initialize();

// Simple HTTP server for Python to ask us to send WhatsApp messages.
const server = http.createServer((req, res) => {
  if (req.method === "POST" && req.url === "/send") {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk.toString();
    });
    req.on("end", async () => {
      try {
        const data = JSON.parse(body || "{}");
        const to = data.to;
        const text = data.text;
        if (!to || !text) {
          res.statusCode = 400;
          res.end("Missing 'to' or 'text'");
          return;
        }
        await client.sendMessage(to, text);
        res.statusCode = 200;
        res.end("ok");
      } catch (err) {
        console.error("Error in /send handler:", err.message || err);
        res.statusCode = 500;
        res.end("error");
      }
    });
  } else if (req.method === "GET" && req.url === "/health") {
    res.statusCode = 200;
    res.end("ok");
  } else {
    res.statusCode = 404;
    res.end("not found");
  }
});

server.listen(SEND_PORT, "127.0.0.1", () => {
  console.log(`Send server listening on http://127.0.0.1:${SEND_PORT}/send`);
});


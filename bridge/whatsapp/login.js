const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");

console.log("ClawBlink WhatsApp login");
console.log("If a QR appears below, scan it with WhatsApp:");
console.log("  WhatsApp → Settings → Linked devices → Link a device\n");

const client = new Client({
  authStrategy: new LocalAuth({ clientId: "clawblink" }),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  },
});

client.on("qr", (qr) => {
  console.log("QR received. Scan this code:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", () => {
  console.log("WhatsApp client is ready. Login complete.");
  console.log("You can now close this process and run `node gateway.js`.");
});

client.on("auth_failure", (msg) => {
  console.error("Authentication failure:", msg);
});

client.initialize();


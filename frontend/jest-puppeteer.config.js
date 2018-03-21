module.exports = {
  server: {
    command: "cd ../; python run.py 2>/dev/null", // We hide stderr because it makes it a pain to see what errored
    port: 8080
  },
  launch: {
    args: ["--no-sandbox"]
    // headless: false,
    // slowMo: 200
    // devtools: true
  }
};

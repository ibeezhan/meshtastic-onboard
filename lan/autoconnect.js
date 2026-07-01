/* One-click auto-connect for the self-hosted Meshtastic web client.
 *
 * The client normally opens on "how do you want to connect?". Since we always
 * want the same HTTP proxy on this LAN, this script fills the address and clicks
 * Connect automatically. The proxy is assumed to be on the SAME host that served
 * this page, port 8080 (that's how start-lan-stack.sh sets things up), so it
 * adapts to whatever LAN IP you're on. Override with ?proxy=host:port if needed,
 * or disable entirely with ?noauto.
 */
(function () {
  const params = new URLSearchParams(location.search);
  if (params.has("noauto")) return;
  const PROXY = params.get("proxy") || (location.hostname + ":8080");

  const banner = document.createElement("div");
  banner.style.cssText =
    "position:fixed;z-index:99999;left:50%;top:12px;transform:translateX(-50%);" +
    "background:#0b0f14;color:#7fd1a4;border:1px solid #223040;border-radius:8px;" +
    "padding:6px 14px;font:13px system-ui,sans-serif;box-shadow:0 4px 16px #0008";
  banner.textContent = "Auto-connecting to " + PROXY + " …";
  const showBanner = () => { if (!banner.isConnected) document.body.appendChild(banner); };

  function setReactInput(input, value) {
    const proto = Object.getPrototypeOf(input);
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set
      || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const visible = (el) => el && el.offsetParent !== null && !el.disabled;
  const btnByText = (re) =>
    [...document.querySelectorAll("button")].filter(
      (b) => visible(b) && re.test((b.textContent || "").trim())
    );

  let filled = false, done = false, tries = 0;

  const tick = setInterval(() => {
    if (done) { clearInterval(tick); return; }
    if (tries++ > 60) { clearInterval(tick); banner.textContent = "Auto-connect gave up — connect manually to " + PROXY; return; }
    showBanner();

    // Step 1: make sure an "Add/New connection" dialog is open. If we can't find a
    // text input yet, try clicking a button that opens the connect dialog.
    let input = [...document.querySelectorAll('input[type="text"], input[type="url"], input:not([type])')]
      .find((el) => visible(el));
    if (!input) {
      const opener = btnByText(/new connection|add connection|add new|^connect$|add device|^add$/i)[0];
      if (opener) opener.click();
      return;
    }

    // Step 2: fill the address once.
    if (!filled) {
      setReactInput(input, PROXY);
      filled = true;
      return; // let React process the change before we click
    }

    // Step 3: click the primary Connect/Save/Add button in the dialog.
    const connect = btnByText(/^(connect|save|add|connect device)$/i)
      .sort((a, b) => (/connect/i.test(b.textContent) ? 1 : 0) - (/connect/i.test(a.textContent) ? 1 : 0))[0];
    if (connect) {
      connect.click();
      done = true;
      banner.textContent = "Connecting to " + PROXY + " …";
      setTimeout(() => banner.remove(), 6000);
    }
  }, 500);
})();

#!/usr/bin/env python3
"""
LAN web dashboard for a USB-connected Meshtastic node.

The node (e.g. SenseCAP T1000-E) talks over USB serial to this host; this script
holds that one connection and re-serves the node's info as a web page on the LAN,
so any device on the same WiFi can view it WITHOUT Bluetooth. nRF52 boards have no
WiFi of their own, so this host-side bridge is how you get "Meshtastic over LAN web".

Usage:  python3 lan-dashboard.py [PORT_DEV] [HTTP_PORT]
        defaults: PORT_DEV=first /dev/cu.usbmodem*, HTTP_PORT=8765
Open:   http://<this-host-lan-ip>:8765   from any device on the LAN.
"""
import sys, glob, json, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import meshtastic.serial_interface as si
from meshtastic.protobuf import config_pb2

DEV = sys.argv[1] if len(sys.argv) > 1 else (sorted(glob.glob('/dev/cu.usbmodem*')) or [''])[0]
HTTP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765

print(f"connecting to {DEV} ...", flush=True)
iface = si.SerialInterface(DEV)
lock = threading.Lock()
print("connected. building snapshot endpoint.", flush=True)

def snapshot():
    with lock:
        ln = iface.localNode
        lora = ln.localConfig.lora
        chans = []
        for idx in range(8):
            ch = ln.getChannelByChannelIndex(idx)
            if ch is None or ch.role == 0:
                continue
            chans.append({
                "index": idx,
                "role": {1: "PRIMARY", 2: "SECONDARY"}.get(ch.role, ch.role),
                "name": ch.settings.name or "LongFast",
                "encrypted": len(ch.settings.psk) > 1,
            })
        my = iface.myInfo
        now = time.time()
        nodes = []
        for num, nd in (iface.nodes or {}).items():
            u = nd.get("user", {}) or {}
            lh = nd.get("lastHeard")
            dm = nd.get("deviceMetrics", {}) or {}
            nodes.append({
                "id": num,
                "short": u.get("shortName"), "long": u.get("longName"),
                "snr": nd.get("snr"), "hops": nd.get("hopsAway"),
                "battery": dm.get("batteryLevel"),
                "lastHeard": lh,
                "ago_s": int(now - lh) if lh else None,
                "is_self": nd.get("num") == getattr(my, "my_node_num", None),
            })
        nodes.sort(key=lambda n: (n["lastHeard"] or 0), reverse=True)
        return {
            "my_node_num": getattr(my, "my_node_num", None),
            "fw": getattr(iface.metadata, "firmware_version", None),
            "region": config_pb2.Config.LoRaConfig.RegionCode.Name(lora.region),
            "preset": config_pb2.Config.LoRaConfig.ModemPreset.Name(lora.modem_preset),
            "tx_enabled": lora.tx_enabled,
            "channels": chans,
            "node_count": len(nodes),
            "nodes": nodes,
            "ts": now,
        }

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Meshtastic · LAN</title>
<style>
 :root{color-scheme:dark}
 body{margin:0;background:#0b0f14;color:#d7e0ea;font:14px/1.5 -apple-system,system-ui,sans-serif}
 header{padding:16px 20px;border-bottom:1px solid #1c2530;position:sticky;top:0;background:#0b0f14}
 h1{margin:0;font-size:16px;letter-spacing:.3px}
 .pills{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap}
 .pill{background:#121a23;border:1px solid #223040;border-radius:999px;padding:3px 10px;font-size:12px;color:#9fb3c8}
 .pill b{color:#e8f0f8}
 table{width:100%;border-collapse:collapse}
 th,td{text-align:left;padding:10px 20px;border-bottom:1px solid #131b24;font-variant-numeric:tabular-nums}
 th{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#6b8095}
 tr.self td{color:#7fd1a4}
 .muted{color:#62748a}
 .ok{color:#7fd1a4}.warn{color:#e0b15a}
 footer{padding:12px 20px;color:#55687c;font-size:12px}
</style></head><body>
<header>
 <h1>📡 Meshtastic node · LAN dashboard</h1>
 <div class=pills id=pills></div>
</header>
<table><thead><tr><th>Node</th><th>SNR</th><th>Hops</th><th>Batt</th><th>Last heard</th></tr></thead>
<tbody id=rows></tbody></table>
<footer id=foot>loading…</footer>
<script>
function ago(s){if(s==null)return '—';if(s<90)return s+'s';if(s<5400)return Math.round(s/60)+'m';return Math.round(s/3600)+'h'}
async function tick(){
 try{
  const d=await (await fetch('/api/info',{cache:'no-store'})).json();
  document.getElementById('pills').innerHTML=
   `<span class=pill>fw <b>${d.fw||'?'}</b></span>`+
   `<span class=pill>region <b>${d.region}</b></span>`+
   `<span class=pill>preset <b>${d.preset}</b></span>`+
   `<span class=pill>TX <b class=${d.tx_enabled?'ok':'warn'}>${d.tx_enabled?'on':'off'}</b></span>`+
   `<span class=pill>nodes <b>${d.node_count}</b></span>`+
   d.channels.map(c=>`<span class=pill>${c.role[0]} <b>${c.name}</b>${c.encrypted?' 🔒':''}</span>`).join('');
  document.getElementById('rows').innerHTML=d.nodes.map(n=>{
   const ext=!n.is_self, direct=n.snr!=null;
   return `<tr class="${n.is_self?'self':''}">
     <td>${n.is_self?'★ ':''}${n.short||'?'} <span class=muted>${n.long||''}</span></td>
     <td class="${direct&&ext?'ok':'muted'}">${n.snr!=null?n.snr:'—'}</td>
     <td>${n.hops!=null?n.hops:'—'}</td>
     <td>${n.battery!=null?n.battery+'%':'—'}</td>
     <td class=muted>${n.is_self?'(this node)':ago(n.ago_s)}</td></tr>`}).join('');
  document.getElementById('foot').textContent='updated '+new Date(d.ts*1000).toLocaleTimeString()+
    ' · external nodes with an SNR value are real RF neighbors';
 }catch(e){document.getElementById('foot').textContent='error: '+e}
}
tick();setInterval(tick,8000);
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/api/info"):
            try:
                body = json.dumps(snapshot()).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500); self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers(); self.wfile.write(PAGE.encode())

srv = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), H)
print(f"=== dashboard live on http://0.0.0.0:{HTTP_PORT}  (open http://<lan-ip>:{HTTP_PORT}) ===", flush=True)
srv.serve_forever()

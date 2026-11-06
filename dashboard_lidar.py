import sys, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ld14p import LD14P, PORT_DEFAUT

PORT_SERIE = sys.argv[1] if len(sys.argv) > 1 else PORT_DEFAUT
PORT_HTTP = 8000
verrou = threading.Lock()
etat = {"scan": [], "erreur": None}


def boucle_lidar():
    try:
        with LD14P(PORT_SERIE) as lidar:
            for scan in lidar.scans():
                pts = [[round(a, 1), int(d)] for a, d, _ in scan if d > 0]
                with verrou:
                    etat["scan"] = pts
    except Exception as e:
        print("Erreur LiDAR :", e)
        with verrou:
            etat["erreur"] = str(e)


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>LiDAR LD14P</title>
<style>
body{margin:0;background:#0b1220;color:#cbd5e1;font-family:sans-serif}
#bar{padding:8px 12px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
canvas{display:block;margin:0 auto;max-width:100%}
button{padding:4px 10px}
</style></head><body>
<div id="bar">
 <label>Portée <input id="rng" type="range" min="1000" max="8000" step="500" value="4000"> <span id="rv">4 m</span></label>
 <label>Rotation <input id="off" type="number" value="0" step="90" style="width:60px">°</label>
 <label><input id="acc" type="checkbox"> Accumuler</label>
 <button id="clr">Effacer</button>
 <span id="st">connexion...</span>
</div>
<canvas id="c" width="720" height="720"></canvas>
<script>
const $=id=>document.getElementById(id);
const c=$('c'), g=c.getContext('2d'), C=c.width/2;
const mem=document.createElement('canvas'); mem.width=mem.height=c.width;
const gm=mem.getContext('2d');
$('rng').oninput=()=>{ $('rv').textContent=$('rng').value/1000+' m'; gm.clearRect(0,0,mem.width,mem.height); };
$('clr').onclick=()=>gm.clearRect(0,0,mem.width,mem.height);
async function tick(){
  try{
    const j=await (await fetch('/scan')).json();
    const R=+$('rng').value, k=(C-12)/R, off=+$('off').value, acc=$('acc').checked;
    g.fillStyle='#0b1220'; g.fillRect(0,0,c.width,c.height);
    g.drawImage(mem,0,0);
    g.strokeStyle='#243247'; g.fillStyle='#64748b'; g.font='12px sans-serif';
    for(let m=1000;m<=R;m+=1000){
      g.beginPath(); g.arc(C,C,m*k,0,7); g.stroke();
      g.fillText(m/1000+' m',C+4,C-m*k-3);
    }
    g.beginPath(); g.moveTo(C,C); g.lineTo(C,12); g.stroke();
    for(const [a,d] of j.scan){
      if(d>R) continue;
      const t=(a+off)*Math.PI/180, x=C+d*k*Math.sin(t), y=C-d*k*Math.cos(t);
      if(acc){ gm.fillStyle='#22c55e'; gm.fillRect(x-1,y-1,2,2); }
      g.fillStyle='#f43f5e'; g.fillRect(x-1.5,y-1.5,3,3);
    }
    g.fillStyle='#38bdf8'; g.beginPath(); g.arc(C,C,5,0,7); g.fill();
    $('st').textContent=j.erreur?('Erreur : '+j.erreur):(j.scan.length+' points');
  }catch(e){ $('st').textContent='serveur injoignable'; }
  setTimeout(tick,100);
}
tick();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body, typ = PAGE.encode(), "text/html; charset=utf-8"
        elif self.path == "/scan":
            with verrou:
                body = json.dumps(etat).encode()
            typ = "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=boucle_lidar, daemon=True).start()
    print(f"Dashboard : http://localhost:{PORT_HTTP}  (Ctrl+C pour arrêter)")
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT_HTTP), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
import time, httpx

base = "https://contenido.bce.fin.ec/documentos/informacioneconomica/cuentasnacionales/trimestrales/"
agents = {
    "ecuadata": "ecuadata (+https://github.com/bernabecj/ec-public-data)",
    "browser": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36",
}
for label, ua in agents.items():
    for name in ["tou_137_202603.xlsx", "tou_136_202602.xlsx", "tou_132_202502.xlsx"]:
        t = time.time()
        try:
            r = httpx.get(
                base + name,
                headers={"User-Agent": ua},
                timeout=30,
                follow_redirects=True,
            )
            print(label, name, r.status_code, r.content[:4], f"{time.time() - t:.1f}s")
        except httpx.HTTPError as e:
            print(label, name, type(e).__name__, f"{time.time() - t:.1f}s")

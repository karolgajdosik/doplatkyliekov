# 3D ilustrácie liekov

Obrázky v `site/img3d/<forma>-<písmeno ATC>.webp` sú vyrenderované v three.js (headless Chromium, WebGL cez SwiftShader).
Cloudflare build ich negeneruje, sú v repozitári. Nová kombinácia formy a skupiny (napr. nová lieková forma) sa doplní takto:

```
cd tools/3d && npm i three@0.170.0 playwright
python3 -m http.server 8833 &
python3 ../../scripts/illus3d.py --jobs > jobs.json   # chýbajúce kombinácie
OUT=out node run.js "$(cat jobs.json)"
python3 ../../scripts/illus3d.py --webp out           # PNG → site/img3d/*.webp (640×480)
```
Ak obrázok chýba, web použije `other-<písmeno>.webp` alebo `other-V.webp`.

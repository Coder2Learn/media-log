import base64

logos = {
    "JioHotstar": "assets/jiohotstar.png",
    "Sony LIV":   "assets/sonyliv.png",
    "ZEE5":       "assets/zee5.png",
}

for name, path in logos.items():
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    print(f'"{name}": "data:image/png;base64,{b64}",')
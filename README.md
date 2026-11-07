# 🎲 ASCII Cube Studio

Upload any image and watch it come alive as a rotating 3D ASCII cube: rendered in real-time with a custom GLSL shader.

Based on the ASCII cube from the [GitHub Shop](https://thegithubshop.com) footer, extended with a drag-and-drop image upload system.

```
     . . < < > > # #
   . . < < > > # # . .
 . . < < > > # # . . < <
 . < < > > # # . . < < >
 . < > > # # . . < < > >
 . < > > # # . . < < > >
 . < < > > # # . . < < >
 . . < < > > # # . . < <
   . . < < > > # # . .
     . . < < > > # #
```

## ✨ Features

- **Upload any image**: drag-and-drop, file picker, or paste from clipboard (Ctrl+V)
- **Live preview**: see your image before applying, texture swaps instantly
- **GPU-powered ASCII rendering**: GLSL fragment shader converts the 3D scene to ASCII in real-time
- **Interactive controls**: arrow keys, click+drag, touch drag
- **Rainbow mode**: toggle gradient color shader with the 🎨 button
- **Responsive**: adaptive cell sizes across 4 breakpoints (mobile → desktop)
- **Zero dependencies**: single HTML file, Three.js loaded from CDN
- **Dockerized**: serve with `docker compose up`

## 🚀 Quick Start

### Open directly

Just open `index.html` in a modern browser (Chrome, Edge, Firefox, Safari 17+).

### With a local server

```bash
# Python
python -m http.server 8080 -d .

# Node.js
npx serve .
```

### With Docker

```bash
docker compose up -d
# → http://localhost:8080
```

## 📸 Image Upload

Three ways to get your image onto the cube:

| Method | How |
|---|---|
| **Drag & drop** | Drop any image file onto the page: works even while the cube spins |
| **File picker** | Click the 📁 Upload button in the HUD |
| **Clipboard paste** | Copy an image, then Ctrl+V / Cmd+V |

Supports PNG, JPG, GIF, SVG, WebP at any resolution. The image is applied as a texture to all 6 faces of the cube and processed through the ASCII shader in real-time.

## 🎮 Controls

| Input | Action |
|---|---|
| `←` `→` | Rotate left / right |
| `↑` `↓` | Rotate up / down |
| Click + drag | Free rotation |
| Touch + drag | Free rotation (mobile) |
| 📁 Upload | Open image upload overlay |
| ⏸ Pause | Stop / resume auto-rotation |
| 🎨 Color | Toggle rainbow gradient mode |
| Ctrl+V | Paste image from clipboard |

## 🔧 How It Works

1. A subdivided `BoxGeometry(50,50,50,32,32,32)` is textured with the uploaded image (or default Mona) and rendered with Three.js
2. The frame passes through an `EffectComposer` → `RenderPass` → `ShaderPass` pipeline
3. A custom fragment shader pixelizes the scene, converts to greyscale, maps brightness to ASCII characters from a pre-rendered atlas
4. Characters `' ..<>#'` form the brightness ramp (6 levels)
5. Laplacian sharpening + smoothstep produce crisp character edges
6. When a new image is uploaded, the old GPU texture is disposed and replaced instantly

## 🏗️ Architecture

```
index.html          ← Main app (Three.js + GLSL shader + upload UI)
about.html          ← Project info & tech details
Dockerfile          ← nginx:alpine container
docker-compose.yml  ← One-command deploy
```

## ⚡ Performance

- **Zero GC pressure**: reusable Three.js objects in animation loop & input handlers
- **DPR capped at 2×**: prevents framebuffer bloat on high-DPR devices
- **Debounced resize** with GPU texture disposal
- **Auto-pause** when tab is hidden
- **Instant texture swap**: old texture disposed before new one applied

## 📄 License

[MIT](LICENSE)

---

Built by [@Manaiakalani](https://github.com/Manaiakalani) · Forked from [github-ascii-cube](https://github.com/Manaiakalani/github-ascii-cube)

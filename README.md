# ASCII Cube Studio

[Live demo](https://manaiakalani.github.io/ascii-cube-custom/) · [About page](https://manaiakalani.github.io/ascii-cube-custom/about.html)

Upload a picture and watch it wrap a spinning cube, drawn live as ASCII. The scene and the GLSL post-process match [GitHub ASCII Cube](https://github.com/Manaiakalani/github-ascii-cube), a recreation of the footer on the [GitHub Shop](https://thegithubshop.com). This repo adds the studio in front of that cube: preview a file, then apply it to all six faces.

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

The page reads the file in the browser and applies it as a WebGL texture. The picture stays on your machine.

**Use Default** closes the overlay and leaves the cube as it is. On first load that texture is the GitHub Shop Mona. If the shop image cannot load, the page draws an Invertocat on a canvas and uses that instead.

## Features

- **Preview, then apply.** Drop a file anywhere, use the file picker, or paste with Ctrl+V / Cmd+V. The overlay shows the image. **Apply to Cube** swaps the texture.
- **Still images.** PNG, JPEG, WebP, GIF, and SVG, at any resolution. An animated GIF or WebP is sampled from its first frame.
- **GPU ASCII.** A fragment shader maps luminance to the six-step ramp `' ..<>#'`. The first two steps are spaces, so the darkest cells stay blank. Then `.`, `<`, `>`, `#`.
- **Hands on.** Arrow keys, click and drag, and touch drag. Pause stops the spin. Color fades a rainbow gradient in over half a second.
- **Fits the window.** Character cells are 4px below 480px wide, 5px below 768px, 6px below 1024px, and 9px above that. Device pixel ratio is capped at 2.
- **No build step.** `index.html` loads Three.js 0.170.0 from jsDelivr through an import map. Docker serves the two HTML files with nginx.

## Controls

| Input | Action |
|---|---|
| `←` `→` | Rotate left / right |
| `↑` `↓` | Rotate up / down |
| Click + drag | Free rotation |
| Touch + drag | Free rotation |
| Drop a file | Open the overlay and preview that file |
| 📁 Upload | Open the upload overlay |
| Ctrl+V / Cmd+V | Preview an image from the clipboard |
| Apply to Cube | Put the preview on all six faces |
| Use Default | Close the overlay and keep the current texture |
| ⏸ Pause | Stop or resume auto-rotation |
| 🎨 Color | Toggle the rainbow gradient |

## Run it

The app is an ES module, so the browser has to load it over HTTP. Opening the file directly will not start the scene.

```bash
python -m http.server 8080
```

Then open <http://localhost:8080>.

```bash
npx serve .
```

```bash
docker compose up -d
```

Compose publishes port 8080. The image is `nginx:alpine` and contains `index.html` and `about.html`.

## How the shader works

1. Three.js draws a `BoxGeometry(50, 50, 50, 32, 32, 32)` with a `MeshStandardMaterial`. The map is Mona, the drawn Invertocat, or your image. One ambient light lights the mesh.
2. `EffectComposer` runs a `RenderPass`, then a `ShaderPass`.
3. The fragment shader snaps the frame to a cell grid, reads ITU-R BT.709 luminance, and picks one glyph from a canvas atlas of `' ..<>#'`.
4. A Laplacian kernel and `smoothstep` keep the glyph edges sharp.
5. Auto-rotation is a quaternion slerp with damping `0.25`. Applying a new image disposes the previous GPU texture and replaces the material map.

The cube scales in over 2.2 seconds. The animation loop pauses while the tab is hidden, and a resize rebuilds the character atlas after a short debounce.

## Layout

```
index.html               Studio: scene, shader, and upload UI
about.html               Short write-up of the same pipeline
scripts/check-static.py  HTML, inline script, and Docker checks
Dockerfile               nginx:alpine image
docker-compose.yml       Publishes host port 8080
.github/workflows/ci.yml       Checks on pull requests and on master
.github/workflows/pages.yml    Publishes index.html and about.html
```

`python3 scripts/check-static.py` is what CI runs. It needs Node on `PATH` so it can syntax-check the inline scripts.

## License

[MIT](LICENSE)

Built by [@Manaiakalani](https://github.com/Manaiakalani). The cube without the uploader is [github-ascii-cube](https://github.com/Manaiakalani/github-ascii-cube).

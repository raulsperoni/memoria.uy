# How to Generate PNG Exports

The PNG exports are generated from the source SVG files in `../src/logo/`.

## Option 1: Using ImageMagick (Recommended)

Install ImageMagick:
```bash
# macOS
brew install imagemagick

# Ubuntu/Debian
sudo apt-get install imagemagick

# Windows (via Chocolatey)
choco install imagemagick
```

Run the generation script:
```bash
./generate-exports.sh
```

## Option 2: Using Inkscape

Install Inkscape and use the command line:
```bash
inkscape src/logo/memoria-uy-mark.svg \
  --export-type=png \
  --export-filename=export/png/black-on-white/mark/memoria-uy-mark-512.png \
  --export-width=512 \
  --export-height=512
```

## Option 3: Using Node.js (sharp)

Install sharp:
```bash
npm install -g sharp-cli
```

Convert:
```bash
sharp -i src/logo/memoria-uy-mark.svg -o export/png/black-on-white/mark/memoria-uy-mark-512.png resize 512 512
```

## Option 4: Online Tools

Upload SVG to:
- https://cloudconvert.com/svg-to-png
- https://svgtopng.com/

Export at these sizes:
- 16px, 32px, 48px, 64px, 128px, 256px, 512px

## Required Exports

### Black on White
- Mark: 512, 256, 128, 64
- Favicon: 32, 16
- Extension: 128, 48

### White on Black
- Mark: 512, 256, 128, 64
- Favicon: 32, 16
- Extension: 128, 48

## Manual Export Guide

If you have a graphic design tool (Figma, Illustrator, Sketch):

1. Open the SVG file
2. Export as PNG at the required sizes
3. Ensure background color matches:
   - **Black on white**: White background (#FFFFFF)
   - **White on black**: Black background (#000000)
4. Save to the appropriate folder in `export/png/`

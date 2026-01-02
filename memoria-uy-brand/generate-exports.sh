#!/bin/bash
# Generate PNG exports from SVG sources
# Requires ImageMagick (brew install imagemagick)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎨 Generating memoria.uy brand assets..."
echo ""

# Check if ImageMagick is installed
if ! command -v magick &> /dev/null && ! command -v convert &> /dev/null; then
    echo "❌ Error: ImageMagick not found"
    echo "Install it with: brew install imagemagick"
    echo "Or see export/GENERATE.md for alternatives"
    exit 1
fi

# Use 'magick' on newer versions, 'convert' on older
CONVERT_CMD="magick"
if ! command -v magick &> /dev/null; then
    CONVERT_CMD="convert"
fi

# Black on White variant
echo "📦 Generating black-on-white variants..."

# Mark (logo)
for size in 512 256 128 64; do
    echo "  → Mark ${size}x${size}..."
    $CONVERT_CMD -background white \
                 -density 300 \
                 src/logo/memoria-uy-mark.svg \
                 -resize ${size}x${size} \
                 export/png/black-on-white/mark/memoria-uy-mark-${size}.png
done

# Favicon
for size in 32 16; do
    echo "  → Favicon ${size}x${size}..."
    $CONVERT_CMD -background white \
                 -density 300 \
                 src/logo/memoria-uy-mark.svg \
                 -resize ${size}x${size} \
                 export/png/black-on-white/favicon/favicon-${size}.png
done

# Extension icons
for size in 128 48; do
    echo "  → Extension icon ${size}x${size}..."
    $CONVERT_CMD -background white \
                 -density 300 \
                 src/logo/memoria-uy-mark.svg \
                 -resize ${size}x${size} \
                 export/png/black-on-white/extension/icon-${size}.png
done

# White on Black variant
echo ""
echo "📦 Generating white-on-black variants..."

# Mark (logo)
for size in 512 256 128 64; do
    echo "  → Mark ${size}x${size}..."
    $CONVERT_CMD -background black \
                 -density 300 \
                 src/logo/memoria-uy-mark-inverse.svg \
                 -resize ${size}x${size} \
                 export/png/white-on-black/mark/memoria-uy-mark-${size}.png
done

# Favicon
for size in 32 16; do
    echo "  → Favicon ${size}x${size}..."
    $CONVERT_CMD -background black \
                 -density 300 \
                 src/logo/memoria-uy-mark-inverse.svg \
                 -resize ${size}x${size} \
                 export/png/white-on-black/favicon/favicon-${size}.png
done

# Extension icons
for size in 128 48; do
    echo "  → Extension icon ${size}x${size}..."
    $CONVERT_CMD -background black \
                 -density 300 \
                 src/logo/memoria-uy-mark-inverse.svg \
                 -resize ${size}x${size} \
                 export/png/white-on-black/extension/icon-${size}.png
done

# Copy SVG exports
echo ""
echo "📦 Copying SVG exports..."
cp src/logo/memoria-uy-mark.svg export/svg/black-on-white/memoria-uy-mark.svg
cp src/logo/memoria-uy-mark-inverse.svg export/svg/white-on-black/memoria-uy-mark.svg

# Generate watermark PNG
echo ""
echo "📦 Generating watermark..."
$CONVERT_CMD -background none \
             -density 300 \
             social/watermark/memoria-uy-watermark.svg \
             -resize 512x512 \
             social/watermark/memoria-uy-watermark.png

echo ""
echo "✅ All assets generated successfully!"
echo ""
echo "📁 Exports location:"
echo "   → PNG: export/png/"
echo "   → SVG: export/svg/"
echo "   → Watermark: social/watermark/"

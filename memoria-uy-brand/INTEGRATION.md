# Integration Guide

How to integrate memoria.uy brand assets into the project.

## 1. Generate PNG Exports

First, generate all PNG assets from the source SVGs:

```bash
cd memoria-uy-brand
./generate-exports.sh
```

This requires ImageMagick. See `export/GENERATE.md` for alternatives.

## 2. Web Favicon

Copy favicon files to Django static directory:

```bash
# From project root
cp memoria-uy-brand/export/png/black-on-white/favicon/favicon-32.png \
   core/static/favicon-32x32.png

cp memoria-uy-brand/export/png/black-on-white/favicon/favicon-16.png \
   core/static/favicon-16x16.png
```

Update `core/templates/base.html`:

```html
<head>
  <!-- Favicon -->
  <link rel="icon" type="image/png" sizes="32x32"
        href="{% static 'favicon-32x32.png' %}">
  <link rel="icon" type="image/png" sizes="16x16"
        href="{% static 'favicon-16x16.png' %}">
  <link rel="shortcut icon" href="{% static 'favicon-32x32.png' %}">
</head>
```

## 3. Browser Extension

Update extension manifest with new icons:

```bash
# Copy extension icons
cp memoria-uy-brand/export/png/black-on-white/extension/icon-128.png \
   browser-extension/icons/icon-128.png

cp memoria-uy-brand/export/png/black-on-white/extension/icon-48.png \
   browser-extension/icons/icon-48.png

# Also copy 16px as fallback
cp memoria-uy-brand/export/png/black-on-white/favicon/favicon-16.png \
   browser-extension/icons/icon-16.png
```

Update `browser-extension/manifest.json`:

```json
{
  "icons": {
    "16": "icons/icon-16.png",
    "48": "icons/icon-48.png",
    "128": "icons/icon-128.png"
  },
  "action": {
    "default_icon": {
      "16": "icons/icon-16.png",
      "48": "icons/icon-48.png",
      "128": "icons/icon-128.png"
    }
  }
}
```

## 4. Logo in Header (Optional)

If you want to add the logo to the site header:

```bash
cp memoria-uy-brand/export/svg/black-on-white/memoria-uy-mark.svg \
   core/static/logo.svg
```

In `core/templates/base.html`:

```html
<header class="border-b-2 border-black">
  <div class="max-w-7xl mx-auto px-4 py-4 flex items-center gap-3">
    <img src="{% static 'logo.svg' %}" alt="memoria.uy" class="h-8 w-8">
    <h1 class="text-xl font-bold mono">memoria.uy</h1>
  </div>
</header>
```

## 5. Social Media Metadata

Add Open Graph meta tags with logo:

```bash
cp memoria-uy-brand/export/png/black-on-white/mark/memoria-uy-mark-512.png \
   core/static/og-image.png
```

In `core/templates/base.html`:

```html
<head>
  <!-- Open Graph -->
  <meta property="og:title" content="memoria.uy - Vota noticias uruguayas">
  <meta property="og:description" content="Votá noticias de forma anónima y explorá patrones de opinión colectiva.">
  <meta property="og:image" content="{% static 'og-image.png' %}">
  <meta property="og:type" content="website">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="memoria.uy">
  <meta name="twitter:image" content="{% static 'og-image.png' %}">
</head>
```

## 6. Watermark for Screenshots (Optional)

If you want to add a watermark to shared news screenshots:

```bash
cp memoria-uy-brand/social/watermark/memoria-uy-watermark.png \
   core/static/watermark.png
```

Use with CSS:

```css
.screenshot {
  position: relative;
}

.screenshot::after {
  content: '';
  position: absolute;
  bottom: 10px;
  right: 10px;
  width: 48px;
  height: 48px;
  background: url('/static/watermark.png') no-repeat;
  background-size: contain;
}
```

## 7. Update README

Update project README with logo:

```markdown
<p align="center">
  <img src="memoria-uy-brand/export/png/black-on-white/mark/memoria-uy-mark-256.png" alt="memoria.uy logo" width="128">
</p>

# memoria.uy
```

## Typography Update

The brand uses **IBM Plex Mono**. Update `theme/static_src/tailwind.config.js`:

```javascript
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        mono: [
          'IBM Plex Mono',
          'JetBrains Mono',
          'ui-monospace',
          'monospace'
        ],
      }
    }
  }
}
```

Add to HTML head:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&display=swap" rel="stylesheet">
```

## File Checklist

After integration, you should have:

- ✅ `core/static/favicon-32x32.png`
- ✅ `core/static/favicon-16x16.png`
- ✅ `browser-extension/icons/icon-128.png`
- ✅ `browser-extension/icons/icon-48.png`
- ✅ `browser-extension/icons/icon-16.png`
- ✅ `core/static/logo.svg` (optional)
- ✅ `core/static/og-image.png` (optional)

## Brand Guidelines

Refer to `guidelines/` for:
- Color usage (`colors.md`)
- Logo usage rules (`usage.md`)
- Typography (`typography.md`)

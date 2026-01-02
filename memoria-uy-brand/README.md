# memoria.uy Brand Assets

Brand identity and visual assets for memoria.uy - anonymous news sentiment aggregator.

## Logo Preview

The logo is a 4x4 grid pattern representing **memory cells**, symbolizing collective memory and data aggregation.

**Black on White** (Primary):
```
████████████████
████████████░░░░
████░░░░████████
████████████░░░░
```

**White on Black** (Inverse):
```
░░░░░░░░░░░░░░░░
░░░░░░░░░░░░████
░░░░████░░░░░░░░
░░░░░░░░░░░░████
```

*(View actual files in `src/logo/`)*

## Structure

```
memoria-uy-brand/
├── src/               # Source files (editable SVGs)
│   ├── logo/          # Main logo variants
│   └── favicon/       # Favicon source (optional)
├── export/            # Generated PNG/SVG exports
│   ├── png/           # PNG exports (512, 256, 128, 64, 48, 32, 16px)
│   └── svg/           # Optimized SVG copies
├── guidelines/        # Brand usage rules
│   ├── colors.md      # Color palette (B&W)
│   ├── typography.md  # IBM Plex Mono guidelines
│   └── usage.md       # Logo usage rules
├── social/            # Social media assets
│   └── watermark/     # Watermark for screenshots
├── INTEGRATION.md     # How to integrate into project
└── generate-exports.sh # Script to generate PNG exports
```

## Getting Started

1. **Generate exports** (requires ImageMagick):
   ```bash
   ./generate-exports.sh
   ```

2. **See integration guide**:
   ```bash
   cat INTEGRATION.md
   ```

3. **Read brand guidelines**:
   - `guidelines/usage.md` - Logo usage rules
   - `guidelines/colors.md` - Color palette
   - `guidelines/typography.md` - Typography specs

## Quick Usage

### Favicon (Web)
```html
<!-- Add to <head> -->
<link rel="icon" type="image/png" sizes="32x32" href="export/png/black-on-white/favicon/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="export/png/black-on-white/favicon/favicon-16.png">
```

### Browser Extension
Use files in `export/png/black-on-white/extension/`:
- `icon-128.png` - Chrome Web Store listing
- `icon-48.png` - Extension toolbar icon

### Logo Mark
For general use: `export/svg/black-on-white/memoria-uy-mark.svg`

## Brand Guidelines

See `guidelines/` for:
- Color palette (`colors.md`)
- Typography (`typography.md`)
- Usage rules (`usage.md`)

## Design Concept

The logo is a 4x4 grid representing **memory cells** (like RAM) with selective patterns:
- **Geometric brutalism**: Hard edges, monochrome, no gradients
- **Data visualization**: Abstract pattern suggesting collective memory
- **Minimal and functional**: Works at any size, even 16x16px

The missing cells create negative space that hints at the ".uy" domain while maintaining readability at small sizes.

## License

Open source - same license as memoria.uy project.

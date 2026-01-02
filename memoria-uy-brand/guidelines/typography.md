# Typography Guidelines

## Brand Typeface

memoria.uy uses **monospace fonts** exclusively to reinforce the technical, data-driven aesthetic.

## Primary Font: IBM Plex Mono

**IBM Plex Mono** is the preferred typeface for all brand materials.

- **License**: Open Font License (free)
- **Download**: [IBM Plex on Google Fonts](https://fonts.google.com/specimen/IBM+Plex+Mono)
- **Weights to use**:
  - Regular (400) - Body text, UI
  - SemiBold (600) - Emphasis, section headers
  - Bold (700) - Page titles, strong emphasis

### CSS Usage

```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&display=swap');

body {
  font-family: 'IBM Plex Mono', monospace;
  font-weight: 400;
  font-size: 14px;
  line-height: 1.6;
}

h1, h2, h3 {
  font-weight: 700;
}

strong {
  font-weight: 600;
}
```

## Alternative Font: JetBrains Mono

If IBM Plex Mono is unavailable, use **JetBrains Mono** as a fallback.

- **License**: Open Font License (free)
- **Download**: [JetBrains Mono](https://www.jetbrains.com/lp/mono/)
- **Weights**: Regular (400), Bold (700)

## System Fallbacks

```css
font-family: 'IBM Plex Mono', 'JetBrains Mono', 'Courier New', Courier, monospace;
```

## Font Sizing

### Web (Desktop)
- **Body text**: 14px (0.875rem)
- **Small text**: 12px (0.75rem) - Metadata, captions
- **Headers**:
  - H1: 32-40px (2-2.5rem)
  - H2: 24px (1.5rem)
  - H3: 18px (1.125rem)
- **Buttons**: 13px (0.8125rem)

### Web (Mobile)
- **Body text**: 13px
- **Headers**: Scale down 10-20%

### Print
- **Body text**: 9pt minimum
- **Headers**: 14-18pt

## Text Styles

### Code/Terminal Style

Use monospace for all text to create a "code editor" or "terminal" aesthetic:

```
> This is a header with a prompt character
// This is a comment-style annotation
└─ This uses terminal tree characters
```

### Prompt Characters

Use sparingly for visual hierarchy:
- `>` for section headers
- `//` for inline comments/metadata
- `└─` for nested/child items
- `•` for bullet lists

## Letter Spacing

- **Headers**: Normal (0)
- **Body**: Normal (0)
- **Uppercase text**: +0.05em (slight tracking increase)

## Line Height

- **Body text**: 1.6 (24px for 14px font)
- **Headers**: 1.2-1.3
- **Code blocks**: 1.5

## Text Colors

Use monochrome palette (see `colors.md`):
- **Primary text**: `#000000` (black)
- **Secondary text**: `#616161` (gray-700)
- **Muted text**: `#BDBDBD` (gray-400)
- **On dark backgrounds**: `#FFFFFF` (white)

## Emphasis

- **Bold**: Use SemiBold (600) or Bold (700), not italic
- **Inline code**: Wrap in backticks, use `#F5F5F5` background
- **Links**: Underline on hover, no color change needed

## Anti-aliasing

```css
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale;
```

## Don'ts

- ❌ Don't use serif fonts
- ❌ Don't use sans-serif fonts (except system fallbacks)
- ❌ Don't use script/decorative fonts
- ❌ Don't use italic (monospace italics are hard to read)
- ❌ Don't use all-caps for long text (only for labels/buttons)

## Accessibility

- Maintain WCAG AA contrast (4.5:1 minimum)
- Don't go below 12px for body text on web
- Ensure sufficient line height for readability (1.5 minimum)

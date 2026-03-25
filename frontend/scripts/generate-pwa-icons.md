# PWA Icon Generation Guide

The PWA requires multiple icon sizes. Use the base SVG icon at `/public/icons/icon.svg` to generate them.

## Required Icons

### Standard Icons
- `icon-72.png` - 72x72px
- `icon-96.png` - 96x96px
- `icon-128.png` - 128x128px
- `icon-144.png` - 144x144px
- `icon-152.png` - 152x152px (iOS)
- `icon-192.png` - 192x192px (Android)
- `icon-384.png` - 384x384px
- `icon-512.png` - 512x512px (Splash screen)

### Maskable Icons (for Android adaptive icons)
- `icon-maskable-192.png` - 192x192px with safe zone padding
- `icon-maskable-512.png` - 512x512px with safe zone padding

### Shortcut Icons
- `shortcut-chat.png` - 96x96px
- `shortcut-goals.png` - 96x96px
- `shortcut-skills.png` - 96x96px
- `shortcut-ultron.png` - 96x96px

### Badge Icon
- `badge-72.png` - 72x72px (monochrome, for notification badges)

## Generation Methods

### Option 1: Using Sharp (Node.js)
```bash
npm install sharp
node scripts/generate-icons.js
```

### Option 2: Using ImageMagick
```bash
# Convert SVG to various PNG sizes
convert -background none -density 300 icon.svg -resize 72x72 icon-72.png
convert -background none -density 300 icon.svg -resize 96x96 icon-96.png
convert -background none -density 300 icon.svg -resize 128x128 icon-128.png
convert -background none -density 300 icon.svg -resize 144x144 icon-144.png
convert -background none -density 300 icon.svg -resize 152x152 icon-152.png
convert -background none -density 300 icon.svg -resize 192x192 icon-192.png
convert -background none -density 300 icon.svg -resize 384x384 icon-384.png
convert -background none -density 300 icon.svg -resize 512x512 icon-512.png
```

### Option 3: Using Online Tools
- [RealFaviconGenerator](https://realfavicongenerator.net/) - Full PWA icon generation
- [PWA Builder](https://www.pwabuilder.com/imageGenerator) - Microsoft's PWA image generator
- [Maskable.app](https://maskable.app/) - For creating maskable icons

## Maskable Icon Guidelines

For maskable icons, ensure the important content is within the "safe zone":
- The safe zone is a circle in the center with radius = 40% of the total size
- For a 512x512 icon, keep content within the center 204px radius

## iOS Splash Screens

Create splash screens for various iOS device sizes:
- 640x1136 - iPhone 5/SE (1st gen)
- 750x1334 - iPhone 6/7/8/SE (2nd gen)
- 1242x2208 - iPhone 6+/7+/8+
- 1125x2436 - iPhone X/XS/11 Pro
- 1284x2778 - iPhone 12/13/14 Pro Max

Place in `/public/splash/` directory.

## Verification

After generating icons, verify:
1. Icons are not blurry at their target sizes
2. Maskable icons work in adaptive icon preview
3. All paths in manifest.json are correct
4. Icons load in browser dev tools Application tab

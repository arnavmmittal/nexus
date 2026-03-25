#!/usr/bin/env node
/**
 * Generate PWA icons from the base SVG icon.
 * Uses sharp (bundled with Next.js).
 *
 * Usage: node scripts/generate-icons.mjs
 */

import sharp from 'sharp';
import { readFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const iconsDir = join(__dirname, '..', 'public', 'icons');
const splashDir = join(__dirname, '..', 'public', 'splash');
const svgPath = join(iconsDir, 'icon.svg');

// Ensure directories exist
mkdirSync(iconsDir, { recursive: true });
mkdirSync(splashDir, { recursive: true });

const svgBuffer = readFileSync(svgPath);

// Standard icon sizes
const sizes = [72, 96, 128, 144, 152, 192, 384, 512];

// Maskable icon sizes (with padding for safe zone)
const maskableSizes = [192, 512];

// Shortcut icons
const shortcuts = ['chat', 'goals', 'skills', 'ultron'];

async function generateStandardIcons() {
  for (const size of sizes) {
    await sharp(svgBuffer)
      .resize(size, size)
      .png()
      .toFile(join(iconsDir, `icon-${size}.png`));
    console.log(`  ✓ icon-${size}.png`);
  }
}

async function generateMaskableIcons() {
  for (const size of maskableSizes) {
    // Maskable icons need 10% padding on each side (safe zone = 80% center)
    const padding = Math.round(size * 0.1);
    const innerSize = size - padding * 2;

    const inner = await sharp(svgBuffer).resize(innerSize, innerSize).png().toBuffer();

    await sharp({
      create: {
        width: size,
        height: size,
        channels: 4,
        background: { r: 10, g: 10, b: 10, alpha: 1 }, // #0a0a0a
      },
    })
      .composite([{ input: inner, left: padding, top: padding }])
      .png()
      .toFile(join(iconsDir, `icon-maskable-${size}.png`));
    console.log(`  ✓ icon-maskable-${size}.png`);
  }
}

async function generateShortcutIcons() {
  // Simple colored variants for shortcuts
  const colors = {
    chat: '#10b981',    // emerald (Jarvis)
    goals: '#3b82f6',   // blue
    skills: '#8b5cf6',  // violet
    ultron: '#ef4444',  // red (Ultron)
  };

  const labels = {
    chat: 'J',
    goals: 'G',
    skills: 'S',
    ultron: 'U',
  };

  for (const name of shortcuts) {
    const color = colors[name];
    const label = labels[name];

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
      <rect width="96" height="96" rx="20" fill="#0a0a0a"/>
      <circle cx="48" cy="48" r="32" fill="${color}"/>
      <text x="48" y="60" font-family="system-ui" font-size="36" font-weight="bold" fill="#0a0a0a" text-anchor="middle">${label}</text>
    </svg>`;

    await sharp(Buffer.from(svg)).resize(96, 96).png().toFile(join(iconsDir, `shortcut-${name}.png`));
    console.log(`  ✓ shortcut-${name}.png`);
  }
}

async function generateBadgeIcon() {
  // Monochrome badge for notifications
  const badgeSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">
    <circle cx="36" cy="36" r="30" fill="white"/>
    <text x="36" y="48" font-family="system-ui" font-size="40" font-weight="bold" fill="black" text-anchor="middle">N</text>
  </svg>`;

  await sharp(Buffer.from(badgeSvg)).resize(72, 72).png().toFile(join(iconsDir, 'badge-72.png'));
  console.log('  ✓ badge-72.png');
}

async function generateFavicon() {
  // favicon.ico from the SVG
  await sharp(svgBuffer).resize(32, 32).png().toFile(join(iconsDir, 'favicon-32.png'));
  console.log('  ✓ favicon-32.png');
}

async function generateSplashScreens() {
  // iOS splash screens - dark background with centered icon
  const splashSizes = [
    { w: 640, h: 1136, name: 'splash-640x1136.png' },
    { w: 750, h: 1334, name: 'splash-750x1334.png' },
    { w: 1242, h: 2208, name: 'splash-1242x2208.png' },
    { w: 1125, h: 2436, name: 'splash-1125x2436.png' },
    { w: 1284, h: 2778, name: 'splash-1284x2778.png' },
  ];

  for (const { w, h, name } of splashSizes) {
    const iconSize = Math.round(Math.min(w, h) * 0.25);
    const icon = await sharp(svgBuffer).resize(iconSize, iconSize).png().toBuffer();

    await sharp({
      create: {
        width: w,
        height: h,
        channels: 4,
        background: { r: 10, g: 10, b: 10, alpha: 1 },
      },
    })
      .composite([
        {
          input: icon,
          left: Math.round((w - iconSize) / 2),
          top: Math.round((h - iconSize) / 2 - h * 0.05), // Slightly above center
        },
      ])
      .png()
      .toFile(join(splashDir, name));
    console.log(`  ✓ ${name}`);
  }
}

async function main() {
  console.log('Generating PWA icons...\n');

  console.log('Standard icons:');
  await generateStandardIcons();

  console.log('\nMaskable icons:');
  await generateMaskableIcons();

  console.log('\nShortcut icons:');
  await generateShortcutIcons();

  console.log('\nBadge icon:');
  await generateBadgeIcon();

  console.log('\nFavicon:');
  await generateFavicon();

  console.log('\nSplash screens:');
  await generateSplashScreens();

  console.log('\nDone! All icons generated.');
}

main().catch(console.error);

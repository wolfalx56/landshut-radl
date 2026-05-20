#!/bin/bash
# Einfache Platzhalter-Icons generieren (benötigt ImageMagick oder rsvg-convert)
# Einmalig auf dem Server ausführen

cat > /tmp/icon.svg << 'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="100" fill="#2d6a4f"/>
  <text x="256" y="330" font-size="280" text-anchor="middle" font-family="Arial">🚴</text>
</svg>
SVG

if command -v rsvg-convert &> /dev/null; then
  rsvg-convert -w 192 -h 192 /tmp/icon.svg > icon-192.png
  rsvg-convert -w 512 -h 512 /tmp/icon.svg > icon-512.png
elif command -v convert &> /dev/null; then
  convert -background none /tmp/icon.svg -resize 192x192 icon-192.png
  convert -background none /tmp/icon.svg -resize 512x512 icon-512.png
else
  echo "ImageMagick oder librsvg installieren: sudo apt install librsvg2-bin"
fi
echo "Icons generiert."

// SPDX-License-Identifier: GPL-3.0-or-later
// VoidStation klar fuer mGBA: scharfe, gleich grosse Pixel auch bei krummen Vergroesserungen ("sharp bilinear").
// Jeder Spielpixel wird erst ganzzahlig vergroessert gedacht, nur der Rest bis zur Bildschirmgroesse wird weich
// ueberblendet. Bei ganzzahliger Vergroesserung ist das Bild damit gleich dem ohne Shader; mit "Ganzzahlig skalieren: Aus"
// fuellt das Spiel den Bildschirm ohne ungleich breite Pixel und ohne Unschaerfe.
varying vec2 texCoord;
uniform sampler2D tex;
uniform vec2 texSize;

void main() {
	vec2 texel = texCoord * texSize;
	vec2 scale = max(floor(1.0 / max(fwidth(texel), vec2(0.0001))), vec2(1.0));   // ganze Bildschirmpunkte je Spielpixel
	vec2 base = floor(texel);
	vec2 center = texel - base - 0.5;
	vec2 region = 0.5 - 0.5 / scale;
	vec2 f = (center - clamp(center, -region, region)) * scale + 0.5;
	gl_FragColor = texture2D(tex, (base + f) / texSize);
}

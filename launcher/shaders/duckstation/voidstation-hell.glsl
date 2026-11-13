// SPDX-License-Identifier: GPL-3.0-or-later
// VoidStation Farbe – Hell: heller, fuer dunkle Spiele auf dem Fernseher.
//
// Dieselbe Rechnung und dieselben Werte wie "ShadeBoost" von PCSX2 (launcher.py PCSX2_COLORS: Wert / 50), damit die
// Stufe auf PlayStation und PlayStation 2 gleich aussieht. Die Formel stammt aus TGMs Shader-Sammlung (frei verwendbar,
// http://irrlicht.sourceforge.net/phpBB2/viewtopic.php?t=21057), wie sie auch PCSX2 nutzt.
//
// Von VoidStation in den Shader-Ordner von DuckStation gelegt (launcher.py duck_shaders_install).

const float BRIGHTNESS = 1.08;
const float CONTRAST = 1.0;
const float SATURATION = 1.0;
const float GAMMA = 1.1;

void main()
{
  float4 color = Sample();
  float3 brt = color.rgb * BRIGHTNESS;
  float lum = dot(brt, float3(0.2125, 0.7154, 0.0721));
  float3 sat = mix(float3(lum, lum, lum), brt, SATURATION);
  float3 con = mix(float3(0.5, 0.5, 0.5), sat, CONTRAST);
  float3 res = pow(max(con, float3(0.0, 0.0, 0.0)), float3(1.0 / GAMMA, 1.0 / GAMMA, 1.0 / GAMMA));
  SetOutput(float4(clamp(res, 0.0, 1.0), color.a));
}

// SPDX-License-Identifier: GPL-3.0-or-later
// VoidStation klar – Nachbearbeitung fuer DuckStation (Kette "PostProcessing", laeuft in der Aufloesung des Bildschirms).
//
// Schaerft Kanten und Texturen nach, ohne flache Flaechen zu verrauschen und ohne helle Saeume: Die Staerke richtet sich
// je Bildpunkt nach dem Kontrast seiner Umgebung (wie AMD FidelityFX CAS, hier die einfache Form mit fuenf Abtastungen).
// Abgetastet wird im Abstand eines Bildpunkts der Renderaufloesung – bei 2-facher Aufloesung auf einem 1080p-Fernseher also
// gut zwei Bildschirmpunkte –, damit es die Unschaerfe des Hochrechnens trifft und nicht nur einzelne Bildschirmpunkte.
//
// Von VoidStation in den Shader-Ordner von DuckStation gelegt (launcher.py duck_shaders_install); Aenderungen dort
// ueberschreibt das naechste Update.

const float SHARPNESS = 0.6;        // 0 = dezent, 1 = kraeftig

void main()
{
  float2 uv = GetCoordinates();
  float2 px = max(GetInvInternalPixelSize(), GetInvWindowSize());   // nie feiner als ein Bildschirmpunkt
  px = min(px, GetInvWindowSize() * 4.0);

  float4 color = SampleLocation(uv);
  float3 c = color.rgb;
  float3 n = SampleLocation(uv + float2(0.0, -px.y)).rgb;
  float3 s = SampleLocation(uv + float2(0.0, px.y)).rgb;
  float3 w = SampleLocation(uv + float2(-px.x, 0.0)).rgb;
  float3 e = SampleLocation(uv + float2(px.x, 0.0)).rgb;

  float3 mn = min(c, min(min(n, s), min(w, e)));
  float3 mx = max(c, max(max(n, s), max(w, e)));

  // Wie viel Luft bis Schwarz bzw. Weiss bleibt, bestimmt die Staerke: kein Uebersteuern, kaum Wirkung in flachen Flaechen
  float3 amp = sqrt(clamp(min(mn, float3(1.0, 1.0, 1.0) - mx) / max(mx, float3(0.0001, 0.0001, 0.0001)), 0.0, 1.0));
  float3 wgt = amp * (-1.0 / mix(8.0, 5.0, SHARPNESS));
  float3 res = (c + (n + s + w + e) * wgt) / (float3(1.0, 1.0, 1.0) + 4.0 * wgt);

  SetOutput(float4(clamp(res, 0.0, 1.0), color.a));
}

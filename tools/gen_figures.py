#!/usr/bin/env python3
"""
ESCOLIOSE 360° — Gerador das ilustracoes SVG do rastreio visual.

Gera os pares de figuras "Normal" vs "Alterado" dos 4 passos do
rastreio visual (ombros, escapulas, cintura e teste de Adams).

O corpo e desenhado a partir de um unico contorno anatomico (vista
posterior) definido no viewBox 0 0 160 230. Cada variante aplica
deformacoes parametricas sobre esse contorno: inclinacao dos ombros
(tilt), desvio lateral do tronco (shift) e indentacao assimetrica da
cintura (waist_indent). As ancoras used nas anotacoes (ombros,
cintura, escapulas) sao deformadas junto com o corpo, de modo que as
marcacoes acompanham a geometria redesenhada.

Uso:
    python3 tools/gen_figures.py            # reescreve os blocos do index.html
    python3 tools/gen_figures.py --check    # apenas verifica se esta em dia
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

VIEWBOX = "0 0 160 230"
GROUND_Y = 219
CENTER_X = 80.0

# Marcadores por figura no index.html.
MARKER = "<!-- FIGURAS:{key}:INICIO -->{content}<!-- FIGURAS:{key}:FIM -->"


# ============================================================
# Utilitarios geometricos
# ============================================================

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def f(value: float) -> str:
    """Formata numero para SVG sem ruido de ponto flutuante."""
    rounded = round(value, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def mirror_point(point):
    return (2 * CENTER_X - point[0], point[1])


def mirror_segments(segments):
    out = []
    for kind, data in segments:
        if kind in ("M", "L"):
            out.append((kind, mirror_point(data)))
        else:
            c1, c2, end = data
            out.append(("C", [mirror_point(c1), mirror_point(c2), mirror_point(end)]))
    return out


def reverse_segments(segments):
    """Inverte a ordem da cadeia; o 'M' inicial vira 'L' de fechamento."""
    out = []
    for kind, data in reversed(segments):
        if kind in ("M", "L"):
            out.append(("L", data))
        else:
            c1, c2, end = data
            out.append(("C", [end, c2, c1]))
    return out


# ============================================================
# Contorno anatomico — vista posterior, em pe
# ============================================================
# Cadeia do lado DIREITO (x > 80) do corpo, do topo da cabeca ate o
# pubis. O lado esquerdo e obtido por espelhamento.
BODY_CHAIN = [
    ("M", (80, 7)),
    ("C", [(91, 7), (99, 15), (99, 24)]),          # craneio
    ("C", [(99, 33), (92, 41), (88, 41)]),          # mandibula
    ("L", (88, 50)),                                # pescoco
    ("C", [(101, 53), (112, 58), (116, 66)]),       # trapezio / ombro
    ("C", [(118, 73), (113, 80), (110, 88)]),       # axila
    ("C", [(112, 99), (110, 112), (107, 122)]),     # flanco
    ("C", [(105, 131), (107, 139), (111, 146)]),    # cintura -> quadril
    ("C", [(114, 150), (116, 155), (116, 162)]),   # quadril
    ("L", (117, 200)),                              # coxa externa
    ("C", [(117, 210), (114, 215), (108, 215)]),    # tornozelo
    ("L", (101, 215)),                              # pe
    ("C", [(98, 215), (97, 211), (97, 206)]),
    ("L", (96, 180)),                               # perna interna
    ("C", [(96, 168), (90, 160), (85, 157)]),
    ("L", (80, 155)),                               # pubis
]

# Ancoras (lado direito) usadas nas anotacoes e marcadores.
ANCHORS = {
    "ombro": (110, 57),
    "cintura": (107, 124),
    "escapula": (64, 84),
    "quadril": (114, 152),
    "pescoco": (88, 47),
}


# ============================================================
# Deformacoes parametricas
# ============================================================

def deform(point, tilt_deg=0.0, shift=0.0, waist_indent=0.0):
    """Aplica inclinacao dos ombros, desvio do tronco e indentacao da cintura."""
    x, y = point

    # 1. Rotacao do hemi-corpo superior (ombros fora de nivel).
    if tilt_deg:
        blend = (clamp((115.0 - y) / 45.0, 0.0, 1.0)
                 * clamp((y - 26.0) / 24.0, 0.0, 1.0))
        ang = math.radians(tilt_deg * blend)
        dx, dy = x - CENTER_X, y - 100.0
        x = CENTER_X + dx * math.cos(ang) - dy * math.sin(ang)
        y = 100.0 + dx * math.sin(ang) + dy * math.cos(ang)

    # 2. Desvio lateral do tronco em relacao a bacia.
    if shift:
        weight = math.exp(-(((y - 92.0) / 40.0) ** 2))
        x += shift * weight

    # 3. Indentacao assimetrica da cintura (triangulo de talhe).
    if waist_indent:
        weight = math.exp(-(((y - 124.0) / 24.0) ** 2))
        side = 1.0 if x > CENTER_X else -1.0
        x += waist_indent * weight * side

    return (x, y)


def apply_deform(segments, **cfg):
    out = []
    for kind, data in segments:
        if kind in ("M", "L"):
            out.append((kind, deform(data, **cfg)))
        else:
            out.append((kind, [deform(p, **cfg) for p in data]))
    return out


def segments_to_path(segments, close=True):
    d = []
    current = None
    for kind, data in segments:
        if kind == "M":
            current = data
            d.append(f"M {f(data[0])} {f(data[1])}")
        elif kind == "L":
            current = data
            d.append(f"L {f(data[0])} {f(data[1])}")
        else:
            c1, c2, end = data
            current = end
            d.append(
                f"C {f(c1[0])} {f(c1[1])}, {f(c2[0])} {f(c2[1])}, "
                f"{f(end[0])} {f(end[1])}"
            )
    if close:
        d.append("Z")
    return " ".join(d)


def build_body(cfg):
    """Retorna (caminho do corpo, ancoras deformadas)."""
    right = apply_deform(BODY_CHAIN, **cfg)
    left = reverse_segments(mirror_segments(right))
    left = left[1:]  # remove a repeticao do pubis espelhado

    anchors = {}
    for name, pt in ANCHORS.items():
        anchors[name] = deform(pt, **cfg)
        anchors[name + "_esq"] = deform(mirror_point(pt), **cfg)
    return segments_to_path(right + left), anchors


def arm_segments(side="right"):
    """Braco colgando, como cadeia de curvas."""
    if side == "right":
        return [
            ("M", (114, 68)),
            ("C", [(122, 88), (124, 112), (120, 138)]),
        ]
    return [
        ("M", (46, 68)),
        ("C", [(38, 88), (36, 112), (40, 138)]),
    ]


def spine_path(cfg, amp=0.0, kind="S", top=50.0, bottom=154.0):
    """Linha da coluna, com curva em S (ou C) e desvio lateral do tronco."""
    steps = 9
    pts = []
    for i in range(steps + 1):
        t = i / steps
        y = top + (bottom - top) * t
        if kind == "S":
            dx = amp * math.sin(2 * math.pi * t)
        else:
            dx = amp * math.sin(math.pi * t)
        x = CENTER_X + dx
        weight = math.exp(-(((y - 92.0) / 40.0) ** 2))
        x += cfg.get("shift", 0.0) * weight
        pts.append((x, y))

    d = f"M {f(pts[0][0])} {f(pts[0][1])}"
    for i in range(1, len(pts)):
        prev, cur = pts[i - 1], pts[i]
        cx = (prev[0] + cur[0]) / 2
        d += (f" C {f(cx)} {f(prev[1])}, {f(cx)} {f(cur[1])}, "
              f"{f(cur[0])} {f(cur[1])}")
    return d


def scapula_path(cfg, side="right", scale=1.0, out=0.0, down=0.0):
    """Escapula (triangulo) em vista posterior."""
    if side == "right":
        base = [(58, 71), (74, 76), (66, 97)]
    else:
        base = [(102, 71), (86, 76), (94, 97)]
    cx = sum(p[0] for p in base) / 3
    cy = sum(p[1] for p in base) / 3
    pts = []
    for (x, y) in base:
        nx = cx + (x - cx) * scale + (out if side == "right" else -out)
        ny = cy + (y - cy) * scale + down
        pts.append(deform((nx, ny), **cfg))
    return "M " + " L ".join(f"{f(x)} {f(y)}" for (x, y) in pts) + " Z"


# ============================================================
# Blocos SVG
# ============================================================

def indent(text, spaces):
    """Reindenta um bloco de linhas SVG."""
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line
                      for line in text.splitlines())


def svg_open(label, desc, classes="illustration", viewbox=None):
    return (
        f'<svg class="{classes}" viewBox="{viewbox or VIEWBOX}" role="img" '
        f'aria-label="{label}">\n'
        f"<title>{label}</title>\n"
        f"<desc>{desc}</desc>\n"
    )


def ground():
    return (f'<g class="fig-ground">\n'
            f'<line x1="16" y1="{GROUND_Y}" x2="144" y2="{GROUND_Y}"/>\n'
            f"</g>\n")


def body(d):
    return f'<path class="fig-body" d="{d}"/>\n'


def limbs(cfg):
    right = apply_deform(arm_segments("right"), **cfg)
    left = apply_deform(arm_segments("left"), **cfg)
    return (f'<g class="fig-limb">\n'
            f'<path d="{segments_to_path(right, close=False)}"/>\n'
            f'<path d="{segments_to_path(left, close=False)}"/>\n'
            f"</g>\n")


def text(x, y, content, cls="fig-text", anchor="middle"):
    return (f'<text class="{cls}" x="{f(x)}" y="{f(y)}" '
            f'text-anchor="{anchor}">{content}</text>\n')


def circle(x, y, r, cls="fig-marker"):
    return f'<circle class="{cls}" cx="{f(x)}" cy="{f(y)}" r="{r}"/>\n'


def line(x1, y1, x2, y2, cls="fig-guide"):
    return (f'<line class="{cls}" x1="{f(x1)}" y1="{f(y1)}" '
            f'x2="{f(x2)}" y2="{f(y2)}"/>\n')


def path_el(d, cls):
    return f'<path class="{cls}" d="{d}"/>\n'


# ============================================================
# Figuras por passo
# ============================================================

def fig_ombros(altered):
    label = ("Ombros em niveis diferentes — vista posterior" if altered
             else "Ombros alinhados — vista posterior")
    desc = ("Silhueta vista de costas com um ombro mais alto que o outro, "
            "marcado por linha de referencia tracejada." if altered else
            "Silhueta vista de costas com os dois ombros na mesma altura, "
            "marcados por linha de referencia tracejada.")

    cfg = {"tilt_deg": -9.0, "shift": 0.0, "waist_indent": 0.0} if altered else \
          {"tilt_deg": 0.0, "shift": 0.0, "waist_indent": 0.0}
    body_d, anchors = build_body(cfg)
    ombro_d, ombro_e = anchors["ombro"], anchors["ombro_esq"]
    ref_y = max(ombro_d[1], ombro_e[1]) if altered else (ombro_d[1] + ombro_e[1]) / 2

    out = [svg_open(label, desc, "illustration illustration--ombros")]
    out.append(ground())
    out.append(body(body_d))
    out.append(limbs(cfg))
    out.append(line(28, ref_y, 132, ref_y, "fig-guide"))

    if altered:
        out.append(circle(ombro_d[0], ombro_d[1], 5.5, "fig-marker fig-marker--alert"))
        out.append(circle(ombro_e[0], ombro_e[1], 5.5, "fig-marker"))
        out.append(text(ombro_d[0], ombro_d[1] - 13, "ombro alto",
                        "fig-text fig-text--alert"))
        out.append(text(ombro_e[0], ombro_e[1] + 16, "ombro baixo", "fig-text"))
        # Cotacao do desnivel entre os dois ombros.
        mid_x = 80.0
        out.append(line(mid_x, ombro_d[1], mid_x, ombro_e[1], "fig-measure"))
        out.append(line(mid_x - 4, ombro_d[1], mid_x + 4, ombro_d[1], "fig-measure"))
        out.append(line(mid_x - 4, ombro_e[1], mid_x + 4, ombro_e[1], "fig-measure"))
    else:
        out.append(circle(ombro_d[0], ombro_d[1], 5.5, "fig-marker"))
        out.append(circle(ombro_e[0], ombro_e[1], 5.5, "fig-marker"))
        out.append(text(CENTER_X, 44, "ombros nivelados", "fig-text"))

    out.append(path_el(spine_path(cfg, amp=3.0 if altered else 0.0, kind="C"), "fig-spine"))
    out.append("</svg>\n")
    return "".join(out)


def fig_escapulas(altered):
    label = ("Escapula saliente de um lado — vista posterior" if altered
             else "Escapulas simetricas — vista posterior")
    desc = ("Uma das escapulas aparece mais saliente e mais alta que a outra." if altered
            else "As duas escapulas aparecem na mesma altura e com a mesma projecao.")

    cfg = {"tilt_deg": -4.0, "shift": 2.5, "waist_indent": 0.0} if altered else \
          {"tilt_deg": 0.0, "shift": 0.0, "waist_indent": 0.0}
    body_d, anchors = build_body(cfg)

    out = [svg_open(label, desc, "illustration illustration--escapulas")]
    out.append(ground())
    out.append(body(body_d))
    out.append(limbs(cfg))

    if altered:
        out.append(path_el(scapula_path(cfg, "right"), "fig-scapula"))
        out.append(path_el(scapula_path(cfg, "left", scale=1.35, out=6.0, down=-5.0),
                           "fig-scapula fig-scapula--alert"))
        esc = deform((96, 82), **cfg)
        out.append(circle(esc[0], esc[1], 5.0, "fig-marker fig-marker--alert"))
        out.append(text(112, esc[1] - 14, "escápula", "fig-text fig-text--alert", "start"))
        out.append(text(112, esc[1] - 3, "saliente", "fig-text fig-text--alert", "start"))
        out.append(path_el(spine_path(cfg, amp=4.0, kind="C"), "fig-spine"))
    else:
        out.append(path_el(scapula_path(cfg, "right"), "fig-scapula"))
        out.append(path_el(scapula_path(cfg, "left"), "fig-scapula"))
        out.append(text(CENTER_X, 44, "escápulas simétricas", "fig-text"))
        out.append(path_el(spine_path(cfg, amp=0.0), "fig-spine"))

    out.append("</svg>\n")
    return "".join(out)


def fig_cintura(altered):
    label = ("Cintura assimetrica — vista posterior" if altered
             else "Cintura simetrica — vista posterior")
    desc = ("O vao entre o braco e a cintura e mais fundo de um lado, formando um triangulo." if altered
            else "O vao entre o braco e a cintura tem a mesma profundidade dos dois lados.")

    cfg = {"tilt_deg": -3.0, "shift": 3.0, "waist_indent": 9.0} if altered else \
          {"tilt_deg": 0.0, "shift": 0.0, "waist_indent": 0.0}
    body_d, anchors = build_body(cfg)
    cint_d, cint_e = anchors["cintura"], anchors["cintura_esq"]

    out = [svg_open(label, desc, "illustration illustration--cintura")]
    out.append(ground())
    out.append(body(body_d))
    out.append(limbs(cfg))
    out.append(line(cint_e[0] - 8, cint_d[1], cint_d[0] + 10, cint_d[1], "fig-guide"))

    if altered:
        # Triangulo de talhe no lado direito (do observador).
        out.append(path_el(f"M {f(cint_d[0] + 12)} {f(cint_d[1] - 18)} "
                           f"L {f(cint_d[0] + 2)} {f(cint_d[1])} "
                           f"L {f(cint_d[0] + 12)} {f(cint_d[1] + 18)}",
                           "fig-triangle"))
        out.append(text(cint_d[0] - 14, cint_d[1] - 2, "triângulo", "fig-text fig-text--alert", "end"))
        out.append(text(cint_d[0] - 14, cint_d[1] + 8, "de talhe", "fig-text fig-text--alert", "end"))
        out.append(path_el(spine_path(cfg, amp=5.0, kind="S"), "fig-spine"))
    else:
        out.append(path_el(spine_path(cfg, amp=0.0), "fig-spine"))
        out.append(text(CENTER_X, 44, "cintura simétrica", "fig-text"))

    out.append("</svg>\n")
    return "".join(out)


def fig_adams(altered):
    """Teste de Adams — tronco fletido para frente (vista posterior das costas)."""
    label = ("Elevacao (gibosidade) de um lado no teste de Adams" if altered
             else "Costas simetricas no teste de Adams")
    desc = ("Com o tronco fletido para frente, um dos lados das costas se eleva formando uma giba." if altered
            else "Com o tronco fletido para frente, os dois lados das costas ficam na mesma altura.")

    hip_y = 186.0
    h_left = 72.0 if altered else 78.0
    h_right = 78.0
    hump = 16.0 if altered else 0.0

    def smoothstep(t):
        t = clamp(t, 0.0, 1.0)
        return t * t * (3 - 2 * t)

    def top_y(x):
        blend = smoothstep((x - 66.0) / 26.0)
        height = h_left * (1 - blend) + h_right * blend
        y = hip_y - height * math.exp(-(((x - 80.0) / 58.0) ** 2))
        if hump:
            gate = smoothstep((x - 78.0) / 14.0)
            y -= hump * gate * math.exp(-(((x - 104.0) / 24.0) ** 2))
        return y

    # Contorno superior do dorso (domo), amostrado e suavizado.
    samples = []
    for i in range(17):
        x = 20.0 + (140.0 - 20.0) * i / 16
        samples.append((x, top_y(x)))

    d = f"M {f(samples[0][0])} {f(samples[0][1])}"
    for i in range(1, len(samples)):
        prev, cur = samples[i - 1], samples[i]
        cx = (prev[0] + cur[0]) / 2
        d += f" C {f(cx)} {f(prev[1])}, {f(cx)} {f(cur[1])}, {f(cur[0])} {f(cur[1])}"
    d += f" C 138 168, 132 178, 126 186 L 34 186 C 28 178, 22 168, {f(samples[0][0])} {f(samples[0][1])} Z"

    # Linha da coluna (goteira central do dorso).
    spine_pts = []
    for i in range(13):
        t = i / 12
        y = 108 + (hip_y - 12 - 108) * t
        x = 80.0 + (4.0 if altered else 0.0) * math.sin(math.pi * t)
        spine_pts.append((x, y))
    spine_d = "M " + " L ".join(f"{f(x)} {f(y)}" for (x, y) in spine_pts)

    # Picos de cada lado do dorso.
    left_peak_y = min(top_y(x) for x in (20 + 60 * i / 40 for i in range(41)))
    right_peak_y = min(top_y(x) for x in (80 + 60 * i / 40 for i in range(41)))

    out = [svg_open(label, desc, "illustration illustration--adams",
                    viewbox="0 84 160 142")]
    out.append(ground())

    # Pernas (traçosGrossos) e pes.
    out.append('<g class="fig-limb">\n'
               '<path d="M 50 178 C 46 190 43 202 42 210"/>\n'
               '<path d="M 110 178 C 114 190 117 202 118 210"/>\n'
               '</g>\n')
    out.append(path_el("M 34 210 L 50 208 L 51 215 L 35 215 Z", "fig-body fig-limb-solid"))
    out.append(path_el("M 110 208 L 126 210 L 125 215 L 109 215 Z", "fig-body fig-limb-solid"))

    # Dorso.
    out.append(f'<path class="fig-body" d="{d}"/>\n')
    out.append(f'<path class="fig-spine" d="{spine_d}"/>\n')

    if altered:
        # Linha de referencia na altura do lado mais baixo (esquerdo).
        out.append(line(18, left_peak_y, 142, left_peak_y, "fig-guide"))
        # Ponto mais elevado do lado direito.
        bx = max((x for x in (80 + 60 * i / 60 for i in range(61))),
                 key=lambda x: left_peak_y - top_y(x))
        by = top_y(bx)
        out.append(circle(bx, by, 6.0, "fig-marker fig-marker--alert"))
        out.append(text(bx + 4, by - 10, "gibosidade", "fig-text fig-text--alert"))
        out.append(text(16, 100, "assimetria", "fig-text fig-text--alert", "start"))
    else:
        out.append(line(18, left_peak_y, 142, left_peak_y, "fig-guide"))
        out.append(text(80, 98, "costas simétricas", "fig-text"))

    out.append("</svg>\n")
    return "".join(out)


# ============================================================
# Montagem dos blocos
# ============================================================

FIGURES = {
    "ombros": (fig_ombros, "Ombros nivelados", "Ombro mais alto"),
    "escapulas": (fig_escapulas, "Escápulas simétricas", "Escápula saliente"),
    "cintura": (fig_cintura, "Cintura simétrica", "Cintura assimétrica"),
    "adams": (fig_adams, "Costas simétricas", "Giba dorsal"),
}

FIG_PANEL = """            <figure class="figure-panel">
              <div class="figure-canvas">
{svg}
              </div>
              <figcaption class="figure-cap">{cap}</figcaption>
            </figure>
"""

FIG_PANEL_ALERT = """            <figure class="figure-panel figure-panel--alert">
              <div class="figure-canvas">
{svg}
              </div>
              <figcaption class="figure-cap">{cap}</figcaption>
            </figure>
"""


def build_block(key):
    fn, normal_cap, alert_cap = FIGURES[key]
    normal = FIG_PANEL.format(svg=indent(fn(False), 16), cap=normal_cap)
    alert = FIG_PANEL_ALERT.format(svg=indent(fn(True), 16), cap=alert_cap)
    return normal + alert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="apenas verifica se o index.html esta atualizado")
    args = parser.parse_args()

    html = INDEX.read_text(encoding="utf-8")
    original = html

    for key in FIGURES:
        block = build_block(key)
        pattern = re.compile(
            re.escape(f"<!-- FIGURAS:{key}:INICIO -->")
            + r".*?"
            + re.escape(f"<!-- FIGURAS:{key}:FIM -->"), re.S)
        if not pattern.search(html):
            print(f"ERRO: marcadores da figura '{key}' nao encontrados no index.html",
                  file=sys.stderr)
            return 1
        html = pattern.sub(
            lambda _m, _b=block: (
                f"<!-- FIGURAS:{key}:INICIO -->\n"
                + _b
                + f"            <!-- FIGURAS:{key}:FIM -->"), html)

    if args.check:
        if html != original:
            print("DESATUALIZADO: rode `python3 tools/gen_figures.py`", file=sys.stderr)
            return 1
        print("OK: as figuras estao atualizadas no index.html")
        return 0

    INDEX.write_text(html, encoding="utf-8")
    print(f"OK: {len(FIGURES) * 2} figuras geradas em {INDEX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

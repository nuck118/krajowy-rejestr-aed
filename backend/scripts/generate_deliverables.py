import base64
import io
import shutil
import sys
from collections import deque
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.standard_xlsx import (  # noqa: E402
    SOURCE_SCOPE_MATRIX,
    STANDARD_FIELDS_SPEC,
    generate_standard_xlsx_bytes,
)

DELIV_DIR = ROOT_DIR / "deliverables"
ASSETS_DIR = DELIV_DIR / "assets"
SCREENSHOTS_DIR = ASSETS_DIR / "screenshots"
LOGO_DIR = DELIV_DIR / "logotyp"
PUBLIC_DELIV_DIR = ROOT_DIR / "frontend" / "public" / "deliverables"

LOGO_SOURCE_PATH = ASSETS_DIR / "logo_final.jpg"

FONT_REG_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_ITALIC_PATH = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"
FONT_BLACK_PATH = "/System/Library/Fonts/Supplemental/Arial Black.ttf"

# Exact palette aligned with the final logo + official gov.pl design language
NAVY = "#152B45"
CRIMSON = "#D9173B"
GOV_BLUE = "#0052A5"
GOV_BLUE_LIGHT = "#EDF4FB"
EMERALD = "#047857"
AMBER = "#92400E"
INK = "#1B1B1B"
MUTED = "#595959"
SURFACE = "#F1F4F8"
BORDER = "#CBD5E1"
WHITE = "#FFFFFF"


def get_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = FONT_REG_PATH
    if weight == "bold":
        path = FONT_BOLD_PATH
    elif weight == "italic":
        path = FONT_ITALIC_PATH
    elif weight == "black":
        path = FONT_BLACK_PATH
    return ImageFont.truetype(path, size)


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    fill: str = INK,
    line_spacing: int = 8,
) -> int:
    lines = wrap_text(draw, text, font, max_width)
    cur_y = y
    for line in lines:
        draw.text((x, cur_y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        cur_y += (bbox[3] - bbox[1]) + line_spacing
    return cur_y


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: str = INK,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((cx - w // 2, y), text, font=font, fill=fill)
    return y + h


def prepare_clean_logo_rgba(src_path: Path) -> Image.Image:
    """
    Loads the final user-provided logo, removes only the outer white background via
    4-corner BFS flood fill (keeping interior white shield/flag/lightning opaque),
    and trims with clean 6% padding.
    """
    im = Image.open(src_path).convert("RGBA")
    w, h = im.size
    pix = im.load()

    visited = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()

    def is_bg(r: int, g: int, b: int) -> bool:
        return r >= 242 and g >= 242 and b >= 242

    for sx, sy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        r, g, b, _ = pix[sx, sy]
        if is_bg(r, g, b):
            visited[sy * w + sx] = 1
            queue.append((sx, sy))

    while queue:
        x, y = queue.popleft()
        pix[x, y] = (255, 255, 255, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                idx = ny * w + nx
                if not visited[idx]:
                    r, g, b, _ = pix[nx, ny]
                    if is_bg(r, g, b):
                        visited[idx] = 1
                        queue.append((nx, ny))

    # Trim to non-transparent bounding box with clean margin
    bbox = im.getbbox()
    if bbox:
        cropped = im.crop(bbox)
    else:
        cropped = im

    cw, ch = cropped.size
    pad = int(max(cw, ch) * 0.08)
    canvas = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (255, 255, 255, 0))
    canvas.paste(cropped, (pad, pad), cropped)
    return canvas


def paste_contain(
    canvas: Image.Image,
    img: Image.Image,
    box: tuple[int, int, int, int],
    *,
    border_color: str | None = None,
    border_width: int = 2,
    bg_color: str | None = None,
) -> tuple[int, int, int, int]:
    """Fit img proportionally inside box=(x0, y0, x1, y1) and paste centered."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    iw, ih = img.size
    scale = min(bw / iw, bh / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    px = x0 + (bw - nw) // 2
    py = y0 + (bh - nh) // 2

    if bg_color:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([px, py, px + nw, py + nh], fill=bg_color)

    if resized.mode == "RGBA":
        canvas.paste(resized, (px, py), resized)
    else:
        canvas.paste(resized, (px, py))

    if border_color:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            [px - 1, py - 1, px + nw + 1, py + nh + 1],
            outline=border_color,
            width=border_width,
        )
    return (px, py, px + nw, py + nh)


def export_logotypes(logo_rgba: Image.Image) -> None:
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DELIV_DIR.mkdir(parents=True, exist_ok=True)

    # 1. PNG (transparent outer bg, high-res)
    png_path = LOGO_DIR / "logotyp_misja_aed.png"
    logo_rgba.save(png_path, format="PNG", optimize=True)

    # 2. JPG (pure white bg, high-res)
    jpg_canvas = Image.new("RGB", logo_rgba.size, WHITE)
    jpg_canvas.paste(logo_rgba, (0, 0), logo_rgba)
    jpg_path = LOGO_DIR / "logotyp_misja_aed.jpg"
    jpg_canvas.save(jpg_path, format="JPEG", quality=96, subsampling=0)

    # 3. PDF (single-page crisp print PDF)
    pdf_path = LOGO_DIR / "logotyp_misja_aed.pdf"
    jpg_canvas.save(pdf_path, format="PDF", resolution=300.0)

    # 4. SVG (clean lossless wrapper embedding the transparent PNG)
    buf = io.BytesIO()
    logo_rgba.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    lw, lh = logo_rgba.size
    svg_content = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lw} {lh}" '
        f'width="{lw}" height="{lh}" role="img" '
        f'aria-label="Logotyp Krajowy Rejestr AED - Misja AED">\n'
        f'  <title>Krajowy Rejestr AED - Ogólnopolska Baza Defibrylatorów</title>\n'
        f'  <image href="data:image/png;base64,{b64}" width="{lw}" height="{lh}" />\n'
        f'</svg>\n'
    )
    svg_path = LOGO_DIR / "logotyp_misja_aed.svg"
    svg_path.write_text(svg_content, encoding="utf-8")

    # Mirror to frontend/public/deliverables/
    for ext in ("png", "jpg", "pdf", "svg"):
        shutil.copy2(LOGO_DIR / f"logotyp_misja_aed.{ext}", PUBLIC_DELIV_DIR / f"logotyp_misja_aed.{ext}")


def _booklet_header_footer(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    page_num: int,
    total_pages: int,
    section_title: str,
) -> None:
    # Top institutional rule
    draw.rectangle([0, 0, w, 12], fill=NAVY)
    draw.rectangle([0, 12, w, 18], fill=CRIMSON)
    draw.text((72, 40), "KSIĘGA ZNAKU  |  KRAJOWY REJESTR AED  |  MISJA AED", font=get_font(17, "bold"), fill=NAVY)
    sec_font = get_font(16, "regular")
    sb = draw.textbbox((0, 0), section_title, font=sec_font)
    draw.text((w - 72 - (sb[2] - sb[0]), 40), section_title, font=sec_font, fill=MUTED)
    draw.line([(72, 74), (w - 72, 74)], fill=BORDER, width=2)

    # Bottom footer
    draw.line([(72, h - 76), (w - 72, h - 76)], fill=BORDER, width=2)
    draw.text(
        (72, h - 58),
        "Kampania „Impuls dla Danych”  |  Portal otwartych danych dane.gov.pl  |  Licencja CC0-1.0",
        font=get_font(15, "regular"),
        fill=MUTED,
    )
    pg_txt = f"Strona {page_num} / {total_pages}"
    pf = get_font(15, "bold")
    pb = draw.textbbox((0, 0), pg_txt, font=pf)
    draw.text((w - 72 - (pb[2] - pb[0]), h - 58), pg_txt, font=pf, fill=NAVY)


def build_portrait_brand_book(logo_rgba: Image.Image) -> None:
    """Builds a print-ready 4-page A4 Portrait Brand Book (1240 x 1754 px @ 150 DPI)."""
    W, H = 1240, 1754
    pages: list[Image.Image] = []

    # ------------------------------------------------------------------
    # PAGE 1: COVER & LOGO CONCEPT (A4 PORTRAIT)
    # ------------------------------------------------------------------
    p1 = Image.new("RGB", (W, H), WHITE)
    d1 = ImageDraw.Draw(p1)

    # Editorial Navy Hero Band
    d1.rectangle([0, 0, W, 240], fill=NAVY)
    d1.rectangle([0, 240, W, 250], fill=CRIMSON)
    d1.text((80, 56), "MINISTERSTWO CYFRYZACJI  |  DANE.GOV.PL  |  MISJA AED", font=get_font(20, "bold"), fill="#B9D2EE")
    d1.text((80, 100), "KSIĘGA ZNAKU", font=get_font(62, "black"), fill=WHITE)
    d1.text((80, 180), "System identyfikacji wizualnej kampanii „Impuls dla Danych”", font=get_font(24, "regular"), fill="#E2E8F0")

    # Central Logo Showcase Card
    d1.rounded_rectangle([80, 300, W - 80, 950], radius=8, fill=WHITE, outline=BORDER, width=2)
    paste_contain(p1, logo_rgba, (220, 330, W - 220, 920))

    # Campaign Name & Slogan Callout
    d1.rounded_rectangle([80, 990, W - 80, 1185], radius=8, fill=GOV_BLUE_LIGHT, outline=GOV_BLUE, width=2)
    d1.rectangle([80, 990, 94, 1185], fill=CRIMSON)
    d1.text((120, 1014), "NAZWA AKCJI PROMOCYJNEJ I HASŁO PRZEWODNIE", font=get_font(17, "bold"), fill=GOV_BLUE)
    d1.text((120, 1048), "IMPULS DLA DANYCH — Misja AED", font=get_font(30, "black"), fill=NAVY)
    draw_wrapped_text(
        d1,
        "„Zamknięta wiedza nie ratuje życia. Otwórz dane o swoim AED w portalu dane.gov.pl.”",
        120,
        1098,
        get_font(24, "italic"),
        W - 240,
        fill=INK,
        line_spacing=8,
    )

    # 4-Sentence Logo Concept Description
    d1.text((80, 1230), "KONCEPCJA ZNAKU (OPIS OFICJALNY — 4 ZDANIA)", font=get_font(20, "bold"), fill=NAVY)
    d1.line([(80, 1262), (W - 80, 1262)], fill=CRIMSON, width=3)
    concept = (
        "1. Znak łączy heraldyczną tarczę bezpieczeństwa publicznego i znacznik lokalizacji (pinezkę GPS) "
        "z międzynarodowym symbolem defibrylatora AED (serce z impulsem elektrycznym na tle krzyża medycznego). "
        "2. Biało-czerwona wstęga spina sygnet z tożsamością państwową Rzeczypospolitej Polskiej oraz systemem "
        "Państwowego Ratownictwa Medycznego i portalu dane.gov.pl. "
        "3. Zestawienie głębokiego granatu państwowego (#152B45) z narodowym karmazynem (#D9173B) zapewnia "
        "natychmiastową rozpoznawalność w sytuacji zagrożenia życia i pełną czytelność zgodnie z WCAG 2.1 AA. "
        "4. Zwarta, symetryczna konstrukcja sprawdza się zarówno jako oznakowanie fizycznych kapsuł AED, "
        "jak i w interfejsach mobilnych, webowych oraz materiałach promocyjnych kierowanych do dysponentów danych."
    )
    draw_wrapped_text(d1, concept, 80, 1284, get_font(21, "regular"), W - 160, fill=INK, line_spacing=11)

    # Bottom metadata bar on cover
    d1.line([(80, H - 80), (W - 80, H - 80)], fill=BORDER, width=2)
    d1.text((80, H - 58), "Wersja 2.0 (Format A4 Pionowy)  |  Formaty plików: .SVG, .PNG, .JPG, .PDF", font=get_font(16, "regular"), fill=MUTED)
    d1.text((W - 220, H - 58), "Strona 1 / 4", font=get_font(16, "bold"), fill=NAVY)
    pages.append(p1)

    # ------------------------------------------------------------------
    # PAGE 2: CLEAR SPACE, CONSTRUCTION & VARIANTS (A4 PORTRAIT)
    # ------------------------------------------------------------------
    p2 = Image.new("RGB", (W, H), WHITE)
    d2 = ImageDraw.Draw(p2)
    _booklet_header_footer(d2, W, H, 2, 4, "Konstrukcja, pole ochronne i warianty")

    d2.text((72, 104), "1. Pole ochronne i budowa znaku (Moduł X)", font=get_font(30, "bold"), fill=NAVY)
    draw_wrapped_text(
        d2,
        "Minimalne pole ochronne wokół logotypu wyznacza moduł X równy 1/6 szerokości tarczy sygnetu. "
        "W wyznaczonej strefie buforowej nie wolno umieszczać żadnych tekstów, linii, ikon ani krawędzi formatu.",
        72,
        150,
        get_font(19, "regular"),
        W - 144,
        fill=MUTED,
        line_spacing=6,
    )

    # Blueprint construction box
    bx0, by0, bx1, by1 = 160, 240, W - 160, 820
    d2.rectangle([bx0, by0, bx1, by1], fill="#F8FAFC", outline=BORDER, width=2)
    # Outer clear-space dashed-feel frame
    pad_x, pad_y = 74, 58
    d2.rectangle([bx0 + pad_x, by0 + pad_y, bx1 - pad_x, by1 - pad_y], outline=GOV_BLUE, width=2)
    d2.rectangle([bx0 + pad_x - 36, by0 + pad_y - 36, bx1 - pad_x + 36, by1 - pad_y + 36], outline="#93C5FD", width=2)
    paste_contain(p2, logo_rgba, (bx0 + pad_x + 14, by0 + pad_y + 14, bx1 - pad_x - 14, by1 - pad_y - 14))

    # X dimension badges on 4 sides
    x_font = get_font(18, "bold")
    for lx, ly in (
        ((bx0 + bx1) // 2 - 10, by0 + 12),
        ((bx0 + bx1) // 2 - 10, by1 - 36),
        (bx0 + 18, (by0 + by1) // 2 - 12),
        (bx1 - 38, (by0 + by1) // 2 - 12),
    ):
        d2.rounded_rectangle([lx - 10, ly - 4, lx + 28, ly + 26], radius=4, fill=GOV_BLUE)
        d2.text((lx + 2, ly), "X", font=x_font, fill=WHITE)

    # 2. Color & Monochrome Variants
    d2.text((72, 868), "2. Warianty kolorystyczne znaku", font=get_font(30, "bold"), fill=NAVY)

    card_w = (W - 144 - 40) // 3
    card_y0, card_y1 = 924, 1290
    # Variant A: Primary on White
    vx0 = 72
    d2.rounded_rectangle([vx0, card_y0, vx0 + card_w, card_y1], radius=6, fill=WHITE, outline=BORDER, width=2)
    paste_contain(p2, logo_rgba, (vx0 + 28, card_y0 + 24, vx0 + card_w - 28, card_y1 - 80))
    d2.text((vx0 + 20, card_y1 - 62), "Wersja podstawowa", font=get_font(18, "bold"), fill=NAVY)
    d2.text((vx0 + 20, card_y1 - 36), "Na białym tle (#FFFFFF)", font=get_font(15, "regular"), fill=MUTED)

    # Variant B: On Dark Navy Surface (inside crisp white badge per gov.pl best practice)
    vx1 = 72 + card_w + 20
    d2.rounded_rectangle([vx1, card_y0, vx1 + card_w, card_y1], radius=6, fill=NAVY, outline=NAVY, width=2)
    d2.rounded_rectangle([vx1 + 26, card_y0 + 22, vx1 + card_w - 26, card_y1 - 78], radius=8, fill=WHITE)
    paste_contain(p2, logo_rgba, (vx1 + 38, card_y0 + 32, vx1 + card_w - 38, card_y1 - 88))
    d2.text((vx1 + 20, card_y1 - 62), "Na ciemnym tle", font=get_font(18, "bold"), fill=WHITE)
    d2.text((vx1 + 20, card_y1 - 36), "Apla biała na #152B45", font=get_font(15, "regular"), fill="#CBD5E1")

    # Variant C: Monochrome Grayscale
    vx2 = 72 + (card_w + 20) * 2
    d2.rounded_rectangle([vx2, card_y0, vx2 + card_w, card_y1], radius=6, fill="#F8FAFC", outline=BORDER, width=2)
    gray_logo = ImageOps.grayscale(logo_rgba.convert("RGB")).convert("RGBA")
    gray_logo.putalpha(logo_rgba.getchannel("A"))
    paste_contain(p2, gray_logo, (vx2 + 28, card_y0 + 24, vx2 + card_w - 28, card_y1 - 80))
    d2.text((vx2 + 20, card_y1 - 62), "Wersja monochromatyczna", font=get_font(18, "bold"), fill=INK)
    d2.text((vx2 + 20, card_y1 - 36), "Druk czarno-biały / faks", font=get_font(15, "regular"), fill=MUTED)

    # 3. Minimum sizes table
    d2.text((72, 1340), "3. Minimalne wielkości użytkowe", font=get_font(30, "bold"), fill=NAVY)
    d2.rounded_rectangle([72, 1396, W - 72, 1630], radius=6, fill=SURFACE, outline=BORDER, width=2)
    rows = [
        ("Wersja znaku", "Minimalny rozmiar (Digital)", "Minimalny rozmiar (Druk)", "Zastosowanie"),
        ("Pełny znak z podpisem", "140 px wysokości", "35 mm wysokości", "Strony www, plakaty, prezentacje"),
        ("Sam sygnet (tarcza + serce)", "32 px x 32 px", "10 mm x 10 mm", "Favicon, ikony, piny mapowe"),
        ("Naklejka na kapsułę AED", "300 px (300 DPI)", "80 mm x 80 mm", "Oznakowanie szafek i kapsuł AED"),
    ]
    ry = 1412
    col_xs = [92, 365, 615, 835]
    for idx, r in enumerate(rows):
        f = get_font(17, "bold") if idx == 0 else get_font(16, "regular")
        col = NAVY if idx == 0 else INK
        if idx > 0:
            d2.line([(92, ry - 10), (W - 92, ry - 10)], fill=BORDER, width=1)
        for ci, cell in enumerate(r):
            d2.text((col_xs[ci], ry), cell, font=f, fill=col)
        ry += 52

    pages.append(p2)

    # ------------------------------------------------------------------
    # PAGE 3: COLOR PALETTE, TYPOGRAPHY & APPLICATIONS (A4 PORTRAIT)
    # ------------------------------------------------------------------
    p3 = Image.new("RGB", (W, H), WHITE)
    d3 = ImageDraw.Draw(p3)
    _booklet_header_footer(d3, W, H, 3, 4, "Kolorystyka, typografia i zastosowania")

    d3.text((72, 104), "4. Oficjalna paleta barw (HEX / RGB / CMYK)", font=get_font(30, "bold"), fill=NAVY)
    swatches = [
        ("Granat Państwowy (Tarcza i nazwa)", NAVY, "21, 43, 69", "70, 38, 0, 73", "14.4:1 AAA"),
        ("Karmazyn Narodowy / AED", CRIMSON, "217, 23, 59", "0, 89, 73, 15", "5.07:1 AA"),
        ("Błękit Instytucjonalny dane.gov.pl", GOV_BLUE, "0, 82, 165", "100, 50, 0, 35", "7.64:1 AAA"),
        ("Szmaragd Dostępności 24/7", EMERALD, "4, 120, 87", "97, 0, 28, 53", "5.48:1 AA"),
        ("Grafit Typograficzny (Tekst)", INK, "27, 27, 27", "0, 0, 0, 89", "17.22:1 AAA"),
    ]
    sy = 160
    for name, hx, rgb, cmyk, wcag in swatches:
        d3.rounded_rectangle([72, sy, W - 72, sy + 114], radius=6, fill=WHITE, outline=BORDER, width=2)
        d3.rounded_rectangle([88, sy + 16, 210, sy + 98], radius=4, fill=hx)
        d3.text((234, sy + 18), name, font=get_font(21, "bold"), fill=INK)
        d3.text((234, sy + 52), f"HEX: {hx}    |    RGB: {rgb}    |    CMYK: {cmyk}", font=get_font(17, "regular"), fill=MUTED)
        d3.rounded_rectangle([W - 280, sy + 36, W - 92, sy + 76], radius=4, fill=GOV_BLUE_LIGHT, outline=GOV_BLUE, width=1)
        draw_centered_text(d3, f"WCAG {wcag}", W - 186, sy + 46, get_font(16, "bold"), fill=GOV_BLUE)
        sy += 130

    # Typography section
    d3.text((72, 836), "5. Typografia oficjalna", font=get_font(30, "bold"), fill=NAVY)
    d3.rounded_rectangle([72, 890, 608, 1130], radius=6, fill=SURFACE, outline=BORDER, width=2)
    d3.text((96, 912), "KRÓJ PODSTAWOWY (INTER)", font=get_font(16, "bold"), fill=GOV_BLUE)
    d3.text((96, 946), "AaĄąBbCcĆćEeĘęŁłŃńÓóŚśŹźŻż", font=get_font(26, "bold"), fill=INK)
    draw_wrapped_text(
        d3,
        "Nagłówki, nawigacja portalu gov.pl, opisy lokalizacji AED oraz materiały edukacyjne. Pełne wsparcie polskich znaków diakrytycznych.",
        96,
        998,
        get_font(17, "regular"),
        488,
        fill=MUTED,
        line_spacing=6,
    )

    d3.rounded_rectangle([632, 890, W - 72, 1130], radius=6, fill=SURFACE, outline=BORDER, width=2)
    d3.text((656, 912), "KRÓJ TECHNICZNY (IBM PLEX MONO)", font=get_font(16, "bold"), fill=GOV_BLUE)
    d3.text((656, 946), "53.123500, 18.008400  |  0461011", font=get_font(24, "bold"), fill=INK)
    draw_wrapped_text(
        d3,
        "Współrzędne WGS84, kody TERYT/SIMC, identyfikatory UUID, punkty końcowe REST API oraz znaczniki formatów otwartych.",
        656,
        998,
        get_font(17, "regular"),
        488,
        fill=MUTED,
        line_spacing=6,
    )

    # Real-world applications
    d3.text((72, 1170), "6. Przykłady zastosowań kampanijnych", font=get_font(30, "bold"), fill=NAVY)
    apps = [
        ("Oznakowanie kapsuły AED", "Naklejka odporna na UV (80x80 mm) z logo i kodem QR do karty urządzenia w Krajowym Rejestrze AED."),
        ("Portal dane.gov.pl i BIP", "Baner dla urzędów miast i instytucji zachęcający do publikacji pliku .xlsx / GeoJSON."),
        ("Aplikacje ratownicze i 112", "Sygnet tarczy z sercem jako jednolity znacznik zweryfikowanych punktów AED na mapach."),
    ]
    ax = 72
    aw = (W - 144 - 40) // 3
    for title, desc in apps:
        d3.rounded_rectangle([ax, 1226, ax + aw, 1620], radius=6, fill=WHITE, outline=BORDER, width=2)
        d3.rectangle([ax, 1226, ax + aw, 1236], fill=NAVY)
        paste_contain(p3, logo_rgba, (ax + 50, 1252, ax + aw - 50, 1420))
        d3.text((ax + 20, 1438), title, font=get_font(19, "bold"), fill=NAVY)
        draw_wrapped_text(d3, desc, ax + 20, 1472, get_font(16, "regular"), aw - 40, fill=MUTED, line_spacing=6)
        ax += aw + 20

    pages.append(p3)

    # ------------------------------------------------------------------
    # PAGE 4: PROHIBITED USES & WCAG 2.1 ACCESSIBILITY MATRIX (A4 PORTRAIT)
    # ------------------------------------------------------------------
    p4 = Image.new("RGB", (W, H), WHITE)
    d4 = ImageDraw.Draw(p4)
    _booklet_header_footer(d4, W, H, 4, 4, "Niedozwolone modyfikacje i dostępność WCAG")

    d4.text((72, 104), "7. Niedozwolone wykorzystywanie znaku", font=get_font(30, "bold"), fill=CRIMSON)
    draw_wrapped_text(
        d4,
        "Aby zachować spójność i autorytet znaku Krajowego Rejestru AED, zabrania się wprowadzania jakichkolwiek zmian w proporcjach, kolorystyce lub układzie elementów.",
        72,
        148,
        get_font(18, "regular"),
        W - 144,
        fill=MUTED,
        line_spacing=6,
    )

    dont_specs = [
        ("1. Zakaz rozciągania proporcji", "stretch"),
        ("2. Zakaz obracania znaku", "rotate"),
        ("3. Zakaz zmiany kolorystyki", "recolor"),
        ("4. Zakaz niekontrastowego tła", "bad_bg"),
        ("5. Zakaz ucinania elementów", "crop"),
        ("6. Zakaz zacierania czytelności", "low_opacity"),
    ]
    gw = (W - 144 - 40) // 3
    gh = 330
    for idx, (label, mode) in enumerate(dont_specs):
        col = idx % 3
        row = idx // 3
        gx0 = 72 + col * (gw + 20)
        gy0 = 224 + row * (gh + 24)
        gx1, gy1 = gx0 + gw, gy0 + gh
        bg = "#FDE68A" if mode == "bad_bg" else WHITE
        d4.rounded_rectangle([gx0, gy0, gx1, gy1], radius=6, fill=bg, outline=CRIMSON, width=2)

        mod = logo_rgba.copy()
        if mode == "stretch":
            mod = mod.resize((int(mod.width * 1.55), int(mod.height * 0.65)), Image.Resampling.LANCZOS)
        elif mode == "rotate":
            mod = mod.rotate(28, expand=True, resample=Image.Resampling.BICUBIC)
        elif mode == "recolor":
            r, g, b, a = mod.split()
            mod = Image.merge("RGBA", (g, b, r, a))
        elif mode == "crop":
            mod = mod.crop((0, 0, int(mod.width * 0.62), int(mod.height * 0.68)))
        elif mode == "low_opacity":
            r, g, b, a = mod.split()
            a = a.point(lambda v: int(v * 0.28))
            mod = Image.merge("RGBA", (r, g, b, a))

        paste_contain(p4, mod, (gx0 + 28, gy0 + 26, gx1 - 28, gy1 - 74))

        # Red X badge
        d4.ellipse([gx1 - 46, gy0 + 14, gx1 - 14, gy0 + 46], fill=CRIMSON)
        d4.text((gx1 - 37, gy0 + 18), "X", font=get_font(20, "black"), fill=WHITE)
        d4.rectangle([gx0 + 2, gy1 - 56, gx1 - 2, gy1 - 2], fill="#FEF2F2")
        d4.text((gx0 + 16, gy1 - 40), label, font=get_font(16, "bold"), fill=CRIMSON)

    # 8. WCAG 2.1 Digital Accessibility Matrix
    d4.text((72, 956), "8. Zgodność cyfrowa WCAG 2.1 AA / AAA i dostępność fizyczna", font=get_font(28, "bold"), fill=NAVY)
    d4.rounded_rectangle([72, 1010, W - 72, 1626], radius=6, fill=SURFACE, outline=BORDER, width=2)

    wcag_rows = [
        ("Kryterium WCAG 2.1 / gov.pl", "Wdrożenie w portalu Krajowy Rejestr AED", "Wynik"),
        ("Kontrast tekstu (1.4.3 / 1.4.6)", "Grafit #1B1B1B (17.2:1), Błękit #0052A5 (7.6:1), Szmaragd #047857 (5.5:1)", "AA / AAA"),
        ("Tryb wysokiego kontrastu BIP", "Czerń #000000 + Żółć #FFFF00 (19.56:1), przełącznik w pasku gov.pl", "AAA"),
        ("Skalowanie tekstu (1.4.4)", "3-stopniowy przełącznik A (100%), A+ (120%), A++ (140%) w localStorage", "SPEŁNIONE"),
        ("Nawigacja klawiaturą (2.4.7)", "Oficjalny potrójny pierścień fokusu gov.pl (#0452A8 / #FFF / #0452A8)", "SPEŁNIONE"),
        ("Czytniki ekranu (ARIA)", "Regiony aria-live, scope/caption w tabelach, obsługa Escape w modalach", "SPEŁNIONE"),
        ("Ograniczenie ruchu (2.3.3)", "Pełne wsparcie prefers-reduced-motion w CSS, mapie i przewijaniu", "SPEŁNIONE"),
        ("Dostępność fizyczna (3 marca)", "Alerty „Otwarte teraz” / „Zamknięte teraz” / „dostęp ograniczony” + tel:", "AKTYWNE"),
    ]
    wy = 1028
    wcols = [96, 470, 1020]
    for idx, row in enumerate(wcag_rows):
        f = get_font(17, "bold") if idx == 0 else get_font(16, "regular")
        c = NAVY if idx == 0 else INK
        if idx > 0:
            d4.line([(92, wy - 10), (W - 92, wy - 10)], fill=BORDER, width=1)
        d4.text((wcols[0], wy), row[0], font=get_font(16, "bold") if idx > 0 else f, fill=c)
        d4.text((wcols[1], wy), row[1], font=f, fill=c)
        badge_col = EMERALD if idx > 0 else NAVY
        d4.text((wcols[2], wy), row[2], font=get_font(16, "bold"), fill=badge_col)
        wy += 72

    pages.append(p4)

    out_pdf = DELIV_DIR / "Ksiega_Znaku_Misja_AED.pdf"
    pages[0].save(out_pdf, format="PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    shutil.copy2(out_pdf, PUBLIC_DELIV_DIR / "Ksiega_Znaku_Misja_AED.pdf")


def _slide_chrome(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    slide_num: int,
    total_slides: int,
    kicker: str,
    title: str,
) -> None:
    draw.rectangle([0, 0, w, 10], fill=NAVY)
    draw.rectangle([0, 10, w, 15], fill=CRIMSON)
    draw.text((64, 34), kicker.upper(), font=get_font(16, "bold"), fill=CRIMSON)
    draw.text((64, 60), title, font=get_font(36, "black"), fill=NAVY)
    draw.line([(64, 114), (w - 64, 114)], fill=BORDER, width=2)

    draw.line([(64, h - 56), (w - 64, h - 56)], fill=BORDER, width=2)
    draw.text(
        (64, h - 42),
        "Krajowy Rejestr AED  |  Misja AED: Dane na ratunek  |  Ministerstwo Cyfryzacji / dane.gov.pl",
        font=get_font(15, "regular"),
        fill=MUTED,
    )
    st = f"Slajd {slide_num} / {total_slides}"
    sf = get_font(15, "bold")
    sb = draw.textbbox((0, 0), st, font=sf)
    draw.text((w - 64 - (sb[2] - sb[0]), h - 42), st, font=sf, fill=NAVY)


def build_presentation_pdf(logo_rgba: Image.Image) -> None:
    """Builds an executive 7-slide 16:9 presentation embedding the final logo and real platform screenshots."""
    W, H = 1600, 900
    slides: list[Image.Image] = []

    shot_map = Image.open(SCREENSHOTS_DIR / "map_view.jpg").convert("RGB")
    shot_open = Image.open(SCREENSHOTS_DIR / "open_data.jpg").convert("RGB")
    shot_sub_top = Image.open(SCREENSHOTS_DIR / "submit_top.jpg").convert("RGB")
    shot_sub_bot = Image.open(SCREENSHOTS_DIR / "submit_bottom.jpg").convert("RGB")

    # ------------------------------------------------------------------
    # SLIDE 1: COVER
    # ------------------------------------------------------------------
    s1 = Image.new("RGB", (W, H), WHITE)
    d1 = ImageDraw.Draw(s1)
    d1.rectangle([0, 0, 560, H], fill=NAVY)
    d1.rectangle([560, 0, 570, H], fill=CRIMSON)

    # White logo card on left navy panel
    d1.rounded_rectangle([66, 130, 494, 640], radius=12, fill=WHITE)
    paste_contain(s1, logo_rgba, (92, 156, 468, 614))

    d1.text((66, 684), "KAMPANIA SPOŁECZNA", font=get_font(16, "bold"), fill="#93C5FD")
    d1.text((66, 712), "IMPULS DLA DANYCH", font=get_font(30, "black"), fill=WHITE)
    draw_wrapped_text(
        d1,
        "„Zamknięta wiedza nie ratuje życia. Otwórz dane o swoim AED w portalu dane.gov.pl.”",
        66,
        760,
        get_font(18, "italic"),
        428,
        fill="#E2E8F0",
        line_spacing=6,
    )

    # Right content panel
    d1.text((630, 120), "WYZWANIE HACKNATION  |  MINISTERSTWO CYFRYZACJI", font=get_font(18, "bold"), fill=CRIMSON)
    d1.text((630, 162), "Krajowy Rejestr AED", font=get_font(60, "black"), fill=NAVY)
    d1.text((630, 238), "Misja AED: Dane na ratunek", font=get_font(32, "bold"), fill=GOV_BLUE)
    draw_wrapped_text(
        d1,
        "Ogólnopolski hub otwartych danych o defibrylatorach AED integrujący rejestry samorządowe dane.gov.pl, "
        "OpenStreetMap oraz zgłoszenia dysponentów w jednym, dostępnym cyfrowo (WCAG 2.1 AA/AAA) portalu gov.pl.",
        630,
        304,
        get_font(22, "regular"),
        900,
        fill=INK,
        line_spacing=10,
    )

    # 4 Live Metrics Cards
    kpis = [
        ("18 319", "Ujednoliconych AED", "Deduplikacja 25 m"),
        ("5 formatów", "Otwartych danych", "GeoJSON, CSV, JSON-LD, XLSX, XML"),
        ("WCAG 2.1", "AA & AAA (BIP)", "A/A+/A++, fokus gov.pl"),
        ("18 / 18", "Testów pytest", "FastAPI Cloud + Prisma"),
    ]
    kx = 630
    kw = 212
    for val, lbl, sub in kpis:
        d1.rounded_rectangle([kx, 470, kx + kw, 634], radius=8, fill=SURFACE, outline=BORDER, width=2)
        d1.rectangle([kx, 470, kx + kw, 478], fill=GOV_BLUE)
        d1.text((kx + 16, 496), val, font=get_font(30, "black"), fill=NAVY)
        d1.text((kx + 16, 542), lbl, font=get_font(17, "bold"), fill=INK)
        draw_wrapped_text(d1, sub, kx + 16, 572, get_font(14, "regular"), kw - 32, fill=MUTED, line_spacing=4)
        kx += kw + 18

    # Live deployment strip
    d1.rounded_rectangle([630, 686, 1536, 814], radius=8, fill=GOV_BLUE_LIGHT, outline=GOV_BLUE, width=2)
    d1.text((656, 706), "ŚRODOWISKO PRODUKCYJNE (LIVE)", font=get_font(16, "bold"), fill=GOV_BLUE)
    d1.text((656, 738), "API FastAPI Cloud:  https://krajowy-rejestr-aed.fastapicloud.dev/docs", font=get_font(18, "bold"), fill=NAVY)
    d1.text((656, 772), "Baza danych: Prisma Postgres (db.prisma.io)  |  Frontend: React 19 + MapLibre GL (Vercel)", font=get_font(17, "regular"), fill=MUTED)
    slides.append(s1)

    # ------------------------------------------------------------------
    # SLIDE 2: PROBLEM "3 MARCA" & DATA HARMONIZATION
    # ------------------------------------------------------------------
    s2 = Image.new("RGB", (W, H), WHITE)
    d2 = ImageDraw.Draw(s2)
    _slide_chrome(d2, W, H, 2, 7, "1. Diagnoza problemu i architektura danych", "Problem „3 marca” i harmonizacja rozproszonych źródeł")

    # Left column: The problem
    d2.rounded_rectangle([64, 144, 760, 810], radius=8, fill="#FEF2F2", outline=CRIMSON, width=2)
    d2.text((92, 170), "DLACZEGO DANE O AED ZAWODZĄ W KRYZYSIE?", font=get_font(20, "bold"), fill=CRIMSON)
    probs = [
        ("Zamknięte na klucz (kontekst 3 marca)", "Wiele defibrylatorów znajduje się wewnątrz urzędów lub firm zamkniętych w nocy i w weekendy — brak godzin otwarcia myli świadka zdarzenia."),
        ("Rozproszenie i brak wspólnego schematu", "Samorządy (Legionowo, Krosno, Marki, Przemyśl) publikują pliki w różnych formatach (CSV, GeoJSON), czasem z odwróconymi współrzędnymi X/Y."),
        ("Duplikaty i niekompletne opisy", "Ten sam AED pojawia się w rejestrze miejskim i OpenStreetMap bez dokładnego opisu piętra, ściany czy numeru telefonu do ochrony."),
    ]
    py = 224
    for pt, pd in probs:
        d2.rounded_rectangle([92, py, 732, py + 170], radius=6, fill=WHITE, outline="#FECACA", width=2)
        d2.text((114, py + 18), pt, font=get_font(21, "bold"), fill=NAVY)
        draw_wrapped_text(d2, pd, 114, py + 54, get_font(18, "regular"), 596, fill=INK, line_spacing=7)
        py += 192

    # Right column: Our solution pipeline
    d2.rounded_rectangle([796, 144, W - 64, 810], radius=8, fill=GOV_BLUE_LIGHT, outline=GOV_BLUE, width=2)
    d2.text((824, 170), "NASZE ROZWIĄZANIE: SILNIK HARMONIZACJI", font=get_font(20, "bold"), fill=GOV_BLUE)
    steps = [
        ("1. Konektory wieloźródłowe (Tier 1–3)", "Automatyczny pobór z PL.geojson (18 291 pkt), oficjalnych rejestrów dane.gov.pl (UM Legionowo, Krosno, Marki, Przemyśl), Overpass OSM oraz zgłoszeń."),
        ("2. Walidacja Pydantic v2 + korekta osi X/Y", "Każdy rekord przechodzi walidację granic Polski (WGS84), normalizację godzin otwarcia oraz automatyczne odwracanie zamienionych współrzędnych."),
        ("3. Deduplikacja przestrzenna 25 m + Provenance", "Punkty w promieniu 25 m scalane są w jeden kanoniczny rekord z zachowaniem pełnej historii źródeł i wyliczeniem jakości 0–100%."),
        ("4. Wzbogacanie adresów (Nominatim + cache DB)", "Brakujące adresy ulic i miast są uzupełniane na żywo i zapisywane w bazie danych, podnosząc użyteczność ratowniczą."),
    ]
    sy = 224
    for st, sd in steps:
        d2.rounded_rectangle([824, sy, W - 92, sy + 130], radius=6, fill=WHITE, outline=BORDER, width=2)
        d2.text((846, sy + 14), st, font=get_font(19, "bold"), fill=NAVY)
        draw_wrapped_text(d2, sd, 846, sy + 46, get_font(16, "regular"), W - 960, fill=INK, line_spacing=6)
        sy += 144
    slides.append(s2)

    # ------------------------------------------------------------------
    # SLIDE 3: LIVE PLATFORM SCREENSHOT — MAP & "3 MARCA" REACHABILITY
    # ------------------------------------------------------------------
    s3 = Image.new("RGB", (W, H), WHITE)
    d3 = ImageDraw.Draw(s3)
    _slide_chrome(d3, W, H, 3, 7, "2. Działający prototyp — portal obywatelski gov.pl", "Mapa krajowa AED, wyszukiwarka i alerty dostępności „3 marca”")

    # Left: Real screenshot of Map View
    paste_contain(s3, shot_map, (64, 144, 1080, 816), border_color=BORDER, border_width=2)

    # Right: Key UX & Accessibility Highlights
    d3.rounded_rectangle([1108, 144, W - 64, 816], radius=8, fill=SURFACE, outline=BORDER, width=2)
    d3.text((1134, 168), "KLUCZOWE FUNKCJE PORTALU", font=get_font(18, "bold"), fill=GOV_BLUE)
    bullets3 = [
        ("Spójny design gov.pl", "Oficjalna hierarchia nagłówków, kolorystyka #0052A5 / #D5233F, potrójny pierścień fokusu i przełącznik PL / EN."),
        ("Alerty fizyczne „3 marca”", "Każdy punkt pokazuje status „Otwarte teraz” lub „Zamknięte teraz” oraz ostrzeżenia „dostęp ograniczony” / „dla klientów”."),
        ("Bezpieczna lokalizacja GPS", "Wielopróbkowe GPS + ochrona przed skokiem na serwer IP w Warszawie + ręczny pin „Wskaż moją lokalizację na mapie”."),
        ("Pełna dostępność WCAG 2.1", "Skalowanie tekstu A / A+ / A++, tryb wysokiego kontrastu AAA (19.5:1), aria-live oraz prefers-reduced-motion."),
    ]
    by = 216
    for bt, bd in bullets3:
        d3.rounded_rectangle([1130, by, W - 86, by + 136], radius=6, fill=WHITE, outline=BORDER, width=1)
        d3.text((1148, by + 14), bt, font=get_font(18, "bold"), fill=NAVY)
        draw_wrapped_text(d3, bd, 1148, by + 44, get_font(15, "regular"), W - 1252, fill=INK, line_spacing=5)
        by += 148
    slides.append(s3)

    # ------------------------------------------------------------------
    # SLIDE 4: LIVE PLATFORM SCREENSHOT — OPEN DATA HUB (DANE.GOV.PL)
    # ------------------------------------------------------------------
    s4 = Image.new("RGB", (W, H), WHITE)
    d4 = ImageDraw.Draw(s4)
    _slide_chrome(d4, W, H, 4, 7, "3. Zgodność z dane.gov.pl (30% kryteriów oceny)", "Hub Otwartych Danych: 5 formatów maszynowych i Harvester XML 1.13")

    paste_contain(s4, shot_open, (64, 144, 1080, 816), border_color=BORDER, border_width=2)

    d4.rounded_rectangle([1108, 144, W - 64, 816], radius=8, fill=GOV_BLUE_LIGHT, outline=GOV_BLUE, width=2)
    d4.text((1134, 168), "STANDARDY OTWARTOŚCI", font=get_font(18, "bold"), fill=GOV_BLUE)
    formats4 = [
        ("GeoJSON (RFC 7946)", "Geometrie punktowe EPSG:4326 gotowe dla GIS i SWD PRM."),
        ("CSV (UTF-8 z BOM)", "Arkusz zgodny z Excel oraz importem w portalu dane.gov.pl."),
        ("JSON-LD (DCAT-AP 4*)", "Dane powiązane semantycznie (W3C DCAT-AP + schema.org)."),
        ("Wzorcowy XLSX (3 zakładki)", "Specyfikacja 18 pól, macierz źródeł i szablon dla dysponenta."),
        ("Harvester XML 1.13 + MD5", "Katalog urn:open-data:1.13 z obsługą HEAD, MD5 i ETag 304."),
    ]
    fy = 216
    for ft, fd in formats4:
        d4.rounded_rectangle([1130, fy, W - 86, fy + 106], radius=6, fill=WHITE, outline=BORDER, width=1)
        d4.text((1148, fy + 12), ft, font=get_font(18, "bold"), fill=NAVY)
        draw_wrapped_text(d4, fd, 1148, fy + 40, get_font(15, "regular"), W - 1252, fill=INK, line_spacing=5)
        fy += 118
    slides.append(s4)

    # ------------------------------------------------------------------
    # SLIDE 5: LIVE PLATFORM SCREENSHOTS — SUBMIT, VERIFY & COMPLETENESS
    # ------------------------------------------------------------------
    s5 = Image.new("RGB", (W, H), WHITE)
    d5 = ImageDraw.Draw(s5)
    _slide_chrome(d5, W, H, 5, 7, "4. Ścieżka użytkownika i dysponenta (krok po kroku)", "Zgłaszanie i weryfikacja AED z licznikiem jakości dane.gov.pl")

    # Left top & bottom stacked screenshots
    paste_contain(s5, shot_sub_top, (64, 144, 780, 560), border_color=BORDER, border_width=2)
    paste_contain(s5, shot_sub_bot, (812, 144, W - 64, 560), border_color=BORDER, border_width=2)

    # Bottom 3-step user journey strip
    d5.rounded_rectangle([64, 594, W - 64, 816], radius=8, fill=SURFACE, outline=BORDER, width=2)
    j_steps = [
        ("KROK 1: Wskaż punkt na mapie lub GPS", "Dysponent lub obywatel wybiera wejście budynku na mapie, wpisuje dokładny opis miejsca (piętro, hol, ściana) oraz godziny dostępności 24/7."),
        ("KROK 2: Podgląd zgodności 0–100%", "Wbudowany miernik jakości w czasie rzeczywistym sprawdza 10 kryteriów standardu dane.gov.pl (próg minimalny 60%, wzorcowy >= 80%)."),
        ("KROK 3: Zapis lub automatyczne scalenie 25 m", "Jeśli w promieniu 25 m istnieje już rekord, API wzbogaca go i dopisuje instytucję do rejestru pochodzenia (provenance) bez tworzenia duplikatu."),
    ]
    jx = 88
    jw = (W - 176 - 48) // 3
    for jt, jd in j_steps:
        d5.rounded_rectangle([jx, 616, jx + jw, 794], radius=6, fill=WHITE, outline=BORDER, width=1)
        d5.text((jx + 18, 632), jt, font=get_font(18, "bold"), fill=GOV_BLUE)
        draw_wrapped_text(d5, jd, jx + 18, 666, get_font(16, "regular"), jw - 36, fill=INK, line_spacing=6)
        jx += jw + 24
    slides.append(s5)

    # ------------------------------------------------------------------
    # SLIDE 6: CAMPAIGN "IMPULS DLA DANYCH" & 18-FIELD STANDARD
    # ------------------------------------------------------------------
    s6 = Image.new("RGB", (W, H), WHITE)
    d6 = ImageDraw.Draw(s6)
    _slide_chrome(d6, W, H, 6, 7, "5. Akcja promocyjna (25%) i Wzorcowy Zakres Danych (10%)", "Kampania „Impuls dla Danych”, logotyp i standard 18 pól (.xlsx)")

    # Left: Logo + Campaign strategy
    d6.rounded_rectangle([64, 144, 580, 816], radius=8, fill=WHITE, outline=BORDER, width=2)
    paste_contain(s6, logo_rgba, (124, 166, 520, 504))
    d6.rounded_rectangle([88, 524, 556, 650], radius=6, fill=GOV_BLUE_LIGHT, outline=GOV_BLUE, width=1)
    d6.text((106, 538), "HASŁO KAMPANII", font=get_font(14, "bold"), fill=GOV_BLUE)
    draw_wrapped_text(
        d6,
        "„Zamknięta wiedza nie ratuje życia. Otwórz dane o swoim AED w portalu dane.gov.pl.”",
        106,
        564,
        get_font(18, "italic"),
        432,
        fill=NAVY,
        line_spacing=6,
    )
    draw_wrapped_text(
        d6,
        "Artefakty gotowe do wdrożenia: logotyp (.svg, .png, .jpg, .pdf), 4-stronicowa Księga Znaku A4 (.pdf) oraz wzorcowy arkusz (.xlsx) dostępny w zakładce „Kampania i Standard”.",
        88,
        674,
        get_font(16, "regular"),
        468,
        fill=MUTED,
        line_spacing=6,
    )

    # Right: Reference 18-field schema summary + municipal onboarding
    d6.rounded_rectangle([612, 144, W - 64, 560], radius=8, fill=SURFACE, outline=BORDER, width=2)
    d6.text((640, 168), "WZORCOWY ZAKRES DANYCH AED (18 PÓL KANONICZNYCH — .XLSX)", font=get_font(19, "bold"), fill=NAVY)
    groups = [
        ("Lokalizacja i adres (40 pkt)", "latitude, longitude (WGS84), street_address, city, postal_code, teryt_code (SIMC)"),
        ("Kontekst „3 marca” i opis (45 pkt)", "location_description (25 pkt), access_type, is_24_7, opening_hours, indoor, level"),
        ("Status, weryfikacja i kontakt (15 pkt)", "status, last_verified_at (ważność 365 dni), operator, phone (ochrona/portiernia)"),
        ("Metadane systemowe", "id (UUID), primary_source, completeness_score, pełna ścieżka provenance"),
    ]
    gy = 216
    for gt, gd in groups:
        d6.rounded_rectangle([640, gy, W - 92, gy + 74], radius=6, fill=WHITE, outline=BORDER, width=1)
        d6.text((658, gy + 10), gt, font=get_font(17, "bold"), fill=GOV_BLUE)
        d6.text((658, gy + 38), gd, font=get_font(15, "regular"), fill=INK)
        gy += 84

    d6.rounded_rectangle([612, 588, W - 64, 816], radius=8, fill=NAVY)
    d6.text((640, 612), "3 KROKI DLA SAMORZĄDU / INSTYTUCJI (ADOPCJA)", font=get_font(19, "bold"), fill="#93C5FD")
    msteps = [
        "1. Pobierz szablon Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx z portalu i uzupełnij lokalizacje AED.",
        "2. Opublikuj plik w dane.gov.pl lub wgraj w zakładce „Otwarte dane” (natychmiastowa walidacja i deduplikacja).",
        "3. Pobierz naklejkę z logo „Impuls dla Danych” i umieść ją na kapsule AED oraz stronie BIP urzędu.",
    ]
    my = 656
    for ms in msteps:
        draw_wrapped_text(d6, ms, 640, my, get_font(17, "regular"), W - 732, fill=WHITE, line_spacing=5)
        my += 50
    slides.append(s6)

    # ------------------------------------------------------------------
    # SLIDE 7: PRODUCTION ARCHITECTURE, VERIFICATION & HONEST LIMITATIONS
    # ------------------------------------------------------------------
    s7 = Image.new("RGB", (W, H), WHITE)
    d7 = ImageDraw.Draw(s7)
    _slide_chrome(d7, W, H, 7, 7, "6. Weryfikacja techniczna, ograniczenia i plan rozwoju", "Architektura produkcyjna, testy automatyczne i jawne ograniczenia")

    # Left: Production Architecture & Verification
    d7.rounded_rectangle([64, 144, 780, 816], radius=8, fill=GOV_BLUE_LIGHT, outline=GOV_BLUE, width=2)
    d7.text((92, 170), "ARCHITEKTURA I DOWODY TECHNICZNE", font=get_font(20, "bold"), fill=GOV_BLUE)
    tech_items = [
        ("Backend FastAPI Cloud (Python 3.13 + SQLAlchemy Async)", "Live pod krajowy-rejestr-aed.fastapicloud.dev. Pełna zgodność MCOD v2.63.0 (JSON:API, polubienia, SlowSQL, Prometheus, XML 1.13)."),
        ("Baza danych Prisma Postgres (Plug-and-Play)", "18 319 punktów AED i 18 365 rekordów źródłowych w chmurze. Automatyczny fallback PostGIS -> indeksowany Haversine (działa na każdym Postgresie)."),
        ("Frontend React 19 + TypeScript + MapLibre GL (Vercel)", "Oficjalny design gov.pl, 0 błędów TS, 0 danych makietowych (100% live API), WCAG 2.1 AA/AAA."),
        ("Testy automatyczne i audyt", "18/18 testów pytest (deduplikacja 25 m, kompletność, eksporty, MCOD v2.63, normalizacja URL Prisma) + audyt kontrastów WCAG."),
    ]
    ty = 222
    for tt, td in tech_items:
        d7.rounded_rectangle([92, ty, 752, ty + 132], radius=6, fill=WHITE, outline=BORDER, width=1)
        d7.text((112, ty + 14), tt, font=get_font(18, "bold"), fill=NAVY)
        draw_wrapped_text(d7, td, 112, ty + 46, get_font(15, "regular"), 620, fill=INK, line_spacing=5)
        ty += 146

    # Right: Honest Limitations & Roadmap
    d7.rounded_rectangle([812, 144, W - 64, 512], radius=8, fill="#FFFBEB", outline=AMBER, width=2)
    d7.text((840, 170), "JAWNE OGRANICZENIA ROZWIĄZANIA", font=get_font(20, "bold"), fill=AMBER)
    lims = [
        ("Pokrycie godzin otwarcia (37.1%)", "Dane z OSM często nie zawierają godzin otwarcia; portal oznacza takie punkty wprost i zachęca do ich uzupełnienia."),
        ("Limit zapytań Nominatim (1 req/s)", "Geokodowanie wsteczne adresów jest buforowane w bazie danych, aby nie przekraczać limitów OSM."),
        ("Dobrowolność zasilania przez dysponentów", "Pełna aktualność rejestru wymaga udziału JST i instytucji — dlatego równolegle stworzono kampanię „Impuls dla Danych”."),
    ]
    ly = 222
    for lt, ld in lims:
        d7.text((840, ly), f"• {lt}:", font=get_font(17, "bold"), fill=NAVY)
        ly = draw_wrapped_text(d7, ld, 858, ly + 26, get_font(15, "regular"), W - 952, fill=INK, line_spacing=5) + 12

    d7.rounded_rectangle([812, 540, W - 64, 816], radius=8, fill=NAVY)
    d7.text((840, 566), "KOLEJNE KROKI WDROŻENIOWE (ROADMAP)", font=get_font(20, "bold"), fill="#93C5FD")
    road = [
        "1. Podpięcie harvestera XML 1.13 bezpośrednio do produkcyjnego katalogu dane.gov.pl.",
        "2. Integracja kanału GeoJSON z Systemem Wspomagania Dowodzenia PRM i aplikacją mObywatel.",
        "3. Automatyczne przypomnienia (co 365 dni) do dysponentów o przeglądzie elektrod i baterii AED.",
    ]
    ry = 616
    for ritem in road:
        ry = draw_wrapped_text(d7, ritem, 840, ry, get_font(17, "regular"), W - 932, fill=WHITE, line_spacing=6) + 14

    slides.append(s7)

    out_pdf = DELIV_DIR / "Prezentacja_Misja_AED.pdf"
    slides[0].save(out_pdf, format="PDF", resolution=150.0, save_all=True, append_images=slides[1:])
    shutil.copy2(out_pdf, PUBLIC_DELIV_DIR / "Prezentacja_Misja_AED.pdf")


def build_xlsx_standard() -> None:
    DELIV_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DELIV_DIR.mkdir(parents=True, exist_ok=True)
    xlsx_bytes = generate_standard_xlsx_bytes()
    out_xlsx = DELIV_DIR / "Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx"
    out_xlsx.write_bytes(xlsx_bytes)
    shutil.copy2(out_xlsx, PUBLIC_DELIV_DIR / "Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx")


def main() -> None:
    if not LOGO_SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Final logo not found at {LOGO_SOURCE_PATH}")

    logo_rgba = prepare_clean_logo_rgba(LOGO_SOURCE_PATH)
    export_logotypes(logo_rgba)
    build_portrait_brand_book(logo_rgba)
    build_presentation_pdf(logo_rgba)
    build_xlsx_standard()
    print("Generated all Misja AED deliverables successfully:")
    for p in sorted(DELIV_DIR.rglob("*")):
        if p.is_file() and p.parent.name != "screenshots":
            print(f"  - {p.relative_to(ROOT_DIR)} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()

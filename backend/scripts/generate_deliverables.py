import math
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

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
LOGO_DIR = DELIV_DIR / "logotyp"
PUBLIC_DELIV_DIR = ROOT_DIR / "frontend" / "public" / "deliverables"

FONT_REG_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_ITALIC_PATH = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"
FONT_BLACK_PATH = "/System/Library/Fonts/Supplemental/Arial Black.ttf"


def get_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = FONT_REG_PATH
    if weight == "bold":
        path = FONT_BOLD_PATH
    elif weight == "italic":
        path = FONT_ITALIC_PATH
    elif weight == "black":
        path = FONT_BLACK_PATH
    return ImageFont.truetype(path, size)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
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
    fill: str = "#1B1B1B",
    line_spacing: int = 8,
) -> int:
    lines = wrap_text(draw, text, font, max_width)
    cur_y = y
    for line in lines:
        draw.text((x, cur_y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        cur_y += (bbox[3] - bbox[1]) + line_spacing
    return cur_y


def draw_heart_polygon(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    scale: float,
    fill: str | None,
    outline: str | None = None,
    width: int = 3,
) -> None:
    pts: list[tuple[float, float]] = []
    for i in range(120):
        t = (2 * math.pi * i) / 120
        x = 16 * (math.sin(t) ** 3)
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * scale, cy + y * scale))
    draw.polygon(pts, fill=fill, outline=outline, width=width)


def draw_campaign_emblem(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    size: int,
    *,
    variant: str = "color",
    deform_x: float = 1.0,
) -> None:
    """Draws the 'IMPULS DLA DANYCH / MISJA AED' campaign emblem inside box (x, y, size*deform_x, size)."""
    w = int(size * deform_x)
    h = size
    r = max(8, size // 8)

    if variant == "color":
        bg_shield = "#0052A5"
        accent_bar = "#D4213D"
        heart_fill = "#D4213D"
        heart_outline = "#FFFFFF"
        pulse_color = "#FFFFFF"
        node_fill = "#059669"
        cross_color = "#FFFFFF"
    elif variant == "mono_dark":
        bg_shield = "#1B1B1B"
        accent_bar = "#1B1B1B"
        heart_fill = "#1B1B1B"
        heart_outline = "#FFFFFF"
        pulse_color = "#FFFFFF"
        node_fill = "#FFFFFF"
        cross_color = "#FFFFFF"
    elif variant == "mono_light":
        bg_shield = "#FFFFFF"
        accent_bar = "#FFFFFF"
        heart_fill = "#FFFFFF"
        heart_outline = "#1B1B1B"
        pulse_color = "#1B1B1B"
        node_fill = "#1B1B1B"
        cross_color = "#1B1B1B"
    else:  # wrong_colors
        bg_shield = "#9333EA"
        accent_bar = "#F59E0B"
        heart_fill = "#EC4899"
        heart_outline = "#FEF08A"
        pulse_color = "#FEF08A"
        node_fill = "#22D3EE"
        cross_color = "#FEF08A"

    # Outer rounded square (Open Data Bracket / Shield)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=bg_shield)

    # Bottom Polish crimson bar
    bar_h = max(6, h // 11)
    draw.rounded_rectangle([x, y + h - bar_h, x + w, y + h], radius=r // 2, fill=accent_bar)

    # Top-right medical cross + open data node motif
    cross_cx = x + int(w * 0.80)
    cross_cy = y + int(h * 0.20)
    arm = max(4, int(size * 0.075))
    thick = max(2, int(size * 0.032))
    draw.rectangle([cross_cx - arm, cross_cy - thick, cross_cx + arm, cross_cy + thick], fill=cross_color)
    draw.rectangle([cross_cx - thick, cross_cy - arm, cross_cx + thick, cross_cy + arm], fill=cross_color)

    # Center heart
    h_cx = x + w * 0.47
    h_cy = y + h * 0.49
    h_scale = (size / 54.0) * min(1.0, deform_x)
    draw_heart_polygon(
        draw,
        h_cx,
        h_cy,
        h_scale,
        fill=heart_fill,
        outline=heart_outline,
        width=max(2, size // 42),
    )

    # ECG / Defibrillator impulse line connecting 3 open data nodes
    p_y = y + int(h * 0.51)
    pts = [
        (x + int(w * 0.14), p_y),
        (x + int(w * 0.33), p_y),
        (x + int(w * 0.41), y + int(h * 0.31)),
        (x + int(w * 0.49), y + int(h * 0.68)),
        (x + int(w * 0.57), y + int(h * 0.42)),
        (x + int(w * 0.63), p_y),
        (x + int(w * 0.84), p_y),
    ]
    lw = max(2, size // 28)
    draw.line(pts, fill=pulse_color, width=lw, joint="curve")

    # Open data nodes at start and end of ECG pulse
    node_r = max(3, size // 20)
    for nx, ny in [pts[0], pts[-1]]:
        draw.ellipse(
            [nx - node_r, ny - node_r, nx + node_r, ny + node_r],
            fill=node_fill,
            outline=pulse_color,
            width=max(1, size // 55),
        )


def draw_full_lockup(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    emblem_size: int = 180,
    *,
    variant: str = "color",
    show_slogan: bool = True,
) -> tuple[int, int]:
    """Draws full horizontal campaign lockup (emblem + typography) and returns (width, height)."""
    draw_campaign_emblem(draw, x, y, emblem_size, variant=variant)

    tx = x + emblem_size + int(emblem_size * 0.24)
    kicker_font = get_font(max(11, int(emblem_size * 0.105)), "bold")
    title_font = get_font(max(20, int(emblem_size * 0.255)), "black")
    sub_font = get_font(max(12, int(emblem_size * 0.135)), "bold")
    slogan_font = get_font(max(10, int(emblem_size * 0.088)), "italic")

    kicker_color = "#D4213D" if variant == "color" else ("#FFFFFF" if variant == "dark_bg" else "#1B1B1B")
    title_color = "#1B1B1B" if variant != "dark_bg" else "#FFFFFF"
    sub_color = "#0052A5" if variant == "color" else title_color
    slogan_color = "#4A5568" if variant != "dark_bg" else "#D5DCE2"

    cy = y + int(emblem_size * 0.07)
    draw.text((tx, cy), "OGÓLNOPOLSKA AKCJA DANE.GOV.PL | MISJA AED", font=kicker_font, fill=kicker_color)
    cy += int(emblem_size * 0.17)

    draw.text((tx, cy), "IMPULS DLA DANYCH", font=title_font, fill=title_color)
    cy += int(emblem_size * 0.34)

    draw.text((tx, cy), "Otwórz dane o AED. Ocal cenne minuty życia.", font=sub_font, fill=sub_color)
    cy += int(emblem_size * 0.22)

    if show_slogan:
        draw.text(
            (tx, cy),
            "„Zamknięta wiedza nie ratuje życia. Udostępnij lokalizację swojego AED w portalu dane.gov.pl.”",
            font=slogan_font,
            fill=slogan_color,
        )

    total_w = emblem_size + int(emblem_size * 4.8)
    return total_w, emblem_size


def generate_logo_svg() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 260" width="960" height="260" role="img" aria-label="Impuls dla Danych - Misja AED (dane.gov.pl)">
  <defs>
    <style>
      .kicker { font: 700 16px 'Inter', 'Arial', sans-serif; fill: #D4213D; letter-spacing: 1.2px; }
      .title { font: 900 52px 'Inter', 'Arial Black', sans-serif; fill: #1B1B1B; letter-spacing: -0.5px; }
      .sub { font: 700 26px 'Inter', 'Arial', sans-serif; fill: #0052A5; }
      .slogan { font: 500 17px 'Inter', 'Arial', sans-serif; fill: #4A5568; }
    </style>
  </defs>

  <rect width="960" height="260" fill="#FFFFFF" rx="8"/>

  <!-- Emblem Shield (x=30, y=30, 200x200) -->
  <g transform="translate(30, 30)">
    <rect x="0" y="0" width="200" height="200" rx="26" fill="#0052A5"/>
    <rect x="0" y="180" width="200" height="20" rx="8" fill="#D4213D"/>

    <!-- Medical Cross Top-Right -->
    <rect x="145" y="34" width="30" height="10" rx="2" fill="#FFFFFF"/>
    <rect x="155" y="24" width="10" height="30" rx="2" fill="#FFFFFF"/>

    <!--AED Heart Center -->
    <path d="M 95 152
             C 95 152, 34 112, 34 70
             C 34 46, 54 32, 74 32
             C 86 32, 95 40, 95 48
             C 95 40, 104 32, 116 32
             C 136 32, 156 46, 156 70
             C 156 112, 95 152, 95 152 Z"
          fill="#D4213D" stroke="#FFFFFF" stroke-width="5" stroke-linejoin="round"/>

    <!-- Open Data Impulse / ECG Waveform -->
    <polyline points="26,102 66,102 82,62 98,136 114,84 126,102 168,102"
              fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>

    <!-- Connected Open Data Nodes -->
    <circle cx="26" cy="102" r="9" fill="#059669" stroke="#FFFFFF" stroke-width="3.5"/>
    <circle cx="168" cy="102" r="9" fill="#059669" stroke="#FFFFFF" stroke-width="3.5"/>
  </g>

  <!-- Campaign Lockup Typography -->
  <text x="268" y="68" class="kicker">OGÓLNOPOLSKA AKCJA DANE.GOV.PL | MISJA AED</text>
  <text x="266" y="128" class="title">IMPULS DLA DANYCH</text>
  <text x="268" y="168" class="sub">Otwórz dane o AED. Ocal cenne minuty życia.</text>
  <text x="268" y="204" class="slogan">„Zamknięta wiedza nie ratuje życia. Udostępnij lokalizację swojego AED w portalu dane.gov.pl.”</text>
</svg>
"""


def generate_logo_files() -> None:
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DELIV_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Open vector format (.svg)
    svg_content = generate_logo_svg()
    (LOGO_DIR / "logotyp_misja_aed.svg").write_text(svg_content, encoding="utf-8")
    (PUBLIC_DELIV_DIR / "logotyp_misja_aed.svg").write_text(svg_content, encoding="utf-8")

    # 2. High-res PNG (transparent & white card), JPG, and PDF
    W, H = 1800, 520
    img_rgba = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img_rgba)
    draw.rectangle([0, 0, W - 1, H - 1], fill="#FFFFFF", outline="#D5DCE2", width=2)
    draw_full_lockup(draw, 80, 95, emblem_size=330, variant="color", show_slogan=True)

    png_path = LOGO_DIR / "logotyp_misja_aed.png"
    jpg_path = LOGO_DIR / "logotyp_misja_aed.jpg"
    pdf_path = LOGO_DIR / "logotyp_misja_aed.pdf"

    img_rgba.save(png_path, format="PNG")
    img_rgb = img_rgba.convert("RGB")
    img_rgb.save(jpg_path, format="JPEG", quality=96)
    img_rgb.save(pdf_path, format="PDF", resolution=150.0)

    for p in (png_path, jpg_path, pdf_path):
        shutil.copy2(p, PUBLIC_DELIV_DIR / p.name)


def _new_a4_landscape() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    # 16:9 / A4 landscape high-res page (1920 x 1080)
    img = Image.new("RGB", (1920, 1080), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    return img, draw


def _draw_page_frame(
    draw: ImageDraw.ImageDraw,
    *,
    section_kicker: str,
    page_title: str,
    page_num: int,
    total_pages: int,
    doc_label: str,
) -> None:
    # Top gov.pl bar
    draw.rectangle([0, 0, 1920, 96], fill="#FFFFFF")
    draw.rectangle([0, 94, 1920, 98], fill="#D4213D")

    draw_campaign_emblem(draw, 64, 18, 58, variant="color")
    draw.text((138, 22), "gov.pl | Ministerstwo Cyfryzacji | dane.gov.pl", font=get_font(15, "bold"), fill="#4A5568")
    draw.text((138, 46), doc_label, font=get_font(22, "bold"), fill="#1B1B1B")

    draw.text(
        (1620, 36),
        f"Strona {page_num} z {total_pages}",
        font=get_font(16, "bold"),
        fill="#4A5568",
    )

    # Section title header
    draw.text((64, 124), section_kicker.upper(), font=get_font(15, "bold"), fill="#D4213D")
    draw.text((64, 148), page_title, font=get_font(36, "black"), fill="#1B1B1B")
    draw.rectangle([64, 202, 1856, 204], fill="#D5DCE2")

    # Bottom footer
    draw.rectangle([0, 1030, 1920, 1080], fill="#F4F6F8")
    draw.rectangle([0, 1030, 1920, 1032], fill="#D5DCE2")
    draw.text(
        (64, 1046),
        "Krajowy Rejestr AED | Kampania społeczna „Impuls dla Danych” (Misja AED - Dane na ratunek) | Licencja CC0-1.0",
        font=get_font(14, "regular"),
        fill="#4A5568",
    )


def generate_brand_book_pdf() -> None:
    pages: list[Image.Image] = []
    total_pages = 4
    doc_label = "KSIĘGA ZNAKU AKCJI SPOŁECZNEJ „IMPULS DLA DANYCH” (MISJA AED)"

    # ---------------- PAGE 1: NAZWA, HASŁO I OPIS KONCEPCJI (4 ZDANIA) ----------------
    img1, d1 = _new_a4_landscape()
    _draw_page_frame(
        d1,
        section_kicker="1. Identyfikacja akcji i idea kreatywna",
        page_title="Nazwa akcji, hasło przewodnie oraz opis koncepcji znaku",
        page_num=1,
        total_pages=total_pages,
        doc_label=doc_label,
    )

    # Logo showcase box
    d1.rounded_rectangle([64, 230, 1856, 510], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
    draw_full_lockup(d1, 120, 265, emblem_size=210, variant="color", show_slogan=True)

    # Left card: Nazwa i Hasło Akcji
    d1.rounded_rectangle([64, 540, 936, 995], radius=6, fill="#F4F6F8", outline="#D5DCE2", width=2)
    d1.text((96, 572), "NAZWA AKCJI SPOŁECZNEJ", font=get_font(15, "bold"), fill="#D4213D")
    d1.text((96, 600), "IMPULS DLA DANYCH — MISJA AED", font=get_font(28, "black"), fill="#1B1B1B")

    d1.text((96, 660), "HASŁO GŁÓWNE KAMPANII", font=get_font(15, "bold"), fill="#0052A5")
    draw_wrapped_text(
        d1,
        "„Zamknięta wiedza nie ratuje życia. Otwórz dane o swoim AED w portalu dane.gov.pl.”",
        96,
        690,
        get_font(22, "bold"),
        790,
        fill="#1B1B1B",
        line_spacing=10,
    )

    d1.text((96, 785), "GRUPA DOCELOWA (DYSPONENCI DANYCH)", font=get_font(15, "bold"), fill="#4A5568")
    draw_wrapped_text(
        d1,
        "Samorządy terytorialne (urzędy miast i gmin), zarządcy obiektów użyteczności publicznej, dworców, sądów, uczelni, centrów handlowych, jednostki OSP/PSP oraz firmy prywatne posiadające defibrylatory AED.",
        96,
        815,
        get_font(18, "regular"),
        790,
        fill="#1B1B1B",
        line_spacing=8,
    )

    # Right card: Opis koncepcji (strictly 4 sentences — requirement: 3-5 sentences!)
    d1.rounded_rectangle([984, 540, 1856, 995], radius=6, fill="#FFFFFF", outline="#0052A5", width=2)
    d1.text((1016, 572), "OPIS KONCEPCJI ZNAKU (4 ZDANIA — WYMÓG 3-5 ZDAŃ)", font=get_font(15, "bold"), fill="#0052A5")

    concept_sentences = (
        "1. Koncepcja znaku łączy międzynarodowy symbol defibrylatora AED (serce oraz impuls elektryczny EKG) z otwartą strukturą węzłów sieciowych tworzących rejestr danych publicznych. "
        "2. Sygnet obrazuje transformację rozproszonych, zamkniętych na klucz informacji w jeden otwarty, publiczny impuls ratujący życie w pierwszych, decydujących minutach nagłego zatrzymania krążenia. "
        "3. Kontrastowa kolorystyka spaja czerwień ratunkową oraz narodowy karmazyn z instytucjonalnym granatem portalu dane.gov.pl i szmaragdową zielenią potwierdzonej dostępności urządzenia 24/7. "
        "4. Prosta, geometryczna konstrukcja gwarantuje natychmiastową rozpoznawalność i czytelność zarówno w aplikacjach mobilnych służb ratowniczych, jak i w materiałach promocyjnych skierowanych do samorządów oraz instytucji."
    )
    draw_wrapped_text(
        d1,
        concept_sentences,
        1016,
        612,
        get_font(19, "regular"),
        800,
        fill="#1B1B1B",
        line_spacing=12,
    )
    pages.append(img1)

    # ---------------- PAGE 2: POLE OCHRONNE I KONSTRUKCJA ZNAKU ----------------
    img2, d2 = _new_a4_landscape()
    _draw_page_frame(
        d2,
        section_kicker="2. Budowa geometryczna i pole ochronne znaku",
        page_title="Siatka konstrukcyjna oraz pole ochronne (moduł X)",
        page_num=2,
        total_pages=total_pages,
        doc_label=doc_label,
    )

    # Left panel: Protective field diagram
    d2.rounded_rectangle([64, 230, 1140, 995], radius=6, fill="#F4F6F8", outline="#D5DCE2", width=2)
    d2.text((96, 260), "SCHEMAT POLA OCHRONNEGO (MODUŁ X = 1/4 WYSOKOŚCI SYGNETU H)", font=get_font(16, "bold"), fill="#0052A5")

    # Outer protective boundary box
    px, py, pw, ph = 140, 340, 920, 440
    margin_x = 70  # module X
    d2.rectangle([px, py, px + pw, py + ph], fill="#EBF3FA", outline="#0052A5", width=2)
    # Inner safe zone (logo bounding box)
    ix, iy, iw, ih = px + margin_x, py + margin_x, pw - 2 * margin_x, ph - 2 * margin_x
    d2.rectangle([ix, iy, ix + iw, iy + ih], fill="#FFFFFF", outline="#D4213D", width=2)

    # Draw logo inside inner safe box
    draw_full_lockup(d2, ix + 36, iy + 78, emblem_size=135, variant="color", show_slogan=False)

    # Dimension labels for X
    x_font = get_font(18, "bold")
    d2.text((px + pw // 2 - 10, py + 22), "X", font=x_font, fill="#0052A5")
    d2.text((px + pw // 2 - 10, iy + ih + 22), "X", font=x_font, fill="#0052A5")
    d2.text((px + 25, py + ph // 2 - 10), "X", font=x_font, fill="#0052A5")
    d2.text((ix + iw + 25, py + ph // 2 - 10), "X", font=x_font, fill="#0052A5")

    draw_wrapped_text(
        d2,
        "Zasada pola ochronnego: Wokół logotypu oraz sygnetu obowiązuje strefa buforowa o szerokości X (gdzie X wynosi 25% wysokości tarczy sygnetu H). W polu ochronnym nie wolno umieszczać żadnych tekstów, krawędzi innych grafik ani elementów interfejsu.",
        96,
        825,
        get_font(18, "regular"),
        1000,
        fill="#1B1B1B",
        line_spacing=8,
    )

    # Right panel: Construction proportions
    d2.rounded_rectangle([1180, 230, 1856, 995], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
    d2.text((1212, 260), "ZASADY KONSTRUKCYJNE", font=get_font(16, "bold"), fill="#1B1B1B")

    rules = [
        ("Moduł bazowy (X)", "Podstawową jednostką miar znaku jest moduł X równy 1/4 wysokości tarczy sygnetu (H = 4X)."),
        ("Proporcje sygnetu", "Sygnet wpisany jest w kwadrat o proporcjach 4X na 4X z zaokrągleniem narożników R = 0.5X oraz dolną belką w kolorze karmazynu narodowego o wysokości 0.4X."),
        ("Odstęp logotypu", "Odległość między prawą krawędzią sygnetu a lewą krawędzią typografii wynosi dokładnie 1X."),
        ("Wersje układu", "Podstawową wersją znaku jest układ poziomy (sygnet + logotyp). W ikonach aplikacji mobilnych, faviconach oraz znacznikach mapy dopuszcza się samodzielne stosowanie sygnetu."),
    ]
    ry = 310
    for title_r, body_r in rules:
        d2.text((1212, ry), title_r, font=get_font(20, "bold"), fill="#0052A5")
        ry += 32
        ry = draw_wrapped_text(d2, body_r, 1212, ry, get_font(17, "regular"), 610, fill="#4A5568", line_spacing=7)
        ry += 24

    pages.append(img2)

    # ---------------- PAGE 3: KOLORYSTYKA I WERSJE MONOCHROMATYCZNE ----------------
    img3, d3 = _new_a4_landscape()
    _draw_page_frame(
        d3,
        section_kicker="3. Kolorystyka oficjalna i warianty tła",
        page_title="Paleta barw (HEX, RGB, CMYK) oraz wersje monochromatyczne",
        page_num=3,
        total_pages=total_pages,
        doc_label=doc_label,
    )

    swatches = [
        ("Granat Instytucjonalny dane.gov.pl", "#0052A5", "RGB: 0, 82, 165", "CMYK: 100, 68, 0, 12", "Tarcza sygnetu, akcenty główne i nawigacja portalu", "#FFFFFF"),
        ("Karmazyn Narodowy / Czerwień AED", "#D4213D", "RGB: 212, 33, 61", "CMYK: 10, 96, 75, 2", "Symbol serca AED, dolna belka gov.pl, alarm ratunkowy", "#FFFFFF"),
        ("Szmaragd Potwierdzonej Dostępności", "#059669", "RGB: 5, 150, 105", "CMYK: 86, 12, 68, 2", "Węzły otwartych danych, status urządzenia sprawnego 24/7", "#FFFFFF"),
        ("Grafit Typograficzny (WCAG AAA)", "#1B1B1B", "RGB: 27, 27, 27", "CMYK: 72, 66, 65, 80", "Logotyp główny, nagłówki i wersja monochromatyczna czarna", "#FFFFFF"),
        ("Szarość Instytucjonalna Tła", "#F4F6F8", "RGB: 244, 246, 248", "CMYK: 4, 2, 2, 0", "Tło sekcji informacyjnych i kart ewidencyjnych AED", "#1B1B1B"),
    ]

    sx = 64
    sw_w = 342
    for name_s, hex_s, rgb_s, cmyk_s, role_s, text_col in swatches:
        d3.rounded_rectangle([sx, 230, sx + sw_w, 600], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
        d3.rounded_rectangle([sx, 230, sx + sw_w, 380], radius=6, fill=hex_s, outline="#D5DCE2", width=1)
        d3.text((sx + 20, 258), hex_s, font=get_font(28, "black"), fill=text_col)
        draw_wrapped_text(d3, name_s, sx + 20, 312, get_font(15, "bold"), sw_w - 40, fill=text_col, line_spacing=4)
        d3.text((sx + 20, 405), hex_s, font=get_font(18, "bold"), fill="#0052A5")
        d3.text((sx + 20, 435), rgb_s, font=get_font(16, "regular"), fill="#1B1B1B")
        d3.text((sx + 20, 462), cmyk_s, font=get_font(16, "regular"), fill="#1B1B1B")
        draw_wrapped_text(d3, role_s, sx + 20, 502, get_font(15, "regular"), sw_w - 40, fill="#4A5568", line_spacing=5)
        sx += sw_w + 20

    # Bottom row: 3 background variants (podstawowa na jasnym tle, kontrowa na ciemnym tle, monochromatyczna)
    variants = [
        ("Wersja podstawowa (tło jasne #FFFFFF)", "#FFFFFF", "#D5DCE2", "color", "#1B1B1B"),
        ("Wersja na tle ciemnym (#0F172A / #1B1B1B)", "#0F172A", "#0F172A", "dark_bg", "#FFFFFF"),
        ("Wersja monochromatyczna (druk czarno-biały)", "#FFFFFF", "#1B1B1B", "mono_dark", "#1B1B1B"),
    ]
    vx = 64
    vw = 574
    for v_label, v_bg, v_border, v_mode, v_text in variants:
        d3.rounded_rectangle([vx, 640, vx + vw, 995], radius=6, fill=v_bg, outline=v_border, width=2)
        d3.text((vx + 28, 668), v_label, font=get_font(16, "bold"), fill=v_text)
        emblem_mode = "color" if v_mode in ("color", "dark_bg") else "mono_dark"
        draw_campaign_emblem(d3, vx + 30, 725, 130, variant=emblem_mode)
        d3.text((vx + 185, 745), "IMPULS DLA DANYCH", font=get_font(28, "black"), fill=v_text)
        d3.text(
            (vx + 185, 788),
            "Misja AED | Portal dane.gov.pl",
            font=get_font(18, "bold"),
            fill="#059669" if v_mode == "dark_bg" else v_text,
        )
        d3.text(
            (vx + 185, 825),
            "Otwórz dane. Ocal cenne minuty życia.",
            font=get_font(16, "regular"),
            fill=v_text,
        )
        vx += vw + 35

    pages.append(img3)

    # ---------------- PAGE 4: MINIMALNA WIELKOŚĆ I NIEDOZWOLONE WYKORZYSTYWANIE ZNAKU ----------------
    img4, d4 = _new_a4_landscape()
    _draw_page_frame(
        d4,
        section_kicker="4. Minimalna wielkość oraz niedozwolone modyfikacje",
        page_title="Skalowanie minimalne i przykłady niedozwolonego użycia znaku",
        page_num=4,
        total_pages=total_pages,
        doc_label=doc_label,
    )

    # Left column: Minimalna wielkość
    d4.rounded_rectangle([64, 230, 740, 995], radius=6, fill="#F4F6F8", outline="#D5DCE2", width=2)
    d4.text((96, 260), "MINIMALNA WIELKOŚĆ ZNAKU", font=get_font(18, "bold"), fill="#0052A5")

    # Full lockup minimum size preview
    d4.rounded_rectangle([96, 310, 708, 560], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=1)
    d4.text((120, 332), "1. Pełny logotyp (sygnet + logotyp):", font=get_font(17, "bold"), fill="#1B1B1B")
    draw_full_lockup(d4, 120, 375, emblem_size=72, variant="color", show_slogan=False)
    d4.text((120, 472), "Minimalna szerokość w druku: 35 mm (wysokość 9 mm)", font=get_font(16, "bold"), fill="#0052A5")
    d4.text((120, 502), "Minimalna szerokość na ekranie (digital): 140 px (wysokość 36 px)", font=get_font(16, "regular"), fill="#1B1B1B")

    # Standalone emblem minimum size preview
    d4.rounded_rectangle([96, 585, 708, 825], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=1)
    d4.text((120, 608), "2. Samodzielny sygnet (favicon / znacznik mapy / PWA):", font=get_font(17, "bold"), fill="#1B1B1B")
    draw_campaign_emblem(d4, 120, 650, 56, variant="color")
    draw_campaign_emblem(d4, 200, 666, 40, variant="color")
    draw_campaign_emblem(d4, 264, 682, 24, variant="color")
    d4.text((120, 735), "Minimalna wielkość w druku: 8 mm x 8 mm", font=get_font(16, "bold"), fill="#0052A5")
    d4.text((120, 765), "Minimalna wielkość na ekranie (digital): 24 px x 24 px", font=get_font(16, "regular"), fill="#1B1B1B")

    draw_wrapped_text(
        d4,
        "Poniżej wymiaru 36 px wysokości dla pełnego znaku należy stosować wyłącznie samodzielny sygnet bez podtytułu i hasła.",
        96,
        855,
        get_font(16, "regular"),
        610,
        fill="#4A5568",
        line_spacing=6,
    )

    # Right column: 6 Prohibited Uses (Niedozwolone wykorzystywanie znaku)
    d4.rounded_rectangle([780, 230, 1856, 995], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
    d4.text((812, 260), "NIEDOZWOLONE WYKORZYSTYWANIE ZNAKU (ZAKAZY)", font=get_font(18, "bold"), fill="#D4213D")

    prohibited = [
        ("1. Zakaz deformacji i rozciągania proporcji", "deform"),
        ("2. Zakaz samowolnej zmiany kolorystyki", "wrong_colors"),
        ("3. Zakaz umieszczania na niekontrastowym tle", "low_contrast"),
        ("4. Zakaz obracania lub pochylania znaku", "rotate"),
        ("5. Zakaz naruszania pola ochronnego tekstem", "crowded"),
        ("6. Zakaz usuwania linii impulsu lub serca AED", "missing_part"),
    ]

    for idx, (p_title, p_kind) in enumerate(prohibited):
        col = idx % 2
        row = idx // 2
        bx = 812 + col * 515
        by = 310 + row * 218
        bw, bh = 490, 196

        bg_box = "#D4213D" if p_kind == "low_contrast" else "#F4F6F8"
        d4.rounded_rectangle([bx, by, bx + bw, by + bh], radius=6, fill=bg_box, outline="#D4213D", width=2)

        if p_kind == "deform":
            draw_campaign_emblem(d4, bx + 28, by + 24, 88, variant="color", deform_x=1.65)
        elif p_kind == "wrong_colors":
            draw_campaign_emblem(d4, bx + 28, by + 24, 96, variant="wrong_colors")
        elif p_kind == "low_contrast":
            draw_campaign_emblem(d4, bx + 28, by + 24, 96, variant="color")
        elif p_kind == "rotate":
            rot_canvas = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            rot_draw = ImageDraw.Draw(rot_canvas)
            draw_campaign_emblem(rot_draw, 12, 12, 92, variant="color")
            rotated = rot_canvas.rotate(22, resample=Image.Resampling.BICUBIC, expand=False)
            img4.paste(rotated.convert("RGB"), (bx + 24, by + 16))
        elif p_kind == "crowded":
            draw_campaign_emblem(d4, bx + 28, by + 24, 96, variant="color")
            d4.text((bx + 115, by + 48), "TEKST W POLU OCHRONNYM", font=get_font(18, "black"), fill="#D4213D")
        elif p_kind == "missing_part":
            d4.rounded_rectangle([bx + 28, by + 24, bx + 124, by + 120], radius=12, fill="#0052A5")

        # Red diagonal prohibition cross in top-right badge of card
        d4.ellipse([bx + bw - 48, by + 14, bx + bw - 14, by + 48], fill="#D4213D")
        d4.line([bx + bw - 40, by + 22, bx + bw - 22, by + 40], fill="#FFFFFF", width=3)
        d4.line([bx + bw - 40, by + 40, bx + bw - 22, by + 22], fill="#FFFFFF", width=3)

        lbl_color = "#FFFFFF" if p_kind == "low_contrast" else "#1B1B1B"
        draw_wrapped_text(d4, p_title, bx + 24, by + 138, get_font(16, "bold"), bw - 40, fill=lbl_color, line_spacing=4)

    pages.append(img4)

    pdf_out = DELIV_DIR / "Ksiega_Znaku_Misja_AED.pdf"
    pages[0].save(
        pdf_out,
        format="PDF",
        resolution=150.0,
        save_all=True,
        append_images=pages[1:],
    )
    shutil.copy2(pdf_out, PUBLIC_DELIV_DIR / pdf_out.name)
    # Save page 1 preview PNG for embedding/inspection
    pages[0].save(PUBLIC_DELIV_DIR / "ksiega_znaku_preview.png", format="PNG")


def generate_presentation_pdf() -> None:
    slides: list[Image.Image] = []
    total_slides = 7
    doc_label = "PREZENTACJA ROZWIĄZANIA — MISJA AED: DANE NA RATUNEK (DANE.GOV.PL)"

    # ---------------- SLIDE 1: TYTUŁ PROJEKTU, WYZWANIE "3 MARCA" I CEL ----------------
    s1, d1 = _new_a4_landscape()
    _draw_page_frame(
        d1,
        section_kicker="Slajd 1 | Wprowadzenie i cel projektu",
        page_title="Krajowy Rejestr AED oraz akcja „Impuls dla Danych” dla portalu dane.gov.pl",
        page_num=1,
        total_pages=total_slides,
        doc_label=doc_label,
    )
    d1.rounded_rectangle([64, 230, 1140, 610], radius=6, fill="#F4F6F8", outline="#D5DCE2", width=2)
    d1.text((96, 260), "GENEZA WYZWANIA: WARSZAWA, 3 MARCA — LICZY SIĘ KAŻDA MINUTA", font=get_font(16, "bold"), fill="#D4213D")
    draw_wrapped_text(
        d1,
        "Podczas nagłego zatrzymania krążenia u fotografa sejmowego w centrum Warszawy świadkowie szukali defibrylatora. Urządzenia znajdowały się w pobliżu, lecz były zamknięte na klucz lub brakowało zweryfikowanej informacji, gdzie dokładnie wiszą i czy są dostępne w danej minucie.",
        96,
        302,
        get_font(20, "regular"),
        1010,
        fill="#1B1B1B",
        line_spacing=10,
    )
    draw_wrapped_text(
        d1,
        "Nasze rozwiązanie łączy rozproszone bazy samorządowe dane.gov.pl, zasoby OpenStreetMap oraz bezpośrednie zgłoszenia dysponentów w jeden ogólnopolski, odczytywalny maszynowo rejestr (18 319 punktów AED) z weryfikacją dostępności w czasie rzeczywistym.",
        96,
        445,
        get_font(20, "bold"),
        1010,
        fill="#0052A5",
        line_spacing=10,
    )

    # KPI Evidence Box on Slide 1
    d1.rounded_rectangle([1180, 230, 1856, 610], radius=6, fill="#FFFFFF", outline="#0052A5", width=2)
    d1.text((1212, 260), "DOWÓD REALIZACJI — STAN REJESTRU NA ŻYWO", font=get_font(16, "bold"), fill="#0052A5")
    kpis = [
        ("18 319", "Ujednoliconych punktów AED w Polsce"),
        ("162", "Scalone duplikaty przestrzenne (promień 25 m)"),
        ("4 + OSM", "Zintegrowane oficjalne źródła dane.gov.pl i OSM"),
        ("5 formatów", "Maszynowych: GeoJSON, CSV, JSON-LD, XLSX, XML"),
    ]
    ky = 310
    for k_val, k_lbl in kpis:
        d1.text((1212, ky), k_val, font=get_font(30, "black"), fill="#1B1B1B")
        draw_wrapped_text(d1, k_lbl, 1435, ky + 6, get_font(17, "regular"), 395, fill="#4A5568", line_spacing=4)
        ky += 70

    # Campaign lockup banner at bottom of Slide 1
    d1.rounded_rectangle([64, 640, 1856, 995], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
    draw_full_lockup(d1, 110, 690, emblem_size=240, variant="color", show_slogan=True)
    slides.append(s1)

    # ---------------- SLIDE 2: DOWÓD TECHNICZNY 1 - MAPA RATOWNICZA I KARTA AED ----------------
    s2, d2 = _new_a4_landscape()
    _draw_page_frame(
        d2,
        section_kicker="Slajd 2 | Dowód realizacji wymagań technicznych (1/3)",
        page_title="Wyszukiwarka najbliższego otwartego AED, precyzyjny GPS i karta ewidencyjna",
        page_num=2,
        total_pages=total_slides,
        doc_label=doc_label,
    )

    # Visual UI Mockup / Evidence Capture of the Live Portal
    d2.rounded_rectangle([64, 230, 1200, 995], radius=6, fill="#F4F6F8", outline="#D5DCE2", width=2)
    # Simulated browser top bar
    d2.rectangle([64, 230, 1200, 290], fill="#FFFFFF")
    d2.rectangle([64, 288, 1200, 292], fill="#D4213D")
    d2.text((92, 250), "gov.pl | Ministerstwo Cyfryzacji | Krajowy Rejestr AED (http://127.0.0.1:8000)", font=get_font(15, "bold"), fill="#1B1B1B")
    d2.rounded_rectangle([940, 244, 1175, 278], radius=4, fill="#DC2626")
    d2.text((962, 253), "Znajdź najbliższy AED", font=get_font(14, "bold"), fill="#FFFFFF")

    # Search bar & filters inside UI evidence
    d2.rounded_rectangle([92, 312, 1172, 420], radius=4, fill="#FFFFFF", outline="#D5DCE2", width=1)
    d2.text((112, 326), "Adres wyszukiwania: ul. Karola Marcinkowskiego 9, 85-056 Bydgoszcz (GPS +/- 18 m)", font=get_font(16, "bold"), fill="#0052A5")
    d2.text((112, 362), "[x] Otwarte teraz (Europe/Warsaw)   [x] Dostępne 24/7   [x] Tylko ogólnodostępne   [ ] Kapsuły zewnętrzne", font=get_font(15, "regular"), fill="#1B1B1B")

    # Split map + detail card inside UI evidence
    d2.rounded_rectangle([92, 440, 680, 970], radius=4, fill="#E9EEF2", outline="#D5DCE2", width=1)
    d2.text((115, 460), "Interaktywna mapa MapLibre GL (Positron)", font=get_font(16, "bold"), fill="#1B1B1B")
    # Map grid lines & markers
    for gx in range(150, 650, 90):
        d2.line([gx, 500, gx, 950], fill="#DDE3EA", width=1)
    for gy in range(520, 950, 80):
        d2.line([95, gy, 675, gy], fill="#DDE3EA", width=1)
    # Origin pin (blue) & AED pins (red)
    d2.ellipse([360, 690, 390, 720], fill="#0052A5", outline="#FFFFFF", width=3)
    d2.text((398, 696), "Twoja lokalizacja (Marcinkowskiego 9)", font=get_font(14, "bold"), fill="#0052A5")
    for ax, ay, albl in [(310, 630, "33 m (1 min)"), (450, 760, "161 m (2 min)"), (230, 810, "230 m (3 min)")]:
        d2.ellipse([ax - 12, ay - 12, ax + 12, ay + 12], fill="#DC2626", outline="#FFFFFF", width=3)
        d2.text((ax + 18, ay - 8), albl, font=get_font(13, "bold"), fill="#DC2626")

    # Right column inside UI evidence: Karta ewidencyjna AED
    d2.rounded_rectangle([700, 440, 1172, 970], radius=4, fill="#FFFFFF", outline="#0052A5", width=2)
    d2.text((720, 462), "KARTA EWIDENCYJNA AED (33 m | 1 min pieszo)", font=get_font(14, "bold"), fill="#0052A5")
    d2.text((720, 492), "Kujawsko-Pomorskie Centrum Edukacji Nauczycieli", font=get_font(17, "bold"), fill="#1B1B1B")
    card_rows = [
        ("Adres:", "ul. Jagiellońska 9, 85-066 Bydgoszcz"),
        ("Miejsce:", "Wewnątrz budynku, parter (poziom 0)"),
        ("Dostępność:", "Dla klientów i interesantów (Otwarte teraz)"),
        ("Telefon ochrony:", "+48 52 349 31 50"),
        ("Źródło:", "pl_geojson + osm_overpass (Poziom 2)"),
        ("Kompletność:", "80% (Zgodny ze standardem dane.gov.pl)"),
    ]
    cry = 540
    for ck, cv in card_rows:
        d2.text((720, cry), ck, font=get_font(14, "bold"), fill="#4A5568")
        draw_wrapped_text(d2, cv, 855, cry, get_font(14, "regular"), 300, fill="#1B1B1B", line_spacing=4)
        cry += 54

    # Right explanation column on Slide 2
    d2.rounded_rectangle([1235, 230, 1856, 995], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
    d2.text((1267, 260), "KLUCZOWE MECHANIZMY RATOWNICZE", font=get_font(17, "bold"), fill="#0052A5")
    mech = [
        ("Rozwiązanie problemu „zamkniętych drzwi”", "Filtr „Otwarte teraz” analizuje reguły czasowe OpenStreetMap w strefie czasowej Europe/Warsaw oraz flagę 24/7, odrzucając niedostępne nocą biura."),
        ("Wieloetapowa precyzja GPS + korekta na mapie", "Algorytm watchPosition wybiera odczyt o najniższym błędzie (+/- m), odpytuje Nominatim o dokładny adres ulicy i pozwala przeciągnąć niebieski znacznik na konkretny budynek."),
        ("Automatyczne wzbogacanie kart AED", "Nawet jeśli surowy punkt OSM nie posiadał tagów addr:street, backend automatycznie rozwiązuje i zapisuje nazwę obiektu, ulicę, kod pocztowy, piętro, telefon i zdjęcie."),
        ("Dostępność cyfrowa WCAG 2.1 AA/AAA", "Przełącznik wysokiego kontrastu (czarno-żółto-biały tryb AAA), powiększanie czcionki A/A+ oraz pełna nawigacja klawiaturą i responsywność mobilna."),
    ]
    my = 310
    for mt, mb in mech:
        d2.text((1267, my), mt, font=get_font(18, "bold"), fill="#1B1B1B")
        my += 28
        my = draw_wrapped_text(d2, mb, 1267, my, get_font(16, "regular"), 555, fill="#4A5568", line_spacing=6)
        my += 24
    slides.append(s2)

    # ---------------- SLIDE 3: DOWÓD TECHNICZNY 2 - KONSOLA HARVESTERA I ŹRÓDŁA ----------------
    s3, d3 = _new_a4_landscape()
    _draw_page_frame(
        d3,
        section_kicker="Slajd 3 | Dowód realizacji wymagań technicznych (2/3)",
        page_title="Integracja rozproszonych źródeł ze wskazaniem ich zakresu referencyjnego",
        page_num=3,
        total_pages=total_slides,
        doc_label=doc_label,
    )

    d3.text(
        (64, 224),
        "Porównanie zakresu referencyjnego zintegrowanych źródeł danych oraz wyniki 25-metrowej deduplikacji przestrzennej:",
        font=get_font(19, "bold"),
        fill="#1B1B1B",
    )

    # Table of sources & reference scopes
    headers_s3 = ["Źródło danych / Dysponent", "Format", "Współrzędne i Adres", "Opis miejsca i Dostęp", "Godziny i Status", "Wynik harmonizacji"]
    col_x = [64, 480, 680, 1020, 1340, 1610]
    d3.rectangle([64, 265, 1856, 318], fill="#0052A5")
    for cx_i, h_text in zip(col_x, headers_s3):
        d3.text((cx_i + 12, 282), h_text, font=get_font(15, "bold"), fill="#FFFFFF")

    rows_s3 = [
        ("Wzorcowy Standard dane.gov.pl (Cel)", "XLSX / CSV / GeoJSON / JSON-LD / XML", "WGS84 + Ulica + Miasto + Kod + TERYT", "Wymagany opis (>=10 zn.) + access_type + indoor + piętro", "is_24_7 + opening_hours + status + telefon ochrony", "100% (18 atrybutów kanonicznych)"),
        ("Ogólnopolski zbiór OSM (PL.geojson)", "GeoJSON (18 291 pkt)", "WGS84 (100%), Adres uzupełniany przez Nominatim", "94.4% opis miejsca, 92.5% zasady dostępu, 87.3% indoor", "37.1% godziny otwarcia, 32.7% data weryfikacji", "18 291 rekordów bazowych"),
        ("UM Legionowo (api.dane.gov.pl)", "CSV (oficjalny rejestr)", "WGS84 + Ulica + Kod pocztowy + TERYT SIMC", "Nazwa obiektu użyteczności publicznej (public)", "Brak godzin w CSV (uzupełniane przy scalaniu z OSM)", "Pobrano i zharmonizowano (Tier 1)"),
        ("UM Krosno (api.dane.gov.pl)", "CSV (oficjalny rejestr)", "WGS84 + Adres z kodem pocztowym", "Kolumny Lokalizacja + Nazwa obiektu (public)", "Status operational, data synchronizacji", "Pobrano i zharmonizowano (Tier 1)"),
        ("UM Marki (api.dane.gov.pl)", "CSV (oficjalny rejestr)", "Automatyczna korekta odwróconych osi X/Y + Adres", "Kolumny Lokalizacja + Nazwa obiektu (public)", "Status operational, data synchronizacji", "Pobrano i zharmonizowano (Tier 1)"),
        ("UM Przemyśl (open-data GeoJSON)", "GeoJSON (oficjalny)", "Point WGS84 + street + home_number + postcode", "Nazwa i numer ewidencyjny AED (public)", "Status operational, data synchronizacji", "Łącznie 74 pkt miejskie (46 scalonych)"),
        ("OpenStreetMap Overpass / Zgłoszenia", "REST API / Formularz", "Walidacja granic Polski + podpowiadanie adresu", "Wymagany dokładny opis montażu + piętro", "Pełny harmonogram 24/7 + weryfikacja terenowa", "116 scalonych duplikatów w Bydgoszczy"),
    ]

    ry = 318
    for idx_r, r_vals in enumerate(rows_s3):
        bg_r = "#F4F6F8" if idx_r % 2 == 1 else "#FFFFFF"
        if idx_r == 0:
            bg_r = "#EBF3FA"
        d3.rectangle([64, ry, 1856, ry + 78], fill=bg_r, outline="#D5DCE2", width=1)
        for c_i, val_text in enumerate(r_vals):
            max_w = (col_x[c_i + 1] if c_i + 1 < len(col_x) else 1856) - col_x[c_i] - 20
            f_cell = get_font(14, "bold" if (c_i == 0 or idx_r == 0) else "regular")
            draw_wrapped_text(d3, val_text, col_x[c_i] + 12, ry + 12, f_cell, max_w, fill="#1B1B1B", line_spacing=4)
        ry += 78

    # Bottom summary of machine-readable exports
    d3.rounded_rectangle([64, 885, 1856, 995], radius=6, fill="#FFFFFF", outline="#059669", width=2)
    d3.text((92, 902), "FORMATY ODCZYTYWALNE MASZYNOWO DLA HARVESTERA DANE.GOV.PL (NAGŁÓWKI ETAG + 304 NOT MODIFIED + CC0-1.0):", font=get_font(15, "bold"), fill="#059669")
    d3.text(
        (92, 938),
        "1. GET /api/v1/export.geojson (3 gwiazdki)   |   2. GET /api/v1/export.csv (UTF-8 BOM, 3 gwiazdki)   |   3. GET /api/v1/export.jsonld (DCAT-AP, 4 gwiazdki)   |   4. GET /api/v1/standard.xlsx   |   5. GET /api/v1/harvester/dane-gov.xml",
        font=get_font(16, "bold"),
        fill="#1B1B1B",
    )
    slides.append(s3)

    # ---------------- SLIDE 4: DOWÓD TECHNICZNY 3 - WZORCOWY ZAKRES DANYCH (.XLSX) ----------------
    s4, d4 = _new_a4_landscape()
    _draw_page_frame(
        d4,
        section_kicker="Slajd 4 | Dowód realizacji wymagań technicznych (3/3)",
        page_title="Wzorcowy zakres danych o defibrylatorach AED (tabela .xlsx + algorytm 0-100%)",
        page_num=4,
        total_pages=total_slides,
        doc_label=doc_label,
    )

    d4.text(
        (64, 222),
        "Plik Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx (3 arkusze: Specyfikacja 18 pól, Zakres źródeł, Szablon dla dysponenta):",
        font=get_font(18, "bold"),
        fill="#0052A5",
    )

    sx_cols = [64, 125, 380, 680, 860, 1060, 1210]
    sx_headers = ["Lp.", "Pole techniczne", "Nazwa atrybutu (PL)", "Typ danych", "Wymagalność", "Waga", "Znaczenie dla ratowania życia i standardu dane.gov.pl"]
    d4.rectangle([64, 258, 1856, 304], fill="#0052A5")
    for cx_i, h_t in zip(sx_cols, sx_headers):
        d4.text((cx_i + 8, 272), h_t, font=get_font(14, "bold"), fill="#FFFFFF")

    ry = 304
    for idx_f, spec_row in enumerate(STANDARD_FIELDS_SPEC[:15]):
        lp, tech, name_pl, dtype, req, weight, _fmt, desc_pl, _ex = spec_row
        bg_f = "#F4F6F8" if idx_f % 2 == 1 else "#FFFFFF"
        d4.rectangle([64, ry, 1856, ry + 44], fill=bg_f, outline="#D5DCE2", width=1)
        vals = [lp, tech, name_pl, dtype, req, weight, desc_pl]
        for c_i, v_t in enumerate(vals):
            max_w = (sx_cols[c_i + 1] if c_i + 1 < len(sx_cols) else 1856) - sx_cols[c_i] - 14
            f_c = get_font(13, "bold" if c_i in (1, 5) else "regular")
            col_c = "#0052A5" if c_i == 1 else "#1B1B1B"
            one_line = wrap_text(d4, v_t, f_c, max_w)[0] if v_t else ""
            d4.text((sx_cols[c_i] + 8, ry + 13), one_line, font=f_c, fill=col_c)
        ry += 44

    d4.text(
        (64, 975),
        "+ pola rozszerzone: phone (telefon do ochrony/portierni), level (piętro), primary_source (pełna tabela 18 pól w załączonym pliku .xlsx).",
        font=get_font(15, "bold"),
        fill="#4A5568",
    )
    slides.append(s4)

    # ---------------- SLIDE 5: OPIS FUNKCJONALNOŚCI I KROKI UŻYTKOWNIKA ----------------
    s5, d5 = _new_a4_landscape()
    _draw_page_frame(
        d5,
        section_kicker="Slajd 5 | Opis funkcjonalności i ścieżki użytkowników",
        page_title="Kroki użytkownika: 1. Świadek zdarzenia / Ratownik  |  2. Dysponent danych AED",
        page_num=5,
        total_pages=total_slides,
        doc_label=doc_label,
    )

    # Path 1: Emergency Responder / Bystander
    d5.rounded_rectangle([64, 230, 936, 995], radius=6, fill="#FFFFFF", outline="#D4213D", width=2)
    d5.rectangle([64, 230, 936, 286], fill="#D4213D")
    d5.text((92, 248), "ŚCIEŻKA 1: ŚWIADEK ZDARZENIA / SŁUŻBY RATOWNICZE (TRYB NAGŁY)", font=get_font(16, "bold"), fill="#FFFFFF")

    steps_1 = [
        ("Krok 1: Uruchomienie lokalizacji jednym kliknięciem", "Użytkownik klika czerwony przycisk „Znajdź najbliższy AED” w nagłówku gov.pl lub wpisuje adres ulicy (np. ul. Marcinkowskiego 9, Bydgoszcz)."),
        ("Krok 2: Precyzyjne domierzenie GPS lub wskazanie budynku", "System pobiera najdokładniejszy sygnał GPS (+/- m), odpytuje Nominatim o ulicę i pozwala jednym ruchem przesunąć niebieski znacznik na właściwy budynek."),
        ("Krok 3: Filtrowanie urządzeń faktycznie dostępnych („Otwarte teraz”)", "Lista po prawej stronie sortuje AED według dystansu w metrach i czasu biegu/marszu (np. 33 m — 1 min), odfiltrowując urządzenia zamknięte po godzinach pracy."),
        ("Krok 4: Odczyt dokładnego miejsca montażu i nawigacja", "Kliknięcie punktu otwiera Kartę Ewidencyjną AED z opisem (np. „Parter, hol główny przy portierni”), piętrem, zdjęciem, telefonem do ochrony i przyciskiem „Wyznacz trasę pieszą”."),
    ]
    sy1 = 315
    for st_title, st_desc in steps_1:
        d5.text((92, sy1), st_title, font=get_font(19, "bold"), fill="#D4213D")
        sy1 += 30
        sy1 = draw_wrapped_text(d5, st_desc, 92, sy1, get_font(17, "regular"), 810, fill="#1B1B1B", line_spacing=7)
        sy1 += 26

    # Path 2: Data Owner / Municipality / Citizen Contributor
    d5.rounded_rectangle([984, 230, 1856, 995], radius=6, fill="#FFFFFF", outline="#0052A5", width=2)
    d5.rectangle([984, 230, 1856, 286], fill="#0052A5")
    d5.text((1012, 248), "ŚCIEŻKA 2: DYSPONENT DANYCH / SAMORZĄD (AKCJA „IMPULS DLA DANYCH”)", font=get_font(16, "bold"), fill="#FFFFFF")

    steps_2 = [
        ("Krok 1: Pobranie wzorcowego szablonu (.xlsx) lub otwarcie formularza", "Dysponent pobiera plik Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx z arkuszem szablonu lub przechodzi do zakładki „Zgłoś lub zweryfikuj AED”."),
        ("Krok 2: Wskazanie wejścia na mapie i walidacja kompletności na żywo", "Kliknięcie budynku na mapie automatycznie uzupełnia współrzędne WGS84 oraz adres ulicy. Pasek gotowości dane.gov.pl na żywo liczy wynik kompletności (0-100%)."),
        ("Krok 3: Automatyczna deduplikacja przestrzenna w promieniu 25 m", "Po wysłaniu zgłoszenia lub wgraniu pliku JSON/GeoJSON silnik PostGIS/SQLite sprawdza promień 25 m. Jeśli AED już istnieje, wzbogaca rekord zamiast tworzyć duplikat."),
        ("Krok 4: Publikacja w kanałach harvestera dane.gov.pl", "Zwalidowany rekord jest natychmiast widoczny na mapie oraz w eksportach maszynowych GeoJSON, CSV, DCAT-AP JSON-LD i XML dla portalu dane.gov.pl."),
    ]
    sy2 = 315
    for st_title, st_desc in steps_2:
        d5.text((1012, sy2), st_title, font=get_font(19, "bold"), fill="#0052A5")
        sy2 += 30
        sy2 = draw_wrapped_text(d5, st_desc, 1012, sy2, get_font(17, "regular"), 810, fill="#1B1B1B", line_spacing=7)
        sy2 += 26

    slides.append(s5)

    # ---------------- SLIDE 6: KAMPANIA SPOŁECZNA, LOGOTYP I KSIĘGA ZNAKU ----------------
    s6, d6 = _new_a4_landscape()
    _draw_page_frame(
        d6,
        section_kicker="Slajd 6 | Kampania promocyjna zachęcająca dysponentów (25% oceny)",
        page_title="Akcja „Impuls dla Danych”: logotyp, hasło i wytyczne z Księgi Znaku",
        page_num=6,
        total_pages=total_slides,
        doc_label=doc_label,
    )

    d6.rounded_rectangle([64, 230, 1856, 480], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
    draw_full_lockup(d6, 105, 255, emblem_size=195, variant="color", show_slogan=True)

    # 3 summary cards below: Concept, Parameters (clear space/min size/colors), Deliverables
    cards_s6 = [
        (
            "Koncepcja i potencjał promocyjny",
            "Znak spaja medyczny symbol serca i impulsu defibrylacji z otwartymi węzłami danych dane.gov.pl. Hasło „Zamknięta wiedza nie ratuje życia” bezpośrednio nawiązuje do problemu zamkniętych lub niezgłoszonych defibrylatorów i motywuje urzędy, zarządców budynków oraz firmy do dzielenia się danymi.",
        ),
        (
            "Podsumowanie Księgi Znaku (.pdf)",
            "1. Kolorystyka: Granat dane.gov.pl (#0052A5), Karmazyn (#D4213D), Szmaragd dostępności (#059669), Grafit (#1B1B1B).\n2. Pole ochronne: Moduł X = 1/4 wysokości sygnetu wokół znaku.\n3. Minimalna wielkość: 140 px / 35 mm (pełny znak), 24 px / 8 mm (sygnet).\n4. Zakazy: 6 skatalogowanych niedozwolonych modyfikacji.",
        ),
        (
            "Dostarczone pliki otwarte i produkcyjne",
            "Wszystkie wymagane formaty znajdują się w repozytorium (katalog deliverables/) oraz są dostępne do pobrania bezpośrednio w interfejsie portalu:\n- logotyp_misja_aed.svg (format otwarty wektorowy)\n- logotyp_misja_aed.png / .jpg / .pdf\n- Ksiega_Znaku_Misja_AED.pdf",
        ),
    ]
    cx6 = 64
    cw6 = 574
    for c_title, c_body in cards_s6:
        d6.rounded_rectangle([cx6, 515, cx6 + cw6, 995], radius=6, fill="#F4F6F8", outline="#D5DCE2", width=2)
        d6.text((cx6 + 28, 545), c_title, font=get_font(20, "bold"), fill="#0052A5")
        cy6 = 595
        for para in c_body.split("\n"):
            cy6 = draw_wrapped_text(d6, para, cx6 + 28, cy6, get_font(17, "regular"), cw6 - 56, fill="#1B1B1B", line_spacing=8)
            cy6 += 8
        cx6 += cw6 + 35

    slides.append(s6)

    # ---------------- SLIDE 7: LISTA EWENTUALNYCH OGRANICZEŃ I KIERUNKI ROZWOJU ----------------
    s7, d7 = _new_a4_landscape()
    _draw_page_frame(
        d7,
        section_kicker="Slajd 7 | Transparentna analiza ograniczeń i rozwój systemu",
        page_title="Lista zidentyfikowanych ograniczeń technicznych i operacyjnych oraz sposoby mitygacji",
        page_num=7,
        total_pages=total_slides,
        doc_label=doc_label,
    )

    limitations = [
        (
            "1. Brak pełnych adresów administracyjnych w surowych węzłach OpenStreetMap (99.2% punktów bez tagu addr:street)",
            "Ograniczenie: Społeczność OSM oznacza defibrylatory jako pojedyncze punkty (node) wewnątrz obrysów budynków bez powielania nazwy ulicy i kodu pocztowego.\nMitygacja w projekcie: Wdrożyliśmy automatyczne, zapisywane w bazie geokodowanie odwrotne (OpenStreetMap Nominatim), które przy pierwszym otwarciu lub wyszukaniu punktu uzupełnia nazwę instytucji, ulicę, numer budynku oraz kod pocztowy.",
        ),
        (
            "2. Niedokładność geolokalizacji IP/Wi-Fi na komputerach stacjonarnych bez modułu GPS",
            "Ograniczenie: Przeglądarki na komputerach stacjonarnych i laptopach (szczególnie przy łączach mobilnych lub VPN) potrafią zwrócić lokalizację węzła operatora ISP oddaloną o dziesiątki kilometrów.\nMitygacja w projekcie: Zastosowaliśmy wielopróbkowe próbkowanie watchPosition z oceną błędu (+/- m), ostrzeżenie o niskiej precyzji sieciowej oraz interaktywny, przeciągalny znacznik „Twoja lokalizacja” na mapie.",
        ),
        (
            "3. Niejednolite kodowanie i błędy współrzędnych w plikach CSV publikowanych przez samorządy",
            "Ograniczenie: Część miejskich zbiorów w dane.gov.pl posiada zamienione miejscami kolumny długości i szerokości geograficznej (np. UM Marki) lub podwójnie zagnieżdżone cudzysłowy CSV.\nMitygacja w projekcie: Konektor dane_gov_municipal automatycznie wykrywa i koryguje orientację osi X/Y względem granic Polski (49-55 N, 14-24.5 E) oraz oczyszcza strukturę CSV.",
        ),
        (
            "4. Brak bezpośredniej telemetrii IoT o stanie baterii i elektrod z fizycznych kapsuł AED",
            "Ograniczenie: Większość zainstalowanych w Polsce defibrylatorów nie posiada łączności sieciowej raportującej zużycie baterii lub przeterminowanie elektrod w czasie rzeczywistym.\nMitygacja w projekcie: Wprowadziliśmy kryterium świeżości weryfikacji (365 dni) w algorytmie kompletności oraz szybki formularz terenowej weryfikacji i zgłaszania usterek przez służby ratownicze i obywateli.",
        ),
    ]

    ly = 230
    for lim_title, lim_body in limitations:
        d7.rounded_rectangle([64, ly, 1856, ly + 176], radius=6, fill="#FFFFFF", outline="#D5DCE2", width=2)
        d7.text((92, ly + 18), lim_title, font=get_font(19, "bold"), fill="#D4213D")
        cy_l = ly + 52
        for line_p in lim_body.split("\n"):
            cy_l = draw_wrapped_text(d7, line_p, 92, cy_l, get_font(16, "regular"), 1730, fill="#1B1B1B", line_spacing=6)
            cy_l += 4
        ly += 192

    slides.append(s7)

    pres_out = DELIV_DIR / "Prezentacja_Misja_AED.pdf"
    slides[0].save(
        pres_out,
        format="PDF",
        resolution=150.0,
        save_all=True,
        append_images=slides[1:],
    )
    shutil.copy2(pres_out, PUBLIC_DELIV_DIR / pres_out.name)


def generate_project_description() -> None:
    md_content = """# Szczegółowy Opis i Tytuł Projektu

## Tytuł projektu
**Krajowy Rejestr AED oraz Kampania Społeczna „Impuls dla Danych” — Ogólnopolski Hub Otwartych Danych o Defibrylatorach dla Portalu dane.gov.pl (Misja AED: Dane na ratunek)**

---

## 1. Streszczenie i odpowiedź na wyzwanie „3 marca”
Tragiczne wydarzenia z 3 marca w centrum Warszawy (nagłe zatrzymanie krążenia u fotografa sejmowego przy braku szybkiej informacji o tym, które pobliskie defibrylatory AED są faktycznie otwarte, a które zamknięte na klucz) ukazały krytyczną lukę w krajowej infrastrukturze informacji ratowniczej. Dane o defibrylatorach w Polsce są rozproszone pomiędzy częściowe wykazy samorządowe, społecznościową bazę OpenStreetMap oraz wewnętrzne ewidencje instytucji.

**Krajowy Rejestr AED** rozwiązuje ten problem poprzez:
1. **Agregator i silnik deduplikacji przestrzennej (25 m)** łączący oficjalne zasoby `dane.gov.pl` (m.in. UM Legionowo, UM Krosno, UM Marki, UM Przemyśl), ogólnopolską bazę OpenStreetMap (`18 291` punktów bazowych -> `18 319` zharmonizowanych rekordów po scaleniu `162` duplikatów) oraz bezpośrednie zgłoszenia dysponentów.
2. **Wzorcowy zakres danych AED dla portalu `dane.gov.pl`** (18 ustandaryzowanych atrybutów dostarczonych w pliku `Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx`), który kładzie szczególny nacisk na fizyczną dostępność urządzenia w danej minucie (`open_now` w strefie `Europe/Warsaw`, `is_24_7`, `access_type`, `indoor`, piętro, dokładny opis miejsca montażu oraz telefon do ochrony/portierni).
3. **Automatyczny most dla harvestera `dane.gov.pl`** udostępniający dane wyłącznie w formatach odczytywalnych maszynowo (3 i 4 poziom otwartości): **GeoJSON (RFC 7946)**, **CSV (UTF-8 z BOM)**, **DCAT-AP / `schema.org` JSON-LD**, **XLSX** oraz **katalog XML harvestera `dane.gov.pl`** z obsługą nagłówków `ETag`, `304 Not Modified` i licencji `CC0-1.0`.
4. **Kampanię społeczną i promocyjną „Impuls dla Danych”** wraz z logotypem (`.svg`, `.png`, `.jpg`, `.pdf`) i **Księgą Znaku (`.pdf`)**, zachęcającą samorządy, instytucje i firmy do udostępniania lokalizacji swoich urządzeń AED.

---

## 2. Wykaz dostarczonych artefaktów (Wymagania formalne — Sekcja 4)

| Wymaganie formalne | Ścieżka w repozytorium / Adres URL w prototypie |
| :--- | :--- |
| **Szczegółowy opis i tytuł projektu** | `deliverables/Opis_Projektu_Misja_AED.md` oraz `README.md` |
| **Prezentacja (7 slajdów z dowodami, krokami użytkownika i listą ograniczeń)** | `deliverables/Prezentacja_Misja_AED.pdf` (dostępna również z poziomu aplikacji: `/deliverables/Prezentacja_Misja_AED.pdf`) |
| **Prototyp rozwiązania + kod źródłowy** | Monorepo `backend/` (FastAPI + PostGIS/SQLite) oraz `frontend/` (React 19 + TypeScript + MapLibre GL w stylistyce `gov.pl`) |
| **Plik z wzorcowym zakresem danych (`.xlsx`)** | `deliverables/Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx` oraz endpoint na żywo `GET /api/v1/standard.xlsx` |
| **Logotyp akcji w formatach `.jpg`, `.png`, `.pdf` i otwartym `.svg`** | `deliverables/logotyp/logotyp_misja_aed.{svg,png,jpg,pdf}` |
| **Księga znaku w formacie `.pdf`** | `deliverables/Ksiega_Znaku_Misja_AED.pdf` (zawiera 4-zdaniowy opis koncepcji, kolorystykę HEX/RGB/CMYK, pole ochronne, minimalną wielkość i zakazy) |

---

## 3. Opis funkcjonalności i kroki użytkownika

### Ścieżka A: Świadek zdarzenia / Dyspozytor / Ratownik (Wyszukiwarka i Mapa AED)
1. **Wyszukanie lokalizacji**: Kliknięcie przycisku **„Znajdź najbliższy AED”** uruchamia wielopróbkowy odczyt GPS (`watchPosition`) wybierający sygnał o najwyższej dokładności (+/- m) lub pozwala wpisać dowolny adres ulicy w Polsce (obsługiwany przez serwerowy endpoint `/api/v1/aeds/geocode`).
2. **Korekta punktu na mapie**: Użytkownik może jednym kliknięciem wskazać swój dokładny budynek na mapie (**„Wskaż moją lokalizację na mapie”**) lub przeciągnąć niebieski znacznik początkowy.
3. **Weryfikacja dostępności „tu i teraz”**: Filtry **„Otwarte teraz”**, **„Dostępne 24/7”**, **„Tylko ogólnodostępne”** oraz **„Tylko kapsuły zewnętrzne”** natychmiast odrzucają urządzenia zamknięte na klucz po godzinach pracy.
4. **Karta Ewidencyjna AED**: Kliknięcie urządzenia prezentuje dystans w metrach, czas dojścia pieszo w minutach, dokładny opis miejsca montażu, adres ulicy (automatycznie wzbogacany przez Nominatim), piętro, telefon kontaktowy do ochrony, zdjęcie oraz przycisk wyznaczania trasy pieszej.

### Ścieżka B: Dysponent danych / Samorząd / Instytucja
1. **Pobranie wzorcowego standardu `.xlsx`**: W zakładce **„Otwarte dane (dane.gov.pl)”** oraz **„Kampania Misja AED”** dysponent pobiera plik `Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx` ze specyfikacją pól i gotowym szablonem.
2. **Zgłoszenie pojedynczego punktu lub import zbioru**: Formularz **„Zgłoś lub zweryfikuj AED”** na żywo oblicza wskaźnik kompletności (0-100%) według standardu `dane.gov.pl`. Narzędzie importu w zakładce harvestera pozwala wgrać cały plik miejski JSON/GeoJSON.
3. **Automatyczna deduplikacja 25 m i weryfikacja terenowa**: Silnik przestrzenny łączy wpisy oddalone o mniej niż 25 m bez utraty historii źródeł (`aed_source_records`). Każdy użytkownik może też potwierdzić sprawność istniejącego AED lub dopisać brakujący opis montażu wewnątrz budynku.

---

## 4. Lista ewentualnych ograniczeń
1. **Brak tagów adresowych `addr:*` w 99.2% surowych węzłów OpenStreetMap**: Węzły `emergency=defibrillator` w OSM rzadko posiadają wpisany adres ulicy. Rozwiązaliśmy to poprzez serwerowe geokodowanie odwrotne Nominatim z zapisem w bazie danych przy pierwszym pobraniu karty urządzenia.
2. **Ograniczona precyzja geolokalizacji przeglądarkowej na komputerach stacjonarnych**: Na komputerach bez odbiornika GPS przeglądarka zwraca lokalizację węzła sieciowego ISP. Zastosowaliśmy wskaźnik błędu (+/- m), ostrzeżenie przy błędzie > 400 m oraz możliwość ręcznego wskazania budynku na mapie.
3. **Rozbieżności formatowania w plikach samorządowych**: Część plików CSV w `dane.gov.pl` zawiera odwrócone współrzędne X/Y lub niestandardowe cudzysłowy — nasz konektor automatycznie normalizuje orientację współrzędnych dla obszaru Polski.
4. **Brak telemetrii sprzętowej IoT z kapsuł AED**: Większość kapsuł AED nie raportuje stanu baterii przez sieć, dlatego system wymusza cykliczną weryfikację (ważność 365 dni w algorytmie kompletności) wspieraną przez zgłoszenia społeczności i dysponentów.
"""
    (DELIV_DIR / "Opis_Projektu_Misja_AED.md").write_text(md_content, encoding="utf-8")
    (PUBLIC_DELIV_DIR / "Opis_Projektu_Misja_AED.md").write_text(md_content, encoding="utf-8")


def main() -> None:
    DELIV_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DELIV_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate XLSX standard file
    xlsx_bytes = generate_standard_xlsx_bytes()
    xlsx_path = DELIV_DIR / "Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx"
    xlsx_path.write_bytes(xlsx_bytes)
    shutil.copy2(xlsx_path, PUBLIC_DELIV_DIR / xlsx_path.name)
    print(f"Generated {xlsx_path} ({len(xlsx_bytes)} bytes)")

    # 2. Generate Campaign Logotypes (.svg, .png, .jpg, .pdf)
    generate_logo_files()
    print("Generated campaign logotypes (.svg, .png, .jpg, .pdf)")

    # 3. Generate Brand Book PDF (Ksiega_Znaku_Misja_AED.pdf)
    generate_brand_book_pdf()
    print("Generated Ksiega_Znaku_Misja_AED.pdf (4 pages)")

    # 4. Generate Presentation PDF (Prezentacja_Misja_AED.pdf, 7 slides)
    generate_presentation_pdf()
    print("Generated Prezentacja_Misja_AED.pdf (7 slides)")

    # 5. Generate Detailed Project Description Markdown
    generate_project_description()
    print("Generated Opis_Projektu_Misja_AED.md")


if __name__ == "__main__":
    main()

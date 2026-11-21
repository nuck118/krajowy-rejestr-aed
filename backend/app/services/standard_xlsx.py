import hashlib
import io
import zipfile
from xml.sax.saxutils import escape

STANDARD_FIELDS_SPEC: list[tuple[str, ...]] = [
    (
        "1",
        "id",
        "Unikalny identyfikator AED (UUID)",
        "UUID (String)",
        "Wymagane (systemowe)",
        "Systemowe",
        "UUID v4 (np. 36c83cff-b5fa-4990-a9f7-d672ea8d2aee)",
        "Stały klucz główny rekordu kanonicznego zachowywany podczas deduplikacji przestrzennej w promieniu 25 m.",
        "36c83cff-b5fa-4990-a9f7-d672ea8d2aee",
    ),
    (
        "2",
        "latitude",
        "Szerokość geograficzna (WGS84)",
        "Float (Decimal)",
        "Wymagane (krytyczne)",
        "10 pkt",
        "49.000000 do 55.000000 (6 miejsc po przecinku, układ EPSG:4326)",
        "Dokładna współrzędna wejścia lub kapsuły AED pozwalająca wyznaczyć trasę pieszą poniżej 3 minut.",
        "53.127833",
    ),
    (
        "3",
        "longitude",
        "Długość geograficzna (WGS84)",
        "Float (Decimal)",
        "Wymagane (krytyczne)",
        "10 pkt",
        "14.000000 do 24.500000 (6 miejsc po przecinku, układ EPSG:4326)",
        "Dokładna współrzędna geograficzna w granicach Rzeczypospolitej Polskiej.",
        "17.997713",
    ),
    (
        "4",
        "location_description",
        "Dokładny opis miejsca montażu",
        "String (max 500)",
        "Wymagane (krytyczne)",
        "25 pkt",
        "Tekst min. 10 znaków: piętro, wejście, punkt orientacyjny (np. recepcja, portiernia, filar)",
        "Kluczowa informacja ratująca minuty życia (wniosek z tragedii 3 marca): wskazuje gdzie dokładnie wewnątrz lub na zewnątrz obiektu wisi kapsuła.",
        "Parter, hol główny po lewej stronie od wejścia przy dyżurce ochrony",
    ),
    (
        "5",
        "access_type",
        "Zasady fizycznego dostępu",
        "Enum (String)",
        "Wymagane (krytyczne)",
        "5 pkt",
        "public | customers_only | private",
        "Eliminuje ryzyko dotarcia do defibrylatora zamkniętego na klucz bez dostępu dla świadka zdarzenia.",
        "public",
    ),
    (
        "6",
        "is_24_7",
        "Dostępność całodobowa (24/7)",
        "Boolean",
        "Wymagane (krytyczne)",
        "5 pkt",
        "true | false",
        "Pozwala w sytuacji nocnego lub weekendowego zatrzymania krążenia odfiltrować urządzenia zamknięte w nieczynnych biurach.",
        "true",
    ),
    (
        "7",
        "opening_hours",
        "Godziny dostępności obiektu",
        "String (OSM syntax)",
        "Wymagane (gdy nie 24/7)",
        "5 pkt",
        "24/7 lub format OpenStreetMap opening_hours (np. Mo-Fr 07:00-21:00; Sa 08:00-16:00)",
        "Umożliwia automatyczne wyliczenie flagi open_now w strefie czasowej Europe/Warsaw w chwili wezwania pomocy.",
        "Mo-Fr 07:30-20:00; Sa 08:00-15:00",
    ),
    (
        "8",
        "indoor",
        "Umiejscowienie (wewnątrz / na zewnątrz)",
        "Boolean",
        "Wymagane",
        "5 pkt",
        "true (wewnątrz budynku) | false (kapsuła zewnętrzna na elewacji lub słupie)",
        "Informuje ratownika, czy musi wejść do środka budynku i szukać portierni, czy kapsuła znajduje się na zewnątrz.",
        "false",
    ),
    (
        "9",
        "street_address",
        "Ulica i numer budynku",
        "String (max 255)",
        "Wymagane",
        "10 pkt",
        "Nazwa ulicy lub placu wraz z numerem porządkowym budynku",
        "Adres administracyjny dla dyspozytorów medycznych, straży pożarnej oraz nawigacji miejskiej.",
        "ul. Karola Marcinkowskiego 9",
    ),
    (
        "10",
        "city",
        "Miejscowość / Gmina",
        "String (max 120)",
        "Wymagane",
        "10 pkt",
        "Oficjalna nazwa miejscowości z rejestru PRNG / TERYT",
        "Umożliwia filtrowanie i raportowanie pokrycia AED na poziomie gminy i miasta.",
        "Bydgoszcz",
    ),
    (
        "11",
        "postal_code",
        "Kod pocztowy",
        "String (6 znaków)",
        "Zalecane",
        "5 pkt (z TERYT)",
        "Wzorzec XX-XXX (np. 85-056)",
        "Ujednoznacznia lokalizację w przypadku powtarzających się nazw miejscowości i ulic.",
        "85-056",
    ),
    (
        "12",
        "teryt_code",
        "Kod TERYT / SIMC gminy",
        "String (7 cyfr)",
        "Zalecane (administracja)",
        "Zamiennie z kodem pocztowym",
        "7-cyfrowy identyfikator GUS TERYT / SIMC (np. 0924833)",
        "Standard referencyjny polskich rejestrów publicznych ułatwiający integrację z bazami GUS i dane.gov.pl.",
        "0461011",
    ),
    (
        "13",
        "status",
        "Status sprawności urządzenia",
        "Enum (String)",
        "Wymagane",
        "5 pkt",
        "operational | out_of_service | unverified",
        "Oddziela urządzenia zweryfikowane i gotowe do użycia od urządzeń w serwisie lub pozbawionych elektrod/baterii.",
        "operational",
    ),
    (
        "14",
        "last_verified_at",
        "Data ostatniej weryfikacji",
        "DateTime (ISO 8601 UTC)",
        "Wymagane przy weryfikacji",
        "5 pkt (<= 365 dni)",
        "RRRR-MM-DD lub pełny znacznik ISO 8601 UTC",
        "Gwarantuje aktualność danych; rekordy niezweryfikowane przez ponad 12 miesięcy tracą punkty świeżości.",
        "2026-11-21T12:00:00Z",
    ),
    (
        "15",
        "operator",
        "Dysponent / Zarządca urządzenia",
        "String (max 200)",
        "Zalecane",
        "Metadane rozszerzone",
        "Nazwa instytucji, urzędu, firmy lub jednostki OSP odpowiedzialnej za AED",
        "Wskazuje podmiot odpowiedzialny za przegląd techniczny, wymianę elektrod oraz udostępnienie danych.",
        "Urząd Miasta Bydgoszczy",
    ),
    (
        "16",
        "phone",
        "Telefon kontaktowy (ochrona / recepcja)",
        "String (E.164 / PL)",
        "Zalecane",
        "Metadane rozszerzone",
        "Numer telefonu do dyżurki lub ochrony obiektu (np. +48 52 585 80 00)",
        "Gdy urządzenie znajduje się w budynku z kontrolą dostępu, pozwala świadkowi natychmiast wezwać ochronę z kluczem.",
        "+48 52 585 80 00",
    ),
    (
        "17",
        "level",
        "Piętro / Kondygnacja",
        "String",
        "Zalecane (budynki)",
        "Metadane rozszerzone",
        "0 (parter), -1 (poziom podziemny), 1 (1. piętro) itd.",
        "Przyspiesza odnalezienie defibrylatora w wielokondygnacyjnych urzędach, galeriach handlowych i na dworcach.",
        "0",
    ),
    (
        "18",
        "primary_source",
        "Źródło referencyjne rekordu",
        "String",
        "Wymagane (systemowe)",
        "Systemowe",
        "dane_gov_municipal | pl_geojson | osm_overpass | direct_submission",
        "Zapewnia pełną rozliczalność pochodzenia danych (provenance) w krajowym rejestrze dane.gov.pl.",
        "dane_gov_municipal",
    ),
]

SOURCE_SCOPE_MATRIX: list[tuple[str, ...]] = [
    (
        "Wzorcowy Standard dane.gov.pl (Misja AED)",
        "Ogólnopolski (standard docelowy)",
        "CSV / GeoJSON / JSON-LD / XLSX / XML",
        "TAK (WGS84)",
        "TAK (wymagany opis miejsca montażu)",
        "TAK (ulica, miasto, kod pocztowy, TERYT)",
        "TAK (public / customers_only / private)",
        "TAK (24/7 + składnia OSM + wyliczanie open_now)",
        "TAK (wewnątrz / na zewnątrz + piętro)",
        "TAK (status + data weryfikacji + telefon do ochrony)",
        "100% (pełny wzorcowy zakres ratowniczy)",
    ),
    (
        "OpenStreetMap / OpenAEDMap (PL.geojson)",
        "Ogólnopolski (18 291 punktów)",
        "GeoJSON / Overpass JSON",
        "TAK (WGS84)",
        "CZĘŚCIOWO (94.4% posiada defibrillator:location)",
        "BRAK W 99.2% WĘZŁÓW (uzupełniane przez nasz silnik Nominatim)",
        "TAK (92.5% posiada tag access)",
        "CZĘŚCIOWO (37.1% posiada tag opening_hours)",
        "TAK (87.3% posiada tag indoor + 20.2% level)",
        "CZĘŚCIOWO (32.7% posiada check_date oraz 24.5% phone)",
        "58% surowy -> 80%+ po wzbogaceniu przez nasz silnik",
    ),
    (
        "UM Legionowo (portal dane.gov.pl)",
        "Lokalny / Samorządowy (Gmina Miejska Legionowo)",
        "CSV (api.dane.gov.pl)",
        "TAK (szerokosc / dlugosc_geograficzna)",
        "TAK (kolumna nazwa obiektu)",
        "TAK (cecha_ulicy, nazwa_ulicy, nr_budynku, kod_pocztowy, kod_simc TERYT)",
        "DOMYŚLNIE PUBLICZNY (brak osobnej kolumny ograniczeń)",
        "BRAK (wymaga uzupełnienia przez dysponenta)",
        "BRAK (wymaga uzupełnienia przez dysponenta)",
        "TAK (oficjalny rejestr miejski, poziom zaufania Tier 1)",
        "85% (wzorcowe dane adresowe i TERYT, brak godzin otwarcia)",
    ),
    (
        "UM Krosno (portal dane.gov.pl)",
        "Lokalny / Samorządowy (Miasto Krosno)",
        "CSV (api.dane.gov.pl)",
        "TAK (Szerokość / Długość geograficzna)",
        "TAK (kolumny Lokalizacja oraz Nazwa)",
        "TAK (kolumna Adres z kodem pocztowym)",
        "DOMYŚLNIE PUBLICZNY",
        "BRAK",
        "BRAK",
        "TAK (oficjalny rejestr miejski, poziom zaufania Tier 1)",
        "82% (dokładne opisy lokalizacji i adresy, brak godzin otwarcia)",
    ),
    (
        "UM Marki (portal dane.gov.pl)",
        "Lokalny / Samorządowy (Gmina Miasto Marki)",
        "CSV (api.dane.gov.pl)",
        "TAK (współrzędne odwrócone X/Y naprawiane automatycznie)",
        "TAK (kolumny Lokalizacja oraz Nazwa)",
        "TAK (kolumna Adres)",
        "DOMYŚLNIE PUBLICZNY",
        "BRAK",
        "BRAK",
        "TAK (oficjalny rejestr miejski, poziom zaufania Tier 1)",
        "80% (wymaga normalizacji cudzysłowów CSV i orientacji osi X/Y)",
    ),
    (
        "UM Przemyśl (portal otwartych danych)",
        "Lokalny / Samorządowy (Miasto Przemyśl)",
        "GeoJSON",
        "TAK (Point coordinates)",
        "TAK (pole name z numerem ewidencyjnym AED)",
        "TAK (pola street, home_number, city, postcode)",
        "DOMYŚLNIE PUBLICZNY",
        "BRAK",
        "BRAK",
        "TAK (oficjalny rejestr miejski, poziom zaufania Tier 1)",
        "85% (pełny format GeoJSON z adresem, brak godzin dostępności)",
    ),
    (
        "Zgłoszenia bezpośrednie (Kampania Misja AED)",
        "Ogólnopolski (dysponenci, instytucje, OSP, obywatele)",
        "Formularz gov.pl / REST API / Import XLSX-CSV-GeoJSON",
        "TAK (mapa + precyzyjny GPS)",
        "TAK (wymagane min. 10 znaków dla pełnej punktacji)",
        "TAK (automatyczne podpowiadanie ulicy i kodu pocztowego)",
        "TAK (wybór z listy słownikowej)",
        "TAK (przełącznik 24/7 lub harmonogram godzinowy)",
        "TAK (wewnątrz budynku / kapsuła zewnętrzna)",
        "TAK (natychmiastowa weryfikacja i łączenie duplikatów w 25 m)",
        "95% do 100% (walidacja w czasie rzeczywistym przed zapisem)",
    ),
]

TEMPLATE_ROWS: list[tuple[str, ...]] = [
    (
        "52.225572",
        "21.015610",
        "Hol główny przy wejściu od ul. Wiejskiej, ściana po lewej stronie obok straży marszałkowskiej",
        "public",
        "true",
        "24/7",
        "false",
        "ul. Wiejska 4/6/8",
        "Warszawa",
        "00-902",
        "1465011",
        "operational",
        "2026-11-21",
        "Kancelaria Sejmu RP",
        "+48 22 694 25 00",
        "0",
    ),
    (
        "53.124031",
        "18.006256",
        "Parter budynku przy wejściu głównym, obok portierni i punktu informacyjnego",
        "customers_only",
        "false",
        "Mo-Fr 07:30-18:00",
        "true",
        "ul. Jagiellońska 9",
        "Bydgoszcz",
        "85-066",
        "0461011",
        "operational",
        "2026-11-21",
        "Kujawsko-Pomorskie Centrum Edukacji Nauczycieli",
        "+48 52 349 31 50",
        "0",
    ),
    (
        "50.064700",
        "19.945000",
        "Kapsuła zewnętrzna na ścianie Sukiennic od strony Rynku Głównego, obok wejścia do muzeum",
        "public",
        "true",
        "24/7",
        "false",
        "Rynek Główny 1/3",
        "Kraków",
        "31-042",
        "1261011",
        "operational",
        "2026-11-21",
        "Urząd Miasta Krakowa",
        "+48 12 616 12 00",
        "0",
    ),
]


def _col_letter(col_idx_1based: int) -> str:
    result = ""
    n = col_idx_1based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _build_worksheet_xml(
    headers: list[str],
    rows: list[tuple[str, ...]],
    col_widths: list[int],
) -> str:
    last_col = _col_letter(len(headers))
    last_row = len(rows) + 1

    cols_xml = "".join(
        f'<col min="{idx}" max="{idx}" width="{w}" customWidth="1"/>'
        for idx, w in enumerate(col_widths, start=1)
    )

    sheet_rows_xml: list[str] = []

    # Header row (style s="1" -> gov.pl navy header with bold white text)
    header_cells = "".join(
        f'<c r="{_col_letter(c_idx)}1" t="inlineStr" s="1"><is><t>{escape(h)}</t></is></c>'
        for c_idx, h in enumerate(headers, start=1)
    )
    sheet_rows_xml.append(f'<row r="1" ht="28" customHeight="1">{header_cells}</row>')

    # Data rows (style s="2" for first column, s="3" for wrapped body cells)
    for r_offset, row_vals in enumerate(rows, start=2):
        cells = []
        for c_idx, val in enumerate(row_vals, start=1):
            cell_ref = f"{_col_letter(c_idx)}{r_offset}"
            style_id = "2" if c_idx <= 2 else "3"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr" s="{style_id}"><is><t>{escape(str(val))}</t></is></c>'
            )
        sheet_rows_xml.append(f'<row r="{r_offset}" ht="34" customHeight="1">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews>"
        '<sheetFormatPr defaultRowHeight="24"/>'
        f"<cols>{cols_xml}</cols>"
        f'<sheetData>{"".join(sheet_rows_xml)}</sheetData>'
        f'<autoFilter ref="A1:{last_col}{last_row}"/>'
        "</worksheet>"
    )


def generate_standard_xlsx_bytes() -> bytes:
    sheet1_headers = [
        "Lp.",
        "Nazwa techniczna pola (API / CSV / GeoJSON)",
        "Nazwa atrybutu (PL)",
        "Typ danych",
        "Wymagalność w standardzie dane.gov.pl",
        "Waga w algorytmie kompletności (0-100%)",
        "Dopuszczalne wartości / Format walidacji",
        "Opis i uzasadnienie ratownicze (wnioski z wydarzeń 3 marca)",
        "Wartość przykładowa",
    ]
    sheet1_widths = [6, 26, 32, 20, 24, 22, 42, 58, 36]

    sheet2_headers = [
        "Źródło danych / Dysponent",
        "Zasięg terytorialny i wolumen",
        "Format źródłowy",
        "Współrzędne WGS84",
        "Dokładny opis miejsca montażu",
        "Adres administracyjny i TERYT",
        "Zasady dostępu (public / zamknięty)",
        "Godziny otwarcia i dostępność 24/7",
        "Wewnątrz / na zewnątrz i piętro",
        "Status sprawności i weryfikacja",
        "Ocena kompletności i reguła harmonizacji",
    ]
    sheet2_widths = [36, 30, 26, 20, 32, 34, 30, 32, 28, 32, 40]

    sheet3_headers = [
        "latitude",
        "longitude",
        "location_description",
        "access_type",
        "is_24_7",
        "opening_hours",
        "indoor",
        "street_address",
        "city",
        "postal_code",
        "teryt_code",
        "status",
        "last_verified_at",
        "operator",
        "phone",
        "level",
    ]
    sheet3_widths = [14, 14, 52, 16, 10, 26, 10, 28, 18, 14, 14, 15, 16, 34, 20, 10]

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet3.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="1_Wzorcowy_Zakres_Danych" sheetId="1" r:id="rId1"/>'
        '<sheet name="2_Zakres_Referencyjny_Zrodel" sheetId="2" r:id="rId2"/>'
        '<sheet name="3_Szablon_Dla_Dysponenta" sheetId="3" r:id="rId3"/>'
        "</sheets>"
        "</workbook>"
    )

    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet2.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet3.xml"/>'
        '<Relationship Id="rId4" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="3">'
        '<font><sz val="10"/><color rgb="FF1B1B1B"/><name val="Calibri"/></font>'
        '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        '<font><b/><sz val="10"/><color rgb="FF0052A5"/><name val="Consolas"/></font>'
        "</fonts>"
        '<fills count="4">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF0052A5"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF4F6F8"/><bgColor indexed="64"/></patternFill></fill>'
        "</fills>"
        '<borders count="2">'
        "<border><left/><right/><top/><bottom/><diagonal/></border>"
        '<border>'
        '<left style="thin"><color rgb="FFD5DCE2"/></left>'
        '<right style="thin"><color rgb="FFD5DCE2"/></right>'
        '<top style="thin"><color rgb="FFD5DCE2"/></top>'
        '<bottom style="thin"><color rgb="FFD5DCE2"/></bottom>'
        "<diagonal/>"
        "</border>"
        "</borders>"
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
        '<alignment vertical="center" wrapText="1"/>'
        "</xf>"
        '<xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
        '<alignment vertical="center" wrapText="1"/>'
        "</xf>"
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1">'
        '<alignment vertical="center" wrapText="1"/>'
        "</xf>"
        "</cellXfs>"
        "</styleSheet>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            _build_worksheet_xml(sheet1_headers, STANDARD_FIELDS_SPEC, sheet1_widths),
        )
        zf.writestr(
            "xl/worksheets/sheet2.xml",
            _build_worksheet_xml(sheet2_headers, SOURCE_SCOPE_MATRIX, sheet2_widths),
        )
        zf.writestr(
            "xl/worksheets/sheet3.xml",
            _build_worksheet_xml(sheet3_headers, TEMPLATE_ROWS, sheet3_widths),
        )
    return buf.getvalue()


def compute_standard_xlsx_etag(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:20]
    return f'W/"xlsx-{digest}"'


def generate_dane_gov_harvester_xml(
    *,
    base_url: str,
    total_records: int,
    updated_iso: str,
) -> bytes:
    xml_text = f"""<?xml version="1.0" encoding="UTF-8"?>
<ns2:datasets xmlns:ns2="urn:open-data:0.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dataset status="published">
    <extIdent>krajowy-rejestr-aed-polska</extIdent>
    <title>
      <polish>Krajowy Rejestr AED - Ogólnopolski Wykaz Automatycznych Defibrylatorów Zewnętrznych</polish>
      <english>National AED Registry - Unified Polish Automated External Defibrillator Open Data Hub</english>
    </title>
    <description>
      <polish>Ujednolicony, ogólnopolski zbiór danych o lokalizacji i dostępności defibrylatorów AED ({total_records} zweryfikowanych i zharmonizowanych punktów z deduplikacją przestrzenną 25 m), integrujący rejestry samorządowe dane.gov.pl, OpenStreetMap oraz zgłoszenia dysponentów w ramach akcji Impuls dla Danych (Misja AED).</polish>
      <english>Unified national open dataset of Automated External Defibrillators ({total_records} spatially deduplicated records within 25 m) integrating Polish municipal open data feeds, OpenStreetMap, and institutional submissions.</english>
    </description>
    <updateFrequency>daily</updateFrequency>
    <hasDynamicData>true</hasDynamicData>
    <hasHighValueData>true</hasHighValueData>
    <hasResearchData>false</hasResearchData>
    <categories>
      <category>HEAL</category>
      <category>GOVE</category>
      <category>REGI</category>
    </categories>
    <conditions>
      <source>true</source>
      <modification>false</modification>
      <License>CC0 1.0</License>
    </conditions>
    <resources>
      <resource status="published">
        <extIdent>krajowy-rejestr-aed-geojson</extIdent>
        <url>{escape(base_url)}/api/v1/export.geojson</url>
        <title>
          <polish>Krajowy wykaz geoprzestrzenny AED (GeoJSON RFC 7946)</polish>
          <english>National Geospatial AED Feed (GeoJSON RFC 7946)</english>
        </title>
        <description>
          <polish>Geometrie punktowe EPSG:4326 wraz z pełnym zakresem atrybutów dostępności i wskaźnikiem kompletności.</polish>
          <english>EPSG:4326 Point geometries with canonical accessibility attributes and completeness scores.</english>
        </description>
        <availability>remote</availability>
        <dataDate>{escape(updated_iso[:10])}</dataDate>
        <lastUpdateDate>{escape(updated_iso)}</lastUpdateDate>
        <hasDynamicData>true</hasDynamicData>
        <hasHighValueData>true</hasHighValueData>
        <opennessScore>3</opennessScore>
        <format>GeoJSON</format>
      </resource>
      <resource status="published">
        <extIdent>krajowy-rejestr-aed-csv</extIdent>
        <url>{escape(base_url)}/api/v1/export.csv</url>
        <title>
          <polish>Tabela krajowego rejestru AED (CSV UTF-8 z BOM)</polish>
          <english>National Tabular AED Registry (CSV UTF-8 BOM)</english>
        </title>
        <description>
          <polish>Plik tabelaryczny CSV zgodny z wzorcowym zakresem danych o defibrylatorach dla portalu dane.gov.pl.</polish>
          <english>Tabular CSV file conforming to the canonical dane.gov.pl AED reference data standard.</english>
        </description>
        <availability>remote</availability>
        <dataDate>{escape(updated_iso[:10])}</dataDate>
        <lastUpdateDate>{escape(updated_iso)}</lastUpdateDate>
        <hasDynamicData>true</hasDynamicData>
        <hasHighValueData>true</hasHighValueData>
        <opennessScore>3</opennessScore>
        <format>CSV</format>
      </resource>
      <resource status="published">
        <extIdent>krajowy-rejestr-aed-jsonld</extIdent>
        <url>{escape(base_url)}/api/v1/export.jsonld</url>
        <title>
          <polish>Katalog semantyczny Linked Open Data AED (DCAT-AP / JSON-LD)</polish>
          <english>Semantic Linked Open Data AED Catalog (DCAT-AP / JSON-LD)</english>
        </title>
        <description>
          <polish>Powiązane dane semantyczne wykorzystujące słowniki W3C DCAT-AP oraz schema.org EmergencyService.</polish>
          <english>Linked open data graph using W3C DCAT-AP and schema.org EmergencyService vocabularies.</english>
        </description>
        <availability>remote</availability>
        <dataDate>{escape(updated_iso[:10])}</dataDate>
        <lastUpdateDate>{escape(updated_iso)}</lastUpdateDate>
        <hasDynamicData>true</hasDynamicData>
        <hasHighValueData>true</hasHighValueData>
        <opennessScore>4</opennessScore>
        <format>JSON-LD</format>
      </resource>
      <resource status="published">
        <extIdent>wzorcowy-zakres-danych-aed-xlsx</extIdent>
        <url>{escape(base_url)}/api/v1/standard.xlsx</url>
        <title>
          <polish>Wzorcowy zakres danych o defibrylatorach AED i szablon dla dysponentów (XLSX)</polish>
          <english>Reference AED Data Standard Specification and Data Owner Template (XLSX)</english>
        </title>
        <description>
          <polish>Specyfikacja 18 atrybutów wzorcowego standardu danych AED, macierz zakresu referencyjnego źródeł oraz szablon dla instytucji.</polish>
          <english>Specification of the 18 canonical AED attributes, source reference scope matrix, and institutional template.</english>
        </description>
        <availability>remote</availability>
        <dataDate>{escape(updated_iso[:10])}</dataDate>
        <lastUpdateDate>{escape(updated_iso)}</lastUpdateDate>
        <hasDynamicData>false</hasDynamicData>
        <hasHighValueData>true</hasHighValueData>
        <opennessScore>3</opennessScore>
        <format>XLSX</format>
      </resource>
    </resources>
    <tags>
      <tag lang="pl">AED</tag>
      <tag lang="pl">defibrylator</tag>
      <tag lang="pl">ratownictwo medyczne</tag>
      <tag lang="pl">Misja AED</tag>
      <tag lang="pl">Impuls dla Danych</tag>
      <tag lang="en">defibrillator</tag>
      <tag lang="en">emergency</tag>
    </tags>
  </dataset>
</ns2:datasets>
"""
    return xml_text.encode("utf-8")

import { useState } from "react";
import { downloadOpenDataExport } from "../../api/client";
import type { Locale } from "../../i18n/translations";
import { DownloadIcon, ExternalLinkIcon } from "../icons/Icons";
import type { AppTab } from "../layout/TopBar";

interface CampaignViewProps {
  locale: Locale;
  onNavigate?: (tab: AppTab) => void;
}

const REFERENCE_STANDARD_ROWS = [
  { lp: "1", field: "id", pl: "Unikalny identyfikator AED (UUID)", en: "Canonical AED UUID", type: "UUID", req: "System", weight: "System" },
  { lp: "2", field: "latitude", pl: "Szerokość geograficzna (WGS84)", en: "WGS84 Latitude", type: "Float", req: "Wymagane / Required", weight: "10 pkt" },
  { lp: "3", field: "longitude", pl: "Długość geograficzna (WGS84)", en: "WGS84 Longitude", type: "Float", req: "Wymagane / Required", weight: "10 pkt" },
  { lp: "4", field: "location_description", pl: "Dokładny opis miejsca montażu (kontekst 3 marca)", en: "Exact placement description (March 3 context)", type: "String", req: "Wymagane / Required", weight: "25 pkt" },
  { lp: "5", field: "access_type", pl: "Zasady fizycznego dostępu (public / customers_only / private)", en: "Physical access policy", type: "Enum", req: "Wymagane / Required", weight: "5 pkt" },
  { lp: "6", field: "is_24_7", pl: "Dostępność całodobowa (24/7)", en: "24/7 availability flag", type: "Boolean", req: "Wymagane / Required", weight: "5 pkt" },
  { lp: "7", field: "opening_hours", pl: "Godziny dostępności obiektu (składnia OSM)", en: "Facility opening hours (OSM syntax)", type: "String", req: "Wymagane / Required", weight: "5 pkt" },
  { lp: "8", field: "indoor", pl: "Umiejscowienie (wewnątrz budynku / kapsuła zewnętrzna)", en: "Indoor vs outdoor capsule", type: "Boolean", req: "Wymagane / Required", weight: "5 pkt" },
  { lp: "9", field: "street_address", pl: "Ulica i numer porządkowy budynku", en: "Street name and building number", type: "String", req: "Wymagane / Required", weight: "10 pkt" },
  { lp: "10", field: "city", pl: "Miejscowość / Gmina", en: "City / Municipality", type: "String", req: "Wymagane / Required", weight: "10 pkt" },
  { lp: "11", field: "postal_code", pl: "Kod pocztowy (XX-XXX)", en: "Postal code (XX-XXX)", type: "String", req: "Zalecane / Recommended", weight: "5 pkt" },
  { lp: "12", field: "teryt_code", pl: "Kod TERYT / SIMC gminy (7 cyfr)", en: "TERYT / SIMC municipality code", type: "String", req: "Zalecane / Recommended", weight: "z kodem poczt." },
  { lp: "13", field: "status", pl: "Status sprawności (operational / out_of_service / unverified)", en: "Operational status", type: "Enum", req: "Wymagane / Required", weight: "5 pkt" },
  { lp: "14", field: "last_verified_at", pl: "Data ostatniej weryfikacji (ważność 365 dni)", en: "Last verification date (365-day freshness)", type: "DateTime", req: "Wymagane / Required", weight: "5 pkt" },
  { lp: "15", field: "operator", pl: "Dysponent / Zarządca urządzenia", en: "Equipment owner / operator", type: "String", req: "Zalecane / Recommended", weight: "Metadane" },
  { lp: "16", field: "phone", pl: "Telefon kontaktowy do ochrony / portierni", en: "Security / reception desk phone", type: "String", req: "Zalecane / Recommended", weight: "Metadane" },
  { lp: "17", field: "level", pl: "Piętro / Kondygnacja (0 = parter)", en: "Floor / building level", type: "String", req: "Zalecane / Recommended", weight: "Metadane" },
  { lp: "18", field: "primary_source", pl: "Źródło referencyjne rekordu", en: "Primary provenance source", type: "String", req: "System", weight: "System" },
];

const SOURCE_SCOPE_ROWS = [
  {
    source: "Wzorcowy Standard dane.gov.pl (Misja AED)",
    scope: "Ogólnopolski (standard docelowy)",
    format: "XLSX, CSV, GeoJSON, JSON-LD, XML",
    coordsAddr: "WGS84 + Ulica + Miasto + Kod + TERYT",
    placementAccess: "Wymagany opis montażu + access_type + indoor + piętro",
    hoursStatus: "is_24_7 + opening_hours + status + telefon ochrony",
  },
  {
    source: "OpenStreetMap / OpenAEDMap (PL.geojson)",
    scope: "Ogólnopolski (18 291 punktów)",
    format: "GeoJSON / Overpass API",
    coordsAddr: "WGS84 (100%), Adres uzupełniany przez Nominatim",
    placementAccess: "94.4% opis montażu, 92.5% zasady dostępu, 87.3% indoor",
    hoursStatus: "37.1% godziny otwarcia, 32.7% data weryfikacji",
  },
  {
    source: "UM Legionowo (portal dane.gov.pl)",
    scope: "Samorządowy (Gmina Miejska Legionowo)",
    format: "CSV (api.dane.gov.pl)",
    coordsAddr: "WGS84 + Ulica + Kod pocztowy + TERYT SIMC",
    placementAccess: "Nazwa obiektu użyteczności publicznej (public)",
    hoursStatus: "Status operational (Tier 1), godziny przy scalaniu z OSM",
  },
  {
    source: "UM Krosno (portal dane.gov.pl)",
    scope: "Samorządowy (Miasto Krosno)",
    format: "CSV (api.dane.gov.pl)",
    coordsAddr: "WGS84 + Adres z kodem pocztowym",
    placementAccess: "Kolumny Lokalizacja + Nazwa obiektu (public)",
    hoursStatus: "Status operational (Tier 1)",
  },
  {
    source: "UM Marki (portal dane.gov.pl)",
    scope: "Samorządowy (Gmina Miasto Marki)",
    format: "CSV (api.dane.gov.pl)",
    coordsAddr: "Automatyczna korekta odwróconych osi X/Y + Adres",
    placementAccess: "Kolumny Lokalizacja + Nazwa obiektu (public)",
    hoursStatus: "Status operational (Tier 1)",
  },
  {
    source: "UM Przemyśl (portal otwartych danych)",
    scope: "Samorządowy (Miasto Przemyśl)",
    format: "GeoJSON",
    coordsAddr: "Point WGS84 + street + home_number + postcode",
    placementAccess: "Nazwa i numer ewidencyjny AED (public)",
    hoursStatus: "Status operational (Tier 1)",
  },
];

const BRAND_COLORS = [
  { name: "Granat Państwowy (Tarcza i nazwa)", hex: "#152B45", rgb: "21, 43, 69", cmyk: "70, 38, 0, 73", role: "Tarcza sygnetu, typografia główna" },
  { name: "Karmazyn Narodowy / Serce AED", hex: "#D9173B", rgb: "217, 23, 59", cmyk: "0, 89, 73, 15", role: "Serce AED, krzyż medyczny, wstęga RP" },
  { name: "Błękit Instytucjonalny dane.gov.pl", hex: "#0052A5", rgb: "0, 82, 165", cmyk: "100, 50, 0, 35", role: "Nawigacja i linki portalu gov.pl" },
  { name: "Szmaragd Dostępności 24/7 (WCAG AA)", hex: "#047857", rgb: "4, 120, 87", cmyk: "97, 0, 28, 53", role: "Status potwierdzonej dostępności 24/7" },
  { name: "Grafit Typograficzny (WCAG AAA)", hex: "#1B1B1B", rgb: "27, 27, 27", cmyk: "0, 0, 0, 89", role: "Tekst główny i wersja monochromatyczna" },
];

export function CampaignView({ locale, onNavigate }: CampaignViewProps) {
  const [downloadingXlsx, setDownloadingXlsx] = useState(false);
  const isPl = locale === "pl";

  const handleDownloadXlsx = async () => {
    setDownloadingXlsx(true);
    try {
      await downloadOpenDataExport("xlsx");
    } finally {
      setDownloadingXlsx(false);
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-4 py-5 space-y-5">
      <div className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-[4px] p-4 sm:p-6 space-y-7">
        {/* Header & Breadcrumb */}
        <div className="space-y-3 pb-6 border-b border-[var(--border-hairline)]">
          <nav
            aria-label="Breadcrumb"
            className="text-xs text-[var(--ink-secondary)] flex flex-wrap items-center gap-1.5"
          >
            <button
              type="button"
              onClick={() => onNavigate?.("map")}
              className="text-[var(--gov-blue)] hover:underline cursor-pointer"
            >
              {isPl ? "Strona główna" : "Home"}
            </button>
            <span aria-hidden="true">/</span>
            <span>Krajowy Rejestr AED</span>
            <span aria-hidden="true">/</span>
            <span className="text-[var(--ink-primary)] font-semibold">
              {isPl
                ? "Kampania społeczna „Impuls dla Danych” i Wzorcowy Standard (Misja AED)"
                : "Public Campaign 'Impulse for Data' and Reference Standard (Misja AED)"}
            </span>
          </nav>

          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--ink-primary)]">
            {isPl
              ? "Misja AED: Kampania „Impuls dla Danych”, Księga Znaku i Wzorcowy Zakres Danych"
              : "Misja AED: 'Impulse for Data' Campaign, Brand Book, and Reference Data Standard"}
          </h1>
          <p className="text-sm sm:text-base text-[var(--ink-secondary)] max-w-4xl leading-relaxed">
            {isPl
              ? "Komplet artefaktów wypracowanych w ramach wyzwania „Misja AED: Dane na ratunek” dla portalu dane.gov.pl: ogólnopolska kampania zachęcająca dysponentów do otwierania danych o defibrylatorach, logotyp w formatach otwartych i produkcyjnych (.svg, .png, .jpg, .pdf), Księga Znaku (.pdf), tabela wzorcowego zakresu danych (.xlsx) oraz prezentacja rozwiązania (.pdf)."
              : "Complete deliverables package for the 'Misja AED: Data to the Rescue' challenge on dane.gov.pl: national campaign encouraging data owners to publish defibrillator locations, logotype files (.svg, .png, .jpg, .pdf), Brand Book (.pdf), reference data standard spreadsheet (.xlsx), and presentation deck (.pdf)."}
          </p>
        </div>

        {/* Section 1: Campaign Identity & Logotype Showcase */}
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--gov-crimson)]">
                {isPl
                  ? "1. Akcja promocyjna dla dysponentów danych (25% kryteriów oceny)"
                  : "1. Promotional Campaign for Data Owners (25% evaluation weight)"}
              </span>
              <h2 className="text-xl font-bold text-[var(--ink-primary)] mt-0.5">
                {isPl
                  ? "Nazwa akcji: IMPULS DLA DANYCH (Misja AED)"
                  : "Campaign Name: IMPULS DLA DANYCH (Misja AED)"}
              </h2>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <a
                href="/deliverables/Ksiega_Znaku_Misja_AED.pdf"
                target="_blank"
                rel="noopener noreferrer"
                className="h-9 px-3.5 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-xs font-semibold inline-flex items-center gap-1.5"
              >
                <DownloadIcon className="w-3.5 h-3.5" />
                <span>{isPl ? "Księga Znaku A4 Pion (.pdf)" : "Brand Book A4 Portrait (.pdf)"}</span>
              </a>
              <a
                href="/deliverables/Prezentacja_Misja_AED.pdf"
                target="_blank"
                rel="noopener noreferrer"
                className="h-9 px-3.5 rounded-[3px] border border-[var(--gov-blue)] bg-[var(--bg-canvas)] hover:bg-[var(--bg-callout)] text-[var(--gov-blue)] text-xs font-semibold inline-flex items-center gap-1.5"
              >
                <ExternalLinkIcon className="w-3.5 h-3.5" />
                <span>{isPl ? "Prezentacja projektu (7 slajdów .pdf)" : "Project Presentation (7 slides .pdf)"}</span>
              </a>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
            <div className="lg:col-span-5 border border-[var(--border-hairline)] rounded-[4px] p-6 bg-[var(--bg-canvas)] flex flex-col items-center justify-center">
              <img
                src="/deliverables/logotyp_misja_aed.png"
                alt="Logotyp Krajowy Rejestr AED - Misja AED"
                className="w-full max-w-[320px] h-auto object-contain"
              />
            </div>

            <div className="lg:col-span-7 flex flex-col gap-4">
              <div className="border border-[var(--border-hairline)] rounded-[4px] p-4 bg-[var(--bg-callout)] space-y-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--gov-blue)]">
                    {isPl ? "Hasło przewodnie akcji" : "Campaign Slogan"}
                  </div>
                  <p className="text-base font-bold text-[var(--ink-primary)] mt-1">
                    „Zamknięta wiedza nie ratuje życia. Otwórz dane o swoim AED w portalu dane.gov.pl.”
                  </p>
                </div>
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--ink-secondary)]">
                    {isPl ? "Pobierz oficjalny logotyp we wszystkich wymaganych formatach" : "Download Official Logotype in All Required Formats"}
                  </div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {(["svg", "png", "jpg", "pdf"] as const).map((ext) => (
                      <a
                        key={ext}
                        href={`/deliverables/logotyp_misja_aed.${ext}`}
                        download={`logotyp_misja_aed.${ext}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-1.5 rounded-[3px] border border-[var(--border-input)] hover:border-[var(--gov-blue)] bg-[var(--bg-canvas)] font-mono text-xs font-semibold text-[var(--gov-blue)] inline-flex items-center gap-1.5"
                      >
                        <DownloadIcon className="w-3.5 h-3.5" />
                        <span>.{ext.toUpperCase()}</span>
                      </a>
                    ))}
                  </div>
                </div>
              </div>

              <div className="border border-[var(--border-hairline)] rounded-[4px] p-4 bg-[var(--bg-canvas)] space-y-2 flex-1">
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--gov-blue)]">
                  {isPl
                    ? "Opis koncepcji znaku (4 zdania, zgodnie z wymogiem 3-5 zdań)"
                    : "Logo Concept Description (4 sentences, per 3-5 sentence requirement)"}
                </div>
                <p className="text-sm text-[var(--ink-primary)] leading-relaxed">
                  1. Znak łączy heraldyczną tarczę bezpieczeństwa publicznego i znacznik lokalizacji (pinezkę GPS) z międzynarodowym symbolem defibrylatora AED (serce z impulsem elektrycznym na tle krzyża medycznego). 2. Biało-czerwona wstęga spina sygnet z tożsamością państwową Rzeczypospolitej Polskiej oraz systemem Państwowego Ratownictwa Medycznego i portalu dane.gov.pl. 3. Zestawienie głębokiego granatu państwowego (#152B45) z narodowym karmazynem (#D9173B) zapewnia natychmiastową rozpoznawalność w sytuacji zagrożenia życia i pełną czytelność zgodnie z WCAG 2.1 AA. 4. Zwarta, symetryczna konstrukcja sprawdza się zarówno jako oznakowanie fizycznych kapsuł AED, jak i w interfejsach mobilnych, webowych oraz materiałach promocyjnych kierowanych do dysponentów danych.
                </p>
              </div>
            </div>
          </div>

          {/* Brand Book Key Parameters Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="border border-[var(--border-hairline)] rounded-[3px] p-4 bg-[var(--bg-canvas)] space-y-2">
              <h3 className="text-sm font-bold text-[var(--ink-primary)]">
                {isPl ? "Kolorystyka oficjalna (HEX / RGB / CMYK)" : "Official Color Palette"}
              </h3>
              <div className="space-y-2">
                {BRAND_COLORS.map((c) => (
                  <div key={c.hex} className="flex items-center gap-2.5 text-xs">
                    <span
                      className="w-5 h-5 rounded-[2px] border border-[var(--border-hairline)] shrink-0"
                      style={{ backgroundColor: c.hex }}
                    />
                    <div>
                      <span className="font-mono font-bold text-[var(--ink-primary)]">{c.hex}</span>{" "}
                      <span className="text-[var(--ink-secondary)]">({c.name})</span>
                      <div className="text-[11px] font-mono text-[var(--ink-secondary)]">
                        RGB: {c.rgb} | CMYK: {c.cmyk}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="border border-[var(--border-hairline)] rounded-[3px] p-4 bg-[var(--bg-canvas)] space-y-2 text-xs">
              <h3 className="text-sm font-bold text-[var(--ink-primary)]">
                {isPl ? "Pole ochronne i minimalna wielkość" : "Clear Space and Minimum Size"}
              </h3>
              <p className="text-[var(--ink-primary)] leading-relaxed">
                <strong>{isPl ? "Pole ochronne (Moduł X):" : "Clear Space (Module X):"}</strong>{" "}
                {isPl
                  ? "Strefa buforowa wokół znaku wynosi X = 1/4 wysokości tarczy sygnetu (H = 4X). W polu ochronnym nie wolno umieszczać tekstów ani krawędzi innych obiektów."
                  : "Protective buffer zone around the mark equals X = 1/4 of emblem shield height (H = 4X)."}
              </p>
              <p className="text-[var(--ink-primary)] leading-relaxed">
                <strong>{isPl ? "Minimalna wielkość (pełny znak):" : "Minimum size (full lockup):"}</strong>{" "}
                140 px x 36 px (digital) | 35 mm x 9 mm (druk).
              </p>
              <p className="text-[var(--ink-primary)] leading-relaxed">
                <strong>{isPl ? "Minimalna wielkość (sam sygnet):" : "Minimum size (emblem only):"}</strong>{" "}
                24 px x 24 px (digital) | 8 mm x 8 mm (druk).
              </p>
            </div>

            <div className="border border-[var(--border-hairline)] rounded-[3px] p-4 bg-[var(--bg-canvas)] space-y-2 text-xs">
              <h3 className="text-sm font-bold text-[var(--gov-crimson)]">
                {isPl ? "Niedozwolone wykorzystywanie znaku" : "Prohibited Logo Modifications"}
              </h3>
              <ul className="space-y-1.5 text-[var(--ink-primary)] list-disc list-inside leading-relaxed">
                <li>Zakaz rozciągania i deformacji proporcji sygnetu lub typografii.</li>
                <li>Zakaz samowolnej zmiany barw poza paletą podstawową i monochromatyczną.</li>
                <li>Zakaz obracania, pochylania lub dodawania cieni (drop-shadow).</li>
                <li>Zakaz umieszczania znaku na niekontrastowym tle naruszającym WCAG.</li>
                <li>Zakaz naruszania pola ochronnego X innymi elementami.</li>
                <li>Zakaz usuwania linii impulsu EKG lub symbolu serca AED.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Section 2: Reference Scope Matrix (Porównanie zakresu referencyjnego źródeł) */}
        <section className="space-y-3 pt-4 border-t border-[var(--border-hairline)]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--gov-blue)]">
                {isPl
                  ? "2. Integracja rozproszonych źródeł ze wskazaniem ich zakresu referencyjnego"
                  : "2. Distributed Sources Integration and Reference Scope Matrix"}
              </span>
              <h2 className="text-xl font-bold text-[var(--ink-primary)] mt-0.5">
                {isPl
                  ? "Porównanie zakresu referencyjnego zintegrowanych dysponentów danych"
                  : "Reference Data Scope Comparison Across Integrated Sources"}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => void handleDownloadXlsx()}
              disabled={downloadingXlsx}
              className="h-10 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-xs font-semibold inline-flex items-center gap-2 cursor-pointer shrink-0"
            >
              <DownloadIcon className="w-4 h-4" />
              <span>
                {downloadingXlsx
                  ? "..."
                  : isPl
                    ? "Pobierz Wzorcowy Zakres Danych (.xlsx)"
                    : "Download Reference Data Standard (.xlsx)"}
              </span>
            </button>
          </div>

          <div className="overflow-x-auto border border-[var(--border-hairline)] rounded-[3px]">
            <table className="w-full text-left border-collapse text-xs">
              <caption className="sr-only">
                {isPl
                  ? "Porównanie zakresu referencyjnego zintegrowanych dysponentów danych"
                  : "Reference Data Scope Comparison Across Integrated Sources"}
              </caption>
              <thead>
                <tr className="bg-[var(--bg-surface)] border-b border-[var(--border-hairline)] text-[var(--ink-primary)]">
                  <th scope="col" className="py-2.5 px-3 font-bold">Źródło / Dysponent</th>
                  <th scope="col" className="py-2.5 px-3 font-bold">Zasięg</th>
                  <th scope="col" className="py-2.5 px-3 font-bold">Format</th>
                  <th scope="col" className="py-2.5 px-3 font-bold">Współrzędne i Adres</th>
                  <th scope="col" className="py-2.5 px-3 font-bold">Opis miejsca i Dostęp</th>
                  <th scope="col" className="py-2.5 px-3 font-bold">Godziny i Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)]">
                {SOURCE_SCOPE_ROWS.map((r, idx) => (
                  <tr
                    key={r.source}
                    className={idx === 0 ? "bg-[var(--bg-callout)] font-medium" : "bg-[var(--bg-canvas)]"}
                  >
                    <td className="py-2.5 px-3 font-bold text-[var(--ink-primary)]">{r.source}</td>
                    <td className="py-2.5 px-3 text-[var(--ink-secondary)]">{r.scope}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[var(--gov-blue)]">{r.format}</td>
                    <td className="py-2.5 px-3 text-[var(--ink-primary)]">{r.coordsAddr}</td>
                    <td className="py-2.5 px-3 text-[var(--ink-primary)]">{r.placementAccess}</td>
                    <td className="py-2.5 px-3 text-[var(--ink-primary)]">{r.hoursStatus}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Section 3: Canonical 18-Field Reference Schema Specification */}
        <section className="space-y-3 pt-4 border-t border-[var(--border-hairline)]">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--gov-blue)]">
              {isPl
                ? "3. Wzorcowy zakres danych o defibrylatorach dla portalu dane.gov.pl (10% kryteriów oceny)"
                : "3. Reference AED Data Standard for dane.gov.pl (10% evaluation weight)"}
            </span>
            <h2 className="text-xl font-bold text-[var(--ink-primary)] mt-0.5">
              {isPl
                ? "Specyfikacja 18 atrybutów kanonicznego rekordu AED (zawarta w pliku .xlsx)"
                : "Specification of the 18 Canonical AED Attributes (included in .xlsx file)"}
            </h2>
          </div>

          <div className="overflow-x-auto border border-[var(--border-hairline)] rounded-[3px]">
            <table className="w-full text-left border-collapse text-xs">
              <caption className="sr-only">
                {isPl
                  ? "Specyfikacja 18 atrybutów kanonicznego rekordu AED"
                  : "Specification of the 18 Canonical AED Attributes"}
              </caption>
              <thead>
                <tr className="bg-[var(--bg-surface)] border-b border-[var(--border-hairline)] text-[var(--ink-primary)]">
                  <th scope="col" className="py-2 px-3 font-bold">Lp.</th>
                  <th scope="col" className="py-2 px-3 font-bold">Pole techniczne (CSV / GeoJSON)</th>
                  <th scope="col" className="py-2 px-3 font-bold">Nazwa atrybutu</th>
                  <th scope="col" className="py-2 px-3 font-bold">Typ</th>
                  <th scope="col" className="py-2 px-3 font-bold">Wymagalność</th>
                  <th scope="col" className="py-2 px-3 font-bold">Waga kompletności</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)]">
                {REFERENCE_STANDARD_ROWS.map((row) => (
                  <tr key={row.field} className="hover:bg-[var(--bg-surface)]">
                    <td className="py-2 px-3 font-mono text-[var(--ink-secondary)]">{row.lp}</td>
                    <td className="py-2 px-3 font-mono font-bold text-[var(--gov-blue)]">{row.field}</td>
                    <td className="py-2 px-3 text-[var(--ink-primary)]">{isPl ? row.pl : row.en}</td>
                    <td className="py-2 px-3 font-mono text-[var(--ink-secondary)]">{row.type}</td>
                    <td className="py-2 px-3 text-[var(--ink-primary)]">{row.req}</td>
                    <td className="py-2 px-3 font-semibold text-[var(--status-emerald)]">{row.weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

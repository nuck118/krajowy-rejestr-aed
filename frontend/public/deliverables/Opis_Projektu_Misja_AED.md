# Szczegółowy Opis i Tytuł Projektu

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

# TODO / roadmap

Trwały backlog projektu. Odhaczaj zrobione, dopisuj nowe. Pamięć projektu jest
w `CLAUDE.md`.

## W toku

- [ ] Pierwszy tytuł: aksolotki 5-6 lat, kawaii, 8.5x11, 40 wzorów.
  - [x] Wygenerować 40 wzorów przez NB2 (4K).
  - [x] Złożyć wnętrze i przejść walidator (`build --strict`, RESULT PASS).
  - [x] Kolorowy przód okładki + skład okładki (wersja robocza).
  - [ ] Przegląd ręczny 40 stron (zamknięte kontury, artefakty, pola).
  - [ ] Finalny tytuł i teksty z badania SEO (patrz niżej), wstawić na okładkę.
  - [x] Przerobić typografię okładki.
- [ ] Regeneracja wnętrza w 2K + profil wieku 4-8 + nowe negatywy (mniej kleksów,
  bogatsze wzory, ~połowa kosztu). WSTRZYMANE, żeby ograniczyć koszty. Odblokować,
  gdy wrócimy do generowania.

## Zaplanowane

- [x] **Typografia okładki**: tytuł jako duże litery z grubym konturem i cieniem
  wprost na grafice (bez białych plomb), podtytuł i autor na półprzezroczystej
  zaokrąglonej wstędze. Kolory sterowane flagami `--title-fill`,
  `--title-outline`, `--banner`, `--banner-alpha`.
- [x] Zaokrąglony font display na tytuł okładki: dołączony **Baloo 2 ExtraBold**
  (OFL, z Google Fonts, statyczna instancja wght=800, pełne polskie znaki) w
  `kdpbuilder/data/fonts/`. Jest domyślnym fontem tytułu; podtytuł i blurb
  zostają w DejaVu dla czytelności. Nadpiszesz przez `--font-title`.

## Backlog

### SEO i słowa kluczowe (priorytet)

Osobno dla rynku PL (Amazon.pl) i EN (Amazon.com). Rynki różnią się sposobem
wyszukiwania, więc nie tłumacz fraz jeden do jednego.

- [~] Rynek polski: badanie słów kluczowych na podstawie lokalnego wolumenu.
  Wersja oparta na analizie konkurencji jest w `docs/seo_axolotl_pl.md`
  (tytuł, podtytuł, opis, 7 tagów, kategorie). Do domknięcia: walidacja
  realnego wolumenu przez autouzupełnianie Amazon.pl i narzędzie (Helium 10 /
  Publisher Rocket), bo tu nie mam dostępu do liczb.
  - [x] tytuł (propozycja)
  - [x] podtytuł (propozycja)
  - [x] opis sprzedażowy (propozycja)
  - [x] siedem tagów (backend keywords)
  - [ ] walidacja wolumenu i finalny wybór wariantu
- [~] Rynek zagraniczny (US): pakiet w `docs/seo_axolotl_en.md` (tytuł,
  podtytuł, opis, 7 tagów, kategorie). Do domknięcia: walidacja wolumenu na
  Amazon.com.
- [x] Powtarzalne narzędzie badania słów kluczowych: komenda `keywords`
  (`kdpbuilder/keywords.py`) wyciąga frazy z częstością z zapisanych aukcji,
  z filtrem `--contains niche` na dumpy HTML. Nie daje wolumenu (do walidacji
  narzędziem zewnętrznym), ale daje powtarzalną listę kandydatów.

### Pixel-perfect skaner PDF

- [x] Skaner `scan` analizujący rzeczywiste piksele osadzonych obrazów
  (`kdpbuilder/scan.py`, komenda `scan`). Kontrole: czystość (szarość z dala od
  krawędzi, ignoruje antyaliasing), grubość linii przez transformatę odległości
  (min 0,75 pkt), drobne artefakty (spójne komponenty), tusz w marginesie.
  Stack: PyMuPDF + numpy + scipy. Sprawdzony na realnym wnętrzu: PASS.
- [x] Zamknięte kontury: realna kontrola słabych zamknięć (erozja czerni o 1 px
  ujawnia cienkie/przerwane ściany, które puszczają kolor). Sprawdzona na
  przykładach z celowo cienką ścianą (WARN) i szczelnym boxem (PASS), oraz na
  realnym wnętrzu (PASS). Pełne przerwy konturu dalej wymagają oka.

### Pipeline i jakość

- [x] Asymetryczny gutter na oprawę: większy margines po stronie oprawy,
  naprzemiennie lewa/prawa wg strony (recto/verso). Flaga `--no-gutter` wraca do
  symetrycznego. Domyślnie włączony dla druku bez spadu.
- [ ] Wariant formatu 8.5x8.5: już obsługiwany przez specyfikacje i pipeline
  (klucz trim `8.5x8.5`), do świadomego wyboru przy tytule. Nic do dobudowania.
- [x] CI: `.github/workflows/ci.yml` uruchamia pytest na push do main i na PR
  (testy pokrywają walidator, skaner i pipeline).
- [x] Więcej tematów w bibliotece promptów: dinosaur, unicorn, ocean, cat
  (plus aksolotl). Styl kawaii uczyniony neutralnym tematycznie (usunięte
  axolotlowe "frilly gills").

## Zrobione

- [x] Skill kdp-compliance z walidatorem PDF.
- [x] Pipeline kdpbuilder: prompts, imageprep, assemble, specs, cli.
- [x] Biblioteka promptów: grupy wieku (3-4, 4-8, 5-6, 6-7), 7 stylistyk, aksolotl.
- [x] Integracja generacji obrazów przez Gemini API (domyślnie NB2, 2K dla wnętrza).
- [x] Moduł okładki: kalkulator grzbietu, wrap PDF, typografia z konturem i wstęgą.
- [x] Skaner pikselowy `scan` (czystość, grubość linii, odpryski, margines, solid-fill).
- [x] Pierwsze wnętrze: 40 wzorów wygenerowane, złożone, walidator i skaner PASS.
- [x] SEO: pakiet PL (`seo_axolotl_pl.md`) i EN (`seo_axolotl_en.md`), narzędzie `keywords`.
- [x] Optymalizacja kosztów: 2K dla wnętrza (~połowa kosztu 4K).

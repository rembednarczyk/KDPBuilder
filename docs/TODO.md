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
  - [ ] Przerobić typografię okładki (task poniżej), potem finalny cover.

## Zaplanowane

- [ ] **Typografia okładki**: przerobić skład tytułu jak w niszy. Duże,
  kolorowe, obrysowane litery "bąbelkowe" wprost na scenie, z cieniem i
  konturem, bez białych plomb pod tekstem. Opcjonalnie półprzezroczysta wstęga
  pod podtytułem. Cel: dorównać okładkom konkurencji zamiast płaskiego tekstu.

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
- [ ] Rynek zagraniczny (US): optymalizacja SEO tytułu, podtytułu, opisu i
  siedmiu tagów pod wyszukiwania anglojęzyczne.
- [ ] Zbudować narzędzie/proces badania słów kluczowych (źródła wolumenu,
  lista frazowa, mapowanie na tytuł i tagi), żeby był powtarzalny dla kolejnych
  tytułów, a nie jednorazowy.

### Pixel-perfect skaner PDF (do oceny i budowy)

- [ ] Skaner renderujący każdą stronę do pikseli i sprawdzający głębiej niż
  obecny walidator. Wykonalne. Realne kontrole:
  - czystość: piksele naprawdę czysto czarne i czysto białe, bez szarości;
  - grubość linii: transformata odległości na czerni, minimalna szerokość kreski
    w px przeliczona na punkty (kontrola min 0,75 pkt);
  - drobne artefakty: małe spójne komponenty (kropki, śmieci) do usunięcia;
  - strefa bezpieczna i krawędzie: brak tuszu w marginesie, a przy spadzie grafika
    dochodzi do krawędzi;
  - zamknięte kontury: wypełnienie zalewowe od zewnątrz i wykrywanie nieszczelnych
    obszarów (trudniejsze, ale osiągalne, do walidacji na przykładach).
  Stack: PyMuPDF do renderu, numpy do analizy. Wynik jako raport per strona.

### Pipeline i jakość

- [ ] Rozkład marginesu na oprawę: asymetryczny gutter dla druku dwustronnego
  (obecnie symetryczny margines bezpieczny).
- [ ] Wariant formatu 8.5x8.5 (kwadrat sprzedaje się dobrze, wyróżnia na
  miniaturce).
- [ ] Wpięcie walidatora jako krok build w CI (`--json --strict`, parsowanie
  raportu).
- [ ] Więcej tematów w bibliotece promptów poza aksolotkiem.

## Zrobione

- [x] Skill kdp-compliance z walidatorem PDF.
- [x] Pipeline kdpbuilder: prompts, imageprep, assemble, specs, cli.
- [x] Biblioteka promptów: 3 grupy wieku, 7 stylistyk, temat aksolotl.
- [x] Integracja generacji obrazów przez Gemini API (domyślnie NB2).
- [x] Moduł okładki: kalkulator grzbietu, skład wrap PDF z tekstem i spadem.
- [x] Zestaw tytułów i opisów PL/EN (wersja startowa, przed badaniem SEO).

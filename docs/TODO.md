# TODO / roadmap

Trwały backlog projektu. Odhaczaj zrobione, dopisuj nowe. Pamięć projektu jest
w `CLAUDE.md`.

## W toku

- [ ] Pierwszy tytuł: aksolotki 5-6 lat, kawaii, 8.5x11, 40 wzorów.
  - [ ] Wygenerować 40 wzorów przez NB2 (4K), przejrzeć strona po stronie.
  - [ ] Złożyć wnętrze i przejść walidator (`build --strict`).
  - [ ] Kolorowy przód okładki + skład okładki z marką Kolorowe Skarby.

## Backlog

### SEO i słowa kluczowe (priorytet)

Osobno dla rynku PL (Amazon.pl) i EN (Amazon.com). Rynki różnią się sposobem
wyszukiwania, więc nie tłumacz fraz jeden do jednego.

- [ ] Rynek polski: przeprowadzić osobne badanie słów kluczowych na podstawie
  lokalnego wolumenu wyszukiwań. Rodzice w Polsce wyszukują inaczej niż w USA.
  Opracować po polsku:
  - [ ] tytuł
  - [ ] podtytuł
  - [ ] opis sprzedażowy
  - [ ] siedem tagów (backend keywords) w panelu KDP
- [ ] Rynek zagraniczny (US): optymalizacja SEO tytułu, podtytułu, opisu i
  siedmiu tagów pod wyszukiwania anglojęzyczne.
- [ ] Zbudować narzędzie/proces badania słów kluczowych (źródła wolumenu,
  lista frazowa, mapowanie na tytuł i tagi), żeby był powtarzalny dla kolejnych
  tytułów, a nie jednorazowy.

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

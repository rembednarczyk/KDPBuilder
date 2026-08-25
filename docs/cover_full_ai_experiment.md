# Eksperyment: w pełni AI okładka (jeden spójny obraz wrapa)

Test kierunku, w którym **każda część okładki jest wygenerowana przez model**,
bez proceduralnych presetów ze skryptu (rich-title, banery scallop, kolaż
miniaturek). Cały wrap (tył + grzbiet + przód) powstał jako **jeden obraz** w
jednym wywołaniu modelu, więc wszystkie części są dopasowane stylistycznie z
konstrukcji.

## Konfiguracja

- Model: **`gemini-3-pro-image`** (Pro), 4K, proporcje `3:2` (najbliższe pełnemu
  wrapowi 17,43 x 11,25 cala).
- Jedno wywołanie = jeden płatny obraz (5056 x 3392 px). Nie sklejka.
- Skrypt robi **tylko geometrię**: dopasowanie do dokładnych wymiarów KDP w 300
  DPI i eksport PDF. Zero rysowania tekstu i kształtów.
- Skrypt eksperymentu: `fullwrap.py` (poza repo, w scratchpadzie).

## Co model zrobił dobrze (wszystko w jednym obrazie, spójne stylistycznie)

- Tytuł "Aksolotki" — poprawnie, bąbelkowe różowe liternictwo z białym konturem.
- Wstęga tęczowa: "Kolorowanka dla dzieci 4-8 lat" — poprawnie.
- Naklejka "40 wzorów" — poprawnie, z ó.
- Blurb na tylnej okładce: pełny polski akapit z wszystkimi diakrytykami
  poprawnie (świata, podróż, pełną, uśmiechu, kreatywności, artystów, którzy,
  kochają, dobrą, wzorów). To zaskoczyło, bo NB2 zwykle przekręca polskie znaki.
- Bohater, miniaturki (line art), emblemat "K", grzbiet — wszystko w jednej
  palecie.

Wniosek: **Pro utrzymuje polską pisownię** na okładce znacznie lepiej niż NB2.
To zmienia bilans przy okładkach: dla wypalanego tekstu Pro jest realną opcją.

## Co musisz wiedzieć, zanim potraktujesz to jako gotowe do publikacji

1. **Blurb to tekst wymyślony przez model**, nie nasz kanoniczny ze specu. Jest
   niezły, ale ma marketingowy ton ("magicznego świata", wykrzyknik), który
   kłóci się z naszą zasadą "bez frazesów". To nie jest zredagowana treść.
2. **Logo "K" jest zmyślone** przez model, to nie jest prawdziwe "Kolorowe
   Skarby". Jeśli chcesz swój realny znak, ta część z definicji nie może być AI.
3. **Miniaturki to zmyślone aksolotki**, nie prawdziwe 40 wzorów z wnętrza.
4. **Geometria KDP niepewna**: tytuł i naklejka blisko górnej krawędzi, brak
   tytułu na grzbiecie (a przy 80 stronach KDP go dopuszcza), strefy bezpieczne
   niesprawdzone. Do realnego uploadu trzeba to zweryfikować.
5. **Pisownię i tak przejrzyj na pełnej rozdzielczości** — tu wygląda czysto,
   ale to output modelu.

## Dwa kierunki (decyzja)

- **A) Czysto AI (jak w tym teście)** — maksymalna spójność i efekt "wow", ale
  tekst, logo i miniaturki są zmyślone przez model, a zgodność z KDP wymaga
  ręcznej weryfikacji każdorazowo. Dobre na makiety, warianty koncepcyjne,
  inspirację.
- **B) Hybryda pod publikację** — model robi tło i bohatera (spójna scena), a
  skrypt składa prawdziwy tekst, logo, tytuł na grzbiet i realne miniaturki.
  Pewna pisownia i geometria, kosztem tego, że nie wszystko jest AI.

Próbka pokazała, że **A działa** i że **Pro utrzymuje polski**. Otwarte opcje na
dalsze prowadzenie:

- dogenerować 2-3 warianty A (inne układy/palety) do wyboru,
- zrobić wariant z kanonicznym blurbem (model używa dokładnie naszego tekstu),
- przełączyć się na B (publikowalna hybryda).

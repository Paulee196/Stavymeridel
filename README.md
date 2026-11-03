# Stavy měřidel pro Home Assistant – 0.2.1

Neoficiální integrace stavymeridel.cz s instalací přes HACS. Načítá odečty
studené vody, teplé vody a topení jednou denně. Přihlášení a aktuální stavy
verze 0.1.0 už byly ověřeny uživatelem. Historické statistiky verze 0.2.0
mají lokální testy; první ověření v Home Assistantu teprve proběhne.

## Nově: Energie a měsíční/roční přehledy

Jednotky stavů i měsíční/roční spotřeby: voda **m³** (tři desetinná místa,
tedy rozlišení na litry), topení na rozdělovačích **dílky** (celá čísla).
Jednotky jsou uložené jako metadata senzoru i historických statistik, aby je
standardní karty HA zobrazovaly také v grafech. Voda má třídu zařízení `water`.
Skutečná měřidla tepla v GJ/kWh si ponechávají jednotku zdroje.

- Import dostupných měsíčních odečtů z tabulek portálu do dlouhodobých statistik HA.
- Voda v m³ je k dispozici jako externí statistika pro panel **Energie → Voda**.
  V seznamu vybírejte položky s názvem **měsíční odečty**, nikoli původní senzor
  aktuálního stavu. Názvy obsahují typ vody, sériové číslo a kód bytu.
- Statistiky topení mají původní jednotky poskytovatele (u rozdělovačů dílky).
  Nejsou převáděny na kWh ani peníze. Zobrazí je karta **Statistický graf**.
- Každé měřidlo má také senzory **tento měsíc** a **tento rok**.
- Atribut původního senzoru `monthly_statistic_id` obsahuje identifikátor
  pro výběr v grafech. Statistiky mají ID `stavy_meridel:byt_KOD_TYP_SERIOVE_CISLO`.
- Archiv uchovává už stažené starší roky i po tom, co je portál přestane vracet.
  Je uložený lokálně v HA, nikoli na GitHubu.

### Přesnost a dostupná historie

Zdrojová tabulka poskytuje **měsíční** stavy. Celá známá spotřeba měsíce se v HA
ukládá do jeho prvního hodinového intervalu. Měsíční a roční součty tak patří
ke správnému období, ale denní a hodinový průběh není skutečné měření: v denním
pohledu se měsíční částka objeví první den měsíce. Aktuální měsíc je průběžný
předběžný součet a při dalším stažení se stejný záznam aktualizuje bez zdvojení.

První měsíc vody bez předchozího známého stavu nelze spočítat a vynechá se.
Chybějící měsíce se nerozdělují odhadem. Roční senzor s neúplnými podklady
má `year_incomplete: true` a ukazuje součet známých měsíců; nejde o celý rok.
Leden rozdělovačů topení v dílcích používá ročně nulovaný stav. U vody a
měřidel tepla v GJ/kWh se nulování nepředpokládá. Po výměně měřidla vznikne
nová série podle sériového čísla a její první neznámá spotřeba se nedopočítává.

Zdroj zpočátku požaduje minulý a aktuální rok stejně jako webový portál. Starší
roky, které portál v této odpovědi nevrací, nejsou automaticky dostupné. Dočasně
chybějící historická buňka nesmaže dříve archivovanou známou hodnotu.
`reading_period` není přesný čas skutečného měření; čas synchronizace jím také není.

## Instalace a aktualizace přes HACS

Repozitář: https://github.com/Paulee196/Stavymeridel

1. V HACS → nabídka → Vlastní repozitáře přidejte uvedenou URL, typ **Integrace**.
2. Vyhledejte **Stavy měřidel (experimentální)** a stáhněte integraci.
   Při aktualizaci z větve bez vydání použijte v detailu nabídku **Znovu stáhnout**.
3. Restartujte Home Assistant. Minimální verze HA je 2025.11.
4. Nastavení → Zařízení a služby → Přidat integraci → **Stavy měřidel**.
5. Zadejte účet uživatele bytu a desetimístný kód bytu. Při aktualizaci už
   existujícího nastavení se znovu nepřihlašujete.
6. Po úspěšné synchronizaci otevřete nastavení Energie, sekci Voda, a vyberte
   odpovídající statistiku s názvem **měsíční odečty**. Recorder importuje data
   na pozadí, proto se seznam může objevit až s malým zpožděním.

Studenou a teplou vodu lze sledovat samostatně. Nepřidávejte současně jejich
součet i oba dílčí zdroje do stejné celkové spotřeby, aby se voda nepočítala dvakrát.

## Graf po měsících a rocích

Na dashboard přidejte **Statistický graf**, vyberte externí statistiky měřidel,
statistiku **změna**, sloupcový graf a období **měsíc** nebo **rok**.
Vodu a topení dejte do samostatných grafů kvůli různým jednotkám.
Ukázka (ID nahraďte atributem `monthly_statistic_id` svého senzoru):

```yaml
type: statistics-graph
title: Spotřeba vody po měsících
chart_type: bar
period: month
days_to_show: 730
stat_types:
  - change
entities:
  - entity: stavy_meridel:byt_KOD_4_SERIOVE_CISLO
    name: Studená voda
  - entity: stavy_meridel:byt_KOD_2_SERIOVE_CISLO
    name: Teplá voda
```

Pro roční graf změňte `period` na `year`. Výběr období v panelu Energie
umožňuje procházet dostupné měsíce a roky.

## Ruční instalace

Zkopírujte `custom_components/stavy_meridel` do
`/config/custom_components/stavy_meridel`, restartujte HA a přidejte integraci.
Heslo se zadává pouze v HA. Je uložené v konfiguraci HA jako u jiných integrací;
chraňte i zálohy. Kód bytu, odečty a hesla nepatří do veřejného repozitáře.

## Ověření a diagnostika

Lokální testy: `python -m unittest discover -s tests -v` (Python, aiohttp, tzdata).
Testy používají umělé odpovědi, ne přihlašovací údaje účtu. Ověřují mimo jiné
měsíční zařazení, časové pásmo, reset topení, vynechané měsíce a opravy dat.
Testy neověřují běh recorderu ani UI Energie v konkrétním HA.

Volitelně `python probe.py` ověří přihlášení a parser lokálně; heslo zadává skrytě.
Nevypisuje ani neukládá token nebo hodnoty odečtů. Integrace neobchází CAPTCHA
ani ochranu prohlížeče. Neznámý formát API způsobí chybu místo nulových odečtů.

Zdroj protokolu: veřejná aplikace https://stavymeridel.cz/assets/index-Dxc54k7K.js
(login HTTP Basic, další požadavky Bearer token a role uživatele bytu).

Odinstalace: odeberte integraci v HA a potom její složku z `custom_components`.
Importované dlouhodobé statistiky ani lokální archiv se automaticky nemažou.

# Stavy měřidel pro Home Assistant – experimentální verze 0.1.0

Balíček je připravený k prvnímu ověření. Přihlášení skutečným účtem a běh v Home
Assistantu zatím nebyly otestované. Webové odečty byly ověřeny v přihlášeném portálu;
API klient vychází z veřejného JavaScriptu aplikace verze 1.38.0. Není to oficiální integrace poskytovatele.

## Co obsahuje

- Nastavení přihlašovacího jména, hesla a kódu bytu přes formulář v HA.
- Čtení topení, teplé a studené vody jednou za 24 hodin.
- Samostatné senzory podle sériových čísel a diagnostický senzor synchronizace.
- Obnovení přihlášení při HTTP 401 a nové zadání hesla při odmítnutí účtu.
- Změna nebo neznámý formát API způsobí chybu, nikoli dosazení nulových odečtů.

První verze záměrně nemá dlouhodobé statistiky, import historie ani napojení do
panelu Energie. Měsíční sloupec sám neposkytuje přesný čas odečtu a vodní senzor
by jinak mohl vykázat starší spotřebu v den stažení. Topení zůstává v dílcích
poskytovatele. Roční reset se zobrazí jako změna stavu, nepřepočítává se na spotřebu.

`reading_period` označuje měsíc sloupce, nikoli čas skutečného měření.
Čas úspěšné synchronizace také není časem měření. Senzory mohou být nedostupné,
pokud nejnovější sloupec nemá hodnotu nebo portál označí měřidlo za chybné.

## Instalace z GitHubu přes HACS

Repozitář: https://github.com/Paulee196/Stavymeridel

Po nahrání souborů do repozitáře:

1. V HACS otevřete nabídku → Vlastní repozitáře.
2. Vložte `https://github.com/Paulee196/Stavymeridel`, zvolte typ **Integrace** a přidejte jej.
3. Vyhledejte **Stavy měřidel (experimentální)** a stáhněte integraci.
4. Restartujte HA a přes Nastavení → Zařízení a služby → Přidat integraci
   přidejte **Stavy měřidel**. Zadejte přihlášení a kód bytu pouze zde.

Aktualizace kódu se pak distribuují stejným repozitářem. Zdrojový kód je veřejný,
ale přihlašovací údaje, kód vašeho bytu a odečty do repozitáře nepatří.
Manifest odkazuje na tento repozitář a jeho issues; správcem je `@Paulee196`.
Struktura už obsahuje `hacs.json`; instalace přes HACS dosud nebyla ověřena.

## Ruční instalace první zkušební verze

1. Rozbalte ZIP. Celou složku `custom_components/stavy_meridel` zkopírujte do
   `/config/custom_components/stavy_meridel` na Home Assistantu. Soubor
   `manifest.json` musí ležet přímo v této složce. Lze použít například Samba
   nebo již nainstalovaný Studio Code Server.
2. Restartujte Home Assistant.
3. Nastavení → Zařízení a služby → Přidat integraci → **Stavy měřidel**.
4. Zadejte účet běžného uživatele bytu a desetimístný kód bytu (mezery se odstraní).
   Heslo se zadává pouze zde; neposílejte ho do chatu. HA ho uloží do své konfigurace
   stejně jako přihlašovací údaje jiných integrací. Chraňte také zálohy HA.
5. Zkontrolujte, že všechny stavy souhlasí s portálem a že atribut `reading_period`
   odpovídá poslednímu měsíci. První verzi nepoužívejte pro fakturaci nebo ochranné automatizace.

Pokud se integrace nezobrazí, obnovte stránku HA po restartu. Pokud přidání selže,
ověřte přihlašovací údaje v portálu a případně použijte níže uvedený lokální test.
Integrace neobchází ověření prohlížeče ani CAPTCHA. Pokud je ochrana vyžadována
i před API, bude potřeba vyřešit přístup s poskytovatelem nebo zvolit jiný způsob.

## Volitelný lokální test před instalací

Na počítači s Pythonem a knihovnou aiohttp spusťte `python probe.py` z této složky.
Heslo se zadává skrytě a zůstává jen v paměti procesu. Test pošle přihlášení přímo
na `https://stavymeridel.cz`, načte tabulky a vypíše pouze jejich strukturu a počet
rozpoznaných měřidel. Neukládá odpovědi, token ani heslo. Bez úspěšného testu nelze
tvrdit, že formát skutečného API odpovídá parseru.

## Ověření provedené při přípravě

Automatické testy používají **umělé odpovědi**, nikoli zachycená data účtu.
Kontrolují mimo jiné neplatné číslo, chybějící hodnotu, budoucí sloupce,
roční reset, jednotky a obnovení přihlášení. Spuštění: `python -m unittest discover -s tests -v`.
Kontrola syntaxe neověřuje běh v HA; ten je potřeba dokončit při prvním nasazení.

## Zdroj protokolu a omezení

Veřejná aplikace: https://stavymeridel.cz/assets/index-Dxc54k7K.js

- GET `/odecty/login`, HTTP Basic; odpověď s `token`.
- Další čtení s `Authorization: Bearer …` a `roleId: 1` (uživatel bytu).
- GET `/odecty/apartments/byCode?code=…` pro interní ID bytu.
- GET `/odecty/apartment/{id}/dashboard?meterTypeID=…&year1=…&year2=…`.
- Typy 19 (případně -19), 2 a 4; tabulka `measurementsTable.headers/rows`;
  buňky s `value`, hlavičky s `key` a `label`.

Parser rozpoznává měsíční hlavičky podle českých názvů měsíců nebo číselného
zápisu. Neznámé schéma odmítne. Změny portálu mohou vyžadovat úpravu integrace.
Přímé přihlašování a stahování ze sítě HA, platnost tokenů a pravidelnost publikace
odečtů zůstávají neověřené. Balíček neobsahuje přihlašovací údaje ani snímky účtu.

Odinstalace: odeberte integraci v HA, potom její složku z `custom_components` a
restartujte HA. Odebrání neovlivňuje účet portálu ani měřidla.

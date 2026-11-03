"""Optional local account test. No response bodies or secrets are printed/saved."""
import asyncio
from datetime import date
from getpass import getpass
import importlib
from pathlib import Path
import re
import sys
import types

import aiohttp

package = types.ModuleType("portal_probe")
package.__path__ = [str(Path(__file__).parent / "custom_components/stavy_meridel")]
sys.modules[package.__name__] = package
api = importlib.import_module("portal_probe.api")
parser = importlib.import_module("portal_probe.parser")


async def main():
    username = input("Přihlašovací jméno: ").strip()
    password = getpass("Heslo (nezobrazuje se): ")
    code = re.sub(r"\s+", "", input("Desetimístný kód bytu: "))
    if not re.fullmatch(r"\d{10}", code):
        print("Kód musí mít 10 číslic.")
        return 1
    async with aiohttp.ClientSession() as session:
        client = api.PortalClient(session, username, password, code)
        try:
            await client.login()
            apartment = await client.get("apartments/byCode", {"code": code})
            if not isinstance(apartment.get("id"), int):
                print("V odpovědi chybí číselné ID bytu.")
                return 1
            year = date.today().year
            for kind in (19, 2, 4):
                data = await client.get(f"apartment/{apartment['id']}/dashboard",
                                        {"meterTypeID": kind, "year1": year - 1, "year2": year})
                table = data.get("measurementsTable", {})
                print(f"Typ {kind}: tabulka={isinstance(table, dict)}, "
                      f"řádků={len(table.get('rows', [])) if isinstance(table, dict) else '?'}")
                # Only schema field names and monthly-column recognition, never cell values.
                if isinstance(table, dict):
                    print("Pole tabulky:", sorted(table.keys()))
                    print("Rozpoznané měsíční sloupce:", sum(
                        parser.period_from_header(h) is not None
                        for h in table.get("headers", [])
                    ))
            readings = await client.fetch()
            print(f"OK: přihlášení a parsování funguje, měřidel={len(readings)}.")
            return 0
        except api.AuthError:
            print("Přihlášení odmítnuto. Heslo ani token nejsou vypsané.")
        except api.ApiError as err:
            print(f"Test selhal: {err}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

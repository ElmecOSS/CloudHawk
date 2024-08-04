# ______________________________________________________
#  Author: Cominoli Luca, Dalle Fratte Andrea
#  License: GNU GPLv3
#  Copyright (C) 2022  Elmec Informatica S.p.A.

#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ______________________________________________________
from os import environ


def token_init():
    # Preleva token da variabile d'ambiente
    token = environ.get("token_jwt", None)

    # Se non settato in variabile d'ambiente legge file
    if token == None:
        # Aperto file in append creandolo se non esistente
        open("./token_jwt", "a")
        # Aperto file in lettura
        with open("./token_jwt", "r") as token_file:
            token = token_file.read()

    # Se ancora non settato, errore
    if token == '':
        exit("Token JWT non inserito in file e nemmeno in variabile")

    # token = "JWT "+token
    # Trim e rimozione carattere a capo
    token = token.strip()
    token = token.replace('\n', '')

    environ["token_jwt"] = token


def get_vault_url():
    endpoint = ""

    if environ["environment"] == "Prod":
        endpoint = "https://elmec-vault.elmec.ad:8200"
    else:
        endpoint = "https://elmec-vault-devel.elmec.ad:8200"

    return endpoint


def set_vault_token():
    header = {}
    header = {
        "X-Vault-Token": environ["vault_jwt"],
    }

    return header

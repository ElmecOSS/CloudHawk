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
import os
import json
from threading import Thread

import boto3
from os import environ
import requests

from src.main import multi_account_region_invoker


def __list_all_regions(aws_access_key_id, aws_secret_access_key, aws_session_token):
    if aws_session_token is None:
        ec2client = boto3.client('ec2',
                                 aws_access_key_id=aws_access_key_id,
                                 aws_secret_access_key=aws_secret_access_key
                                 )
    else:
        ec2client = boto3.client('ec2',
                                 aws_access_key_id=aws_access_key_id,
                                 aws_secret_access_key=aws_secret_access_key,
                                 aws_session_token=aws_session_token,
                                 )
    return [region['RegionName'] for region in ec2client.describe_regions()['Regions']]


def token_init():
    # Preleva token da variabile d'ambiente
    token = environ.get("token_jwt", None)

    # Se non settato in variabile d'ambiente legge file
    if token is None:
        # Aperto file in append creandolo se non esistente
        open("../token_jwt", "a")
        # Aperto file in lettura
        with open("../token_jwt", "r") as token_file:
            token = token_file.read()

    # Se ancora non settato, errore
    if token == "":
        exit("Token JWT non inserito in file e nemmeno in variabile")

    # token = "JWT "+token
    # Trim e rimozione carattere a capo
    token = token.strip()
    token = token.replace("\n", "")

    environ["token_jwt"] = token


def get_vault_url():
    return "https://elmec-vault.elmec.ad:8200"


def set_vault_token():
    header = {}
    header = {
        "X-Vault-Token": environ["vault_jwt"],
    }

    return header


def main():
    accounts_id = []

    # JWT Token Init
    token_init()
    vault_url = get_vault_url()
    # Estrazione vault token
    token_response = requests.post(
        url=f"{vault_url}/v1/auth/jwt/login",
        data={"jwt": environ["token_jwt"]},
        verify=False,
    )
    if token_response.status_code == 200:
        vault_jwt = token_response.json()["auth"]["client_token"]

        for account_id in accounts_id:
            # threads = []
            credentials_response = requests.post(
                url=f"{vault_url}/v1/aws/sts/aws-quick-setup",
                headers={"X-Vault-Token": vault_jwt},
                data={"role_arn": f"arn:aws:iam::{account_id}:role/ElmecVaultAccessRole"},
                verify=False,
            )
            credential = json.loads(credentials_response.text)
            aws_access_key_id = credential["data"]["access_key"]
            aws_secret_access_key = credential["data"]["secret_key"]
            aws_session_token = credential["data"]["security_token"]
            print(f"Credenziali ottenute per l'account {account_id}")
            if credentials_response.status_code == 200:
                for region in __list_all_regions(aws_access_key_id, aws_secret_access_key, aws_session_token):
                    print(f"Run for {account_id} - {region}")
                    multi_account_region_invoker(f"{account_id}.log", region, aws_access_key_id, aws_secret_access_key,
                                                 aws_session_token)

                #     thread = Thread(target=multi_account_region_invoker, args=(f"{account_id}.log", region,
                #                                                                aws_access_key_id,
                #                                                                aws_secret_access_key,
                #                                                                aws_session_token,))
                #     threads.append(thread)
                #
                # for thread in threads:
                #     thread.start()
                #
                # for thread in threads:
                #     thread.join()
                # input("Continua")


if __name__ == "__main__":
    main()

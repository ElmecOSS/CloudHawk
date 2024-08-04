# ______________________________________________________
#  Author: Cominoli Luca, Dalle Fratte Andrea
#  GitHub Source Code: https://github.com/ElmecOSS/CloudHawk
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

import argparse
import logging
import sys
from threading import Thread
from time import perf_counter

from utility import Utility

import boto3
import urllib3
# Import listing class
from ElmecAWSResourceLister.resource_lister import ResourceLister

# Import callback class
from callbacks import Callbacks

urllib3.disable_warnings()

# Logging system initialization
LOGGER = logging.getLogger()
for h in LOGGER.handlers:
    LOGGER.removeHandler(h)

HANDLER = logging.StreamHandler(sys.stdout)
FORMAT = "%(levelname)s %(asctime)s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"
HANDLER.setFormatter(logging.Formatter(FORMAT))
LOGGER.addHandler(HANDLER)


# # Inizializzazione del logger
# LOGGER = logging.getLogger()
# FORMAT = "%(levelname)s %(asctime)s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"
# FORMATTER = logging.Formatter(FORMAT)


# def multi_account_region_invoker(file_log_name, aws_region, aws_access_key_id, aws_secret_access_key,
#                                  aws_session_token):
#     from os import environ
#     event = {}
#
#     # Aggiungi un handler per scrivere i log su file
#     file_handler = logging.FileHandler(file_log_name)
#     file_handler.setFormatter(FORMATTER)
#     LOGGER.addHandler(file_handler)
#
#     # Aggiungi anche l'handler per lo standard output
#     console_handler = logging.StreamHandler(sys.stdout)
#     console_handler.setFormatter(FORMATTER)
#     LOGGER.addHandler(console_handler)
#
#     # Imposta il livello di log del logger
#     LOGGER.setLevel(logging.INFO)
#
#     event["filter_tag_key"] = environ.get("filter_tag_key", "")
#     event["filter_tag_value"] = environ.get("filter_tag_value", "")
#     event["aws_region"] = aws_region
#     event["aws_access_key_id"] = aws_access_key_id
#     event["aws_secret_access_key"] = aws_secret_access_key
#     event["aws_session_token"] = aws_session_token
#     lambda_handler(event, "")


def __use_credentials_as_params(event):
    return 'aws_access_key_id' in event and 'aws_secret_access_key' in event and 'aws_session_token' in event


def lambda_handler(event, context):
    from os import environ

    """
    main function
    """
    try:
        if "log" not in environ:
            LOGGER.setLevel(logging.INFO)
        else:
            LOGGER.setLevel(environ["log"])

        parser = argparse.ArgumentParser()
        parser.add_argument(
            '--exclude', help='Comma separated list of excluded services', default=environ.get("exclude", ""))
        parser.add_argument(
            '--include', help='Comma separated list of included services', default=environ.get("include", ""))
        parser.add_argument('--filter_tag_key', help='Key of the tag to filter',
                            default=event.get("filter_tag_key", environ.get("filter_tag_key", "")))
        parser.add_argument('--filter_tag_value', help='Value of the tag to filter',
                            default=event.get("filter_tag_value", environ.get("filter_tag_value", "")))
        parser.add_argument('--aws_region', help='AWS Region',
                            default=event.get("aws_region", environ.get("aws_region", "")))
        parser.add_argument('--sns_topic_name',
                            help='SNS Topic name (or multiple names splitted with ;) used as destination for alarm/ok actions. Must be in the same region of the scanned resources.',
                            default=environ.get("sns_topic_name", "Elmec-CardinalisNotifier"))
        parser.add_argument('--sns_topic_arn',
                            help='SNS Topic arn used as destination for alarm/ok actions. If set has more priority over sns_topic_name.',
                            default=environ.get("sns_topic_arn", None))
        parser.add_argument('--aws_account_alias_key', help='Name of the label that can identify your AWS account',
                            default=environ.get("aws_account_alias_key", ""))
        parser.add_argument('--aws_account_alias_value',
                            help='A custom alias for your AWS Account that will be shown inside a JSON in the "AlarmDescription"',
                            default=environ.get("aws_account_alias_value", ""))
        parser.add_argument('--alarm_prefix', help='Prefix used inside CloudWath alarm names',
                            default=environ.get("alarm_prefix", ""))
        parser.add_argument('--db_table_name', help='Name of the DynamoDB table used for alarm granularity',
                            default=environ.get("db_table_name", ""))
        parser.add_argument('--default_values_file_path', help='Path where you can find default_values.json override file',
                            default=environ.get("default_values_file_path", ""))

        # Load From Args
        args = parser.parse_args()

        services_excluded = args.__dict__["exclude"].lower()
        services_included = args.__dict__["include"].lower()

        if len(services_excluded) > 0 and len(services_included) > 0:
            raise Exception("Exclude and Include can't be used together")

        # Merge required variables (key-value) da environment variables e arguments
        required_variables = ["filter_tag_key", "filter_tag_value", "aws_region",
                              "aws_account_alias_key", "aws_account_alias_value", "alarm_prefix"]

        # Set environment variables from arguments
        for required_variable in required_variables:
            environ[required_variable] = str(
                args.__dict__.get(required_variable))
            if environ[required_variable] == "":
                raise Exception(
                    f"Required variable not set (from environment or as argument): {required_variable}")
            LOGGER.debug(f"{required_variable}: {environ[required_variable]}")

        environ["region"] = environ.get("aws_region", event["aws_region"])

        if __use_credentials_as_params(event):
            environ["account_id"] = boto3.client("sts",
                                                 aws_access_key_id=event["aws_access_key_id"],
                                                 aws_secret_access_key=event["aws_secret_access_key"],
                                                 aws_session_token=event["aws_session_token"],
                                                 region_name=environ.get("aws_region"),
                                                 ).get_caller_identity().get("Account")
        else:
            environ["account_id"] = boto3.client("sts").get_caller_identity().get("Account")

        if ('sns_topic_arn' in args.__dict__) and (args.__dict__['sns_topic_arn'] is not None):
            environ["sns_topic_arn"] = args.__dict__['sns_topic_arn']
        elif ('sns_topic_name' in args.__dict__) and (args.__dict__['sns_topic_name'] is not None):
            environ["sns_topic_arn"] = "arn:aws:sns:" + environ["region"] + \
                                       ":" + environ["account_id"] + ":" + environ["sns_topic_name"]
        else:
            raise Exception('Almeno un valore tra sns_topic_name e sns_topic_arn deve esistere')

        # JSON file reading
        default_values = Utility.get_full_default_values_file()

        # Boto3 client initialization for supported services
        clients = {
            "ec2": None,
            "rds": None,
            "elbv2": None,
            "efs": None,
            "eks": None,
            "acm": None,
            "opensearch": None,
            "directconnect": None,
            "dynamodb": None,
            "elasticache": None,
            "fsx": None,
            "globalaccelerator": None,
            "lambda": None,
            "ecs": None
        }
        static_regions = {
            "globalaccelerator": "us-west-2"
        }

        if 'sns_topic_arn' in args.__dict__:
            environ["sns_topic_arn_globalaccelerator"] = environ["sns_topic_arn"]
        else:
            environ["sns_topic_arn_globalaccelerator"] = "arn:aws:sns:" + static_regions["globalaccelerator"] + \
                                                         ":" + environ["account_id"] + ":" + environ["sns_topic_name"]

        # Client initialization
        if __use_credentials_as_params(event):
            cloudwatchclient = boto3.client("cloudwatch",
                                            aws_access_key_id=event["aws_access_key_id"],
                                            aws_secret_access_key=event["aws_secret_access_key"],
                                            aws_session_token=event["aws_session_token"],
                                            region_name=environ["region"])
        else:
            cloudwatchclient = boto3.client("cloudwatch", region_name=environ["region"])

        # Exclude = all services except excluded
        if len(services_excluded) > 0 or (len(services_excluded) == 0 and len(services_included) == 0):
            for client in clients:
                if client not in services_excluded:
                    region_to_use = environ["region"] if client not in static_regions else static_regions[client]
                    if __use_credentials_as_params(event):
                        clients[client] = boto3.client(client,
                                                       aws_access_key_id=event["aws_access_key_id"],
                                                       aws_secret_access_key=event["aws_secret_access_key"],
                                                       aws_session_token=event["aws_session_token"],
                                                       region_name=region_to_use, verify=False)
                    else:
                        clients[client] = boto3.client(client, region_name=region_to_use, verify=False)

        # Include = no services except included
        if len(services_included) > 0:
            for client in clients:
                if client in services_included:
                    region_to_use = environ["region"] if client not in static_regions else static_regions[client]
                    if __use_credentials_as_params(event):
                        clients[client] = boto3.client(client,
                                                       aws_access_key_id=event["aws_access_key_id"],
                                                       aws_secret_access_key=event["aws_secret_access_key"],
                                                       aws_session_token=event["aws_session_token"],
                                                       region_name=region_to_use, verify=False)
                    else:
                        clients[client] = boto3.client(client, region_name=region_to_use, verify=False)

        start_time = perf_counter()
        resource_lister = ResourceLister(
            filter_tag_key=environ["filter_tag_key"], filter_tag_value=environ["filter_tag_value"])

        # Resource extraction with the chosen tag

        if clients["ec2"] is not None:
            try:
                ec2 = Thread(target=resource_lister.list_ec2,
                             args=(clients["ec2"],
                                   [{"Name": "tag:" + environ["filter_tag_key"],
                                     "Values": [environ["filter_tag_value"]]}, {
                                        "Name": "instance-state-name",
                                        "Values": ["pending", "running", "stopping", "stopped"]}],
                                   Callbacks.callback_ec2,
                                   (cloudwatchclient, default_values["EC2"])))
                ec2.start()
                ec2.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service ec2 excluded by user due to ec2 client exclusion")

        if clients["ec2"] is not None:
            try:
                ebs = Thread(target=resource_lister.list_ebs,
                             args=(clients["ec2"],
                                   [{"Name": "tag:" + environ["filter_tag_key"], "Values": [
                                       environ["filter_tag_value"]]}, {"Name": "status", "Values": ["in-use"]}],
                                   Callbacks.callback_ebs,
                                   (cloudwatchclient, default_values["EBS"])))
                ebs.start()
                ebs.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service ebs excluded by user due to ec2 client exclusion")

        if clients["rds"] is not None:
            try:
                rds = Thread(target=resource_lister.list_rds,
                             args=(clients["rds"],
                                   None,
                                   None,
                                   Callbacks.callback_rds, (cloudwatchclient, default_values["RDS"])))
                rds.start()
                rds.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service rds excluded by user due to rds client exclusion")

        if clients["elbv2"] is not None:
            try:
                elb = Thread(target=resource_lister.list_elb,
                             args=(clients["elbv2"],
                                   None,
                                   Callbacks.callback_elb,
                                   (cloudwatchclient, default_values["ALB"], default_values["NLB"])))
                elb.start()
                elb.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service elb excluded by user due to elbv2 client exclusion")

        if clients["elbv2"] is not None:
            try:
                elb_tg = Thread(target=resource_lister.list_elbtg,
                                args=(clients["elbv2"],
                                      None,
                                      Callbacks.callback_elb_tg,
                                      (cloudwatchclient, default_values["ALBTG"], default_values["NLBTG"])))
                elb_tg.start()
                elb_tg.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service elb_tg excluded by user due to elbv2 client exclusion")

        if clients["efs"] is not None:
            try:
                efs = Thread(target=resource_lister.list_efs,
                             args=(clients["efs"],
                                   None,
                                   Callbacks.callback_efs,
                                   (cloudwatchclient, default_values["EFS"])))
                efs.start()
                efs.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service efs excluded by user due to efs client exclusion")

        if clients["eks"] is not None:
            try:
                eks = Thread(target=resource_lister.list_eks,
                             args=(clients["eks"],
                                   None,
                                   Callbacks.callback_eks,
                                   (cloudwatchclient, default_values["EKS"])))
                eks.start()
                eks.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service eks excluded by user due to eks client exclusion")

        if clients["ec2"] is not None:
            try:
                vpn = Thread(target=resource_lister.list_vpn,
                             args=(clients["ec2"],
                                   None,
                                   Callbacks.callback_vpn,
                                   (cloudwatchclient, default_values["VPN"])))
                vpn.start()
                vpn.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service vpn excluded by user due to ec2 client exclusion")

        if clients["acm"] is not None:
            try:
                acm = Thread(target=resource_lister.list_acm,
                             args=(clients["acm"],
                                   #    {"RenewalEligibility": "INELIGIBLE"},
                                   None,
                                   Callbacks.callback_acm,
                                   (cloudwatchclient, default_values["ACM"])))
                acm.start()
                acm.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service acm excluded by user due to acm client exclusion")

        if clients["opensearch"] is not None:
            try:
                opensearch = Thread(target=resource_lister.list_os,
                                    args=(clients["opensearch"],
                                          None,
                                          Callbacks.callback_os,
                                          (cloudwatchclient, default_values["OpenSearch"])))
                opensearch.start()
                opensearch.join()

            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service opensearch excluded by user due to opensearch client exclusion")

        if clients["directconnect"] is not None:
            try:
                directconnect = Thread(target=resource_lister.list_directconnect,
                                       args=(clients["directconnect"],
                                             None,
                                             Callbacks.callback_directconnect,
                                             (cloudwatchclient, default_values["DirectConnect"])))
                directconnect.start()
                directconnect.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service directconnect excluded by user due to directconnect client exclusion")

        if clients["dynamodb"] is not None:
            try:
                dynamodb = Thread(target=resource_lister.list_dynamodb,
                                  args=(clients["dynamodb"],
                                        None,
                                        Callbacks.callback_dynamodb,
                                        (cloudwatchclient, default_values["DynamoDB"])))
                dynamodb.start()
                dynamodb.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service dynamodb excluded by user due to dynamodb client exclusion")

        if clients["elasticache"] is not None:
            try:
                elasticache = Thread(target=resource_lister.list_elasticache,
                                     args=(clients["elasticache"],
                                           None,
                                           Callbacks.callback_elasticache,
                                           (cloudwatchclient, default_values["ElastiCache"])))
                elasticache.start()
                elasticache.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service elasticache excluded by user due to elasticache client exclusion")

        if clients["fsx"] is not None:
            try:
                fsx = Thread(target=resource_lister.list_fsxs,
                             args=(clients["fsx"],
                                   None,
                                   Callbacks.callback_fsx,
                                   (cloudwatchclient, default_values["FSX"])))
                fsx.start()
                fsx.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service fsx excluded by user due to fsx client exclusion")

        if clients["globalaccelerator"] is not None:
            try:
                # Client initialization
                if __use_credentials_as_params(event):
                    cloudwatchclient_global_ax = boto3.client("cloudwatch",
                                                    aws_access_key_id=event["aws_access_key_id"],
                                                    aws_secret_access_key=event["aws_secret_access_key"],
                                                    aws_session_token=event["aws_session_token"],
                                                    region_name=static_regions["globalaccelerator"])
                else:
                    cloudwatchclient_global_ax = boto3.client("cloudwatch", region_name=static_regions["globalaccelerator"])
                globalaccelerator = Thread(target=resource_lister.list_globalaccelerator,
                                           args=(clients["globalaccelerator"],
                                                 None,
                                                 Callbacks.callback_globalaccelerator,
                                                 (cloudwatchclient_global_ax, default_values["GlobalAccelerator"])))
                globalaccelerator.start()
                globalaccelerator.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service globalaccelerator excluded by user due to globalaccelerator client exclusion")

        if clients["lambda"] is not None:
            try:
                lambda_thread = Thread(target=resource_lister.list_lambda,
                                       args=(clients["lambda"],
                                             None,
                                             Callbacks.callback_lambda,
                                             (cloudwatchclient, default_values["Lambda"])))
                lambda_thread.start()
                lambda_thread.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info(
                "Service lambda excluded by user due to lambda client exclusion")

        if clients["ecs"] is not None:
            try:
                lambda_thread = Thread(target=resource_lister.list_ecs,
                                       args=(clients["ecs"],
                                             None,
                                             Callbacks.callback_ecs,
                                             (cloudwatchclient, default_values["ECS"])))
                lambda_thread.start()
                lambda_thread.join()
            except Exception as error:
                LOGGER.error(error)
        else:
            LOGGER.info("Service ecs excluded by user due to ecs client exclusion")

        end_time = perf_counter()
        print(f"Completed after {end_time - start_time: 0.2f} second(s).")

    except Exception as e:
        LOGGER.error(e)


if __name__ == "__main__":
    from os import environ

    event = {}

    event["filter_tag_key"] = environ.get("filter_tag_key", "")
    event["filter_tag_value"] = environ.get("filter_tag_value", "")
    event["region"] = environ.get("region", "")
    event["aws_region"] = environ.get("aws_region", "")

    lambda_handler(event, "")

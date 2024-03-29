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

import logging
import sys
import boto3
import json
from threading import Thread
from time import perf_counter
import argparse
from os import environ


# Import listing class
from ElmecAWSResourceLister.resource_lister import ResourceLister


# Import callback class
from callbacks import Callbacks

# Logging system initialization
LOGGER = logging.getLogger()
for h in LOGGER.handlers:
    LOGGER.removeHandler(h)

HANDLER = logging.StreamHandler(sys.stdout)
FORMAT = "%(levelname)s %(asctime)s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"
HANDLER.setFormatter(logging.Formatter(FORMAT))
LOGGER.addHandler(HANDLER)


def lambda_handler(event, context):
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
        parser.add_argument('--sns_topic_name', help='SNS Topic name (or multiple names splitted with ;) used as destination for alarm/ok actions. Must be in the same region of the scanned resources.',
                            default=environ.get("sns_topic_name", ""))
        parser.add_argument('--aws_account_alias_key', help='Name of the label that can identify your AWS account',
                            default=environ.get("aws_account_alias_key", ""))
        parser.add_argument('--aws_account_alias_value', help='A custom alias for your AWS Account that will be shown inside a JSON in the "AlarmDescription"',
                            default=environ.get("aws_account_alias_value", ""))
        parser.add_argument('--alarm_prefix', help='Prefix used inside CloudWath alarm names',
                            default=environ.get("alarm_prefix", ""))
        parser.add_argument('--db_table_name', help='Name of the DynamoDB table used for alarm granularity',
                            default=environ.get("db_table_name", ""))

        # Load From Args
        args = parser.parse_args()

        services_excluded = args.__dict__["exclude"].lower()
        services_included = args.__dict__["include"].lower()

        if len(services_excluded) > 0 and len(services_included) > 0:
            raise Exception("Exclude and Include can't be used together")

        # Merge required variables (key-value) da environment variables e arguments
        required_variables = ["filter_tag_key", "filter_tag_value", "aws_region", "sns_topic_name",
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
        environ["account_id"] = boto3.client(
            "sts").get_caller_identity().get("Account")

        environ["sns_topic_arn"] = "arn:aws:sns:"+environ["region"] + \
            ":"+environ["account_id"]+":"+environ["sns_topic_name"]

        # JSON file reading
        with open("default_values.json") as json_file:
            default_values = json.load(json_file)

        # Boto3 client initialization for supported services
        # Boto3 client initialization for supported services
        services = {
            "ec2": {
                "boto_client": "ec2",
                "excluded": True

            },
            "rds": {
                "boto_client": "rds",
                "excluded": True

            },
            "elbv2": {
                "boto_client": "elbv2",
                "excluded": True

            },
            "efs": {
                "boto_client": "efs",
                "excluded": True

            },
            "eks": {
                "boto_client": "eks",
                "excluded": True

            },
            "vpn": {
                "boto_client": "ec2",
                "excluded": True
            },
            "acm": {
                "boto_client": "acm",
                "excluded": True
            },
            "opensearch": {
                "boto_client": "opensearch",
                "excluded": True
            }
        }
        # Client initialization
        cloudwatchclient = boto3.client(
            "cloudwatch", region_name=environ["region"])

        # Exclude = all services except excluded
        if len(services_excluded) > 0 or (len(services_excluded) == 0 and len(services_included) == 0):
            for service in services:
                if service not in services_excluded:
                    # Replace boto_client name with boto client object
                    services[service]["excluded"] = False
                    services[service]["boto_client"] = boto3.client(
                        services[service]["boto_client"], region_name=environ["region"])


        # Include = no services except included
        if len(services_included) > 0:
            for service in services:
                if service in services_included:
                    # Replace boto_client name with boto client object
                    services[service]["excluded"] = False
                    services[service]["boto_client"] = boto3.client(
                        services[service]["boto_client"], region_name=environ["region"])

        start_time = perf_counter()
        resource_lister = ResourceLister(
            filter_tag_key=environ["filter_tag_key"], filter_tag_value=environ["filter_tag_value"])

        # Resource extraction with the chosen tag

        if services["ec2"]["excluded"]:
            LOGGER.info(
                "EC2 resources skipped due to user exclusion")
        else:
            try:
                ec2 = Thread(target=resource_lister.list_ec2,
                             args=(services["ec2"]["boto_client"],
                                   [{"Name": "tag:" + environ["filter_tag_key"], "Values": [environ["filter_tag_value"]]}, {
                                       "Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}],
                                   Callbacks.callback_ec2,
                                   (cloudwatchclient,  default_values["EC2"])))
                ec2.start()
                ec2.join()
            except Exception as error:
                LOGGER.error(error)


        if services["ec2"]["excluded"]:
            LOGGER.info(
                "EBS resources skipped due to user exclusion of EC2 client")
        else:
            try:
                ebs = Thread(target=resource_lister.list_ebs,
                             args=(services["ec2"]["boto_client"],
                                   [{"Name": "tag:" + environ["filter_tag_key"], "Values": [
                                    environ["filter_tag_value"]]}, {"Name": "status", "Values": ["in-use"]}],
                                   Callbacks.callback_ebs,
                                   (cloudwatchclient, default_values["EBS"])))
                ebs.start()
                ebs.join()
            except Exception as error:
                LOGGER.error(error)


        if services["rds"]["excluded"]:
            LOGGER.info(
                "RDS resources skipped due to user exclusion")
        else:
            try:
                rds = Thread(target=resource_lister.list_rds,
                             args=(services["rds"]["boto_client"],
                                   None,
                                   None,
                                   Callbacks.callback_rds, (cloudwatchclient, default_values["RDS"])))
                rds.start()
                rds.join()
            except Exception as error:
                LOGGER.error(error)


        if services["elbv2"]["excluded"]:
            LOGGER.info(
                "ELB resources skipped due to user exclusion")
        else:
            try:
                elb = Thread(target=resource_lister.list_elb,
                             args=(services["elbv2"]["boto_client"],
                                   None,
                                   Callbacks.callback_elb,
                                   (cloudwatchclient, default_values["ALB"], default_values["NLB"])))
                elb.start()
                elb.join()
            except Exception as error:
                LOGGER.error(error)


        if services["elbv2"]["excluded"]:
            LOGGER.info(
                "ELB Target Groups resources skipped due to user exclusion of ELB client")
        else:
            try:
                elb_tg = Thread(target=resource_lister.list_elbtg,
                                args=(services["elbv2"]["boto_client"],
                                      None,
                                      Callbacks.callback_elb_tg,
                                      (cloudwatchclient, default_values["ALBTG"], default_values["NLBTG"])))
                elb_tg.start()
                elb_tg.join()
            except Exception as error:
                LOGGER.error(error)


        if services["efs"]["excluded"]:
            LOGGER.info(
                "EFS resources skipped due to user exclusion")
        else:
            try:
                efs = Thread(target=resource_lister.list_efs,
                             args=(services["efs"]["boto_client"],
                                   None,
                                   Callbacks.callback_efs,
                                   (cloudwatchclient, default_values["EFS"])))
                efs.start()
                efs.join()
            except Exception as error:
                LOGGER.error(error)


        if services["eks"]["excluded"]:
            LOGGER.info(
                "EKS resources skipped due to user exclusion")
        else:
            try:
                eks = Thread(target=resource_lister.list_eks,
                             args=(services["eks"]["boto_client"],
                                   None,
                                   Callbacks.callback_eks,
                                   (cloudwatchclient, default_values["EKS"])))
                eks.start()
                eks.join()
            except Exception as error:
                LOGGER.error(error)


        if services["vpn"]["excluded"]:
            LOGGER.info(
                "VPN resources skipped due to user exclusion")
        else:
            try:
                vpn = Thread(target=resource_lister.list_vpn,
                             args=(services["vpn"]["boto_client"],
                                   None,
                                   Callbacks.callback_vpn,
                                   (cloudwatchclient, default_values["VPN"])))
                vpn.start()
                vpn.join()
            except Exception as error:
                LOGGER.error(error)


        if services["acm"]["excluded"]:
            LOGGER.info(
                "ACM resources skipped due to user exclusion")
        else:
            try:
                acm = Thread(target=resource_lister.list_acm,
                             args=(services["acm"]["boto_client"],
                                   #    {"RenewalEligibility": "INELIGIBLE"},
                                   None,
                                   Callbacks.callback_acm,
                                   (cloudwatchclient, default_values["ACM"])))
                acm.start()
                acm.join()
            except Exception as error:
                LOGGER.error(error)


        if services["opensearch"]["excluded"]:
            LOGGER.info(
                "OpenSearch resources skipped due to user exclusion")
        else:
            try:
                opensearch = Thread(target=resource_lister.list_os,
                                    args=(services["opensearch"]["boto_client"],
                                          None,
                                          Callbacks.callback_os,
                                          (cloudwatchclient, default_values["OpenSearch"])))
                opensearch.start()
                opensearch.join()

            except Exception as error:
                LOGGER.error(error)


        end_time = perf_counter()
        print(f"Completed after {end_time- start_time: 0.2f} second(s).")

    except Exception as e:
        LOGGER.error(e)


if __name__ == "__main__":
    from os import environ
    event = {}

    event["filter_tag_key"] = environ.get("filter_tag_key", "")
    event["filter_tag_value"] = environ.get("filter_tag_value", "")
    event["aws_region"] = environ.get("aws_region", "")

    lambda_handler(event, "")

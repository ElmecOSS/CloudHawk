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

# Import listing class
from resource_lister.resource_lister import ResourceLister

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
LOGGER.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    main function
    """
    try:
        import os
        os.environ["region"] = event["aws_region"]
        os.environ["account_id"] = boto3.client(
            "sts").get_caller_identity().get("Account")
        os.environ["sns_topic_arn"] = "arn:aws:sns:"+os.environ["region"]+":"+os.environ["account_id"]+":"+os.environ["sns_topic_name"]

        # JSON file reading
        with open("default_values.json") as json_file:
            default_values = json.load(json_file)

        # Boto3 client initialization for supported services
        cloudwatchclient = boto3.client(
            "cloudwatch", region_name=os.environ["region"])
        ec2client = boto3.client("ec2", region_name=os.environ["region"])
        rdsclient = boto3.client("rds", region_name=os.environ["region"])
        elbclient = boto3.client("elbv2", region_name=os.environ["region"])
        efsclient = boto3.client("efs", region_name=os.environ["region"])
        eksclient = boto3.client("eks", region_name=os.environ["region"])
        acmclient = boto3.client("acm", region_name=os.environ["region"])
        osclient = boto3.client("opensearch", region_name=os.environ["region"])

        start_time = perf_counter()
        resource_lister = ResourceLister(
            filter_tag_key=event["filter_tag_key"], filter_tag_value=event["filter_tag_value"])

        # Resource extraction with the chosen tag
        ec2 = Thread(target=resource_lister.list_ec2,
                     args=(ec2client,
                           [{"Name": "tag:" + event["filter_tag_key"], "Values": [event["filter_tag_value"]]}, {
                               "Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}],
                           Callbacks.callback_ec2,
                           (cloudwatchclient,  default_values["EC2"])))
        ebs = Thread(target=resource_lister.list_ebs,
                     args=(ec2client,
                           [{"Name": "tag:" + event["filter_tag_key"], "Values": [
                               event["filter_tag_value"]]}, {"Name": "status", "Values": ["in-use"]}],
                           Callbacks.callback_ebs,
                           (cloudwatchclient, default_values["EBS"])))
        rds = Thread(target=resource_lister.list_rds,
                     args=(rdsclient,
                           None,
                           None,
                           Callbacks.callback_rds, (cloudwatchclient, default_values["RDS"])))
        elb = Thread(target=resource_lister.list_elb,
                     args=(elbclient,
                           None,
                           Callbacks.callback_elb,
                           (cloudwatchclient, default_values["ALB"], default_values["NLB"])))
        elb_tg = Thread(target=resource_lister.list_elbtg,
                        args=(elbclient,
                            None,
                            Callbacks.callback_elb_tg,
                            (cloudwatchclient, default_values["ALBTG"], default_values["NLBTG"])))
        efs = Thread(target=resource_lister.list_efs,
                     args=(efsclient,
                           None,
                           Callbacks.callback_efs,
                           (cloudwatchclient, default_values["EFS"])))
        eks = Thread(target=resource_lister.list_eks,
                     args=(eksclient,
                           None,
                           Callbacks.callback_eks,
                           (cloudwatchclient, default_values["EKS"])))
        vpn = Thread(target=resource_lister.list_vpn,
                     args=(ec2client,
                           None,
                           Callbacks.callback_vpn,
                           (cloudwatchclient, default_values["VPN"])))
        acm = Thread(target=resource_lister.list_acm,
                     args=(acmclient,
                           {"RenewalEligibility": "INELIGIBLE"},
                           Callbacks.callback_acm,
                           (cloudwatchclient, default_values["ACM"])))
        os = Thread(target=resource_lister.list_os,
                    args=(osclient,
                          None,
                          Callbacks.callback_os,
                          (cloudwatchclient, default_values["OpenSearch"])))

        ec2.start()
        ebs.start()
        rds.start()
        elb.start()
        elb_tg.start()
        efs.start()
        eks.start()
        vpn.start()
        acm.start()
        os.start()

        ec2.join()
        ebs.join()
        rds.join()
        elb.join()
        elb_tg.join()
        efs.join()
        eks.join()
        vpn.join()
        acm.join()
        os.join()

        end_time = perf_counter()
        print(f"Completed after {end_time- start_time: 0.2f} second(s).")

    except Exception as e:
        LOGGER.error(e)


if __name__ == "__main__":
    import os
    event = {}
    if "filter_tag_key" in os.environ and "filter_tag_value" in os.environ and "aws_region" in os.environ and "sns_topic_name" in os.environ:
        event["filter_tag_key"] = os.environ["filter_tag_key"]
        event["filter_tag_value"] = os.environ["filter_tag_value"]
        event["aws_region"] = os.environ["aws_region"]
    else:
        raise Exception("Required environment variables not exported")
    lambda_handler(event, "")

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
import os

from utility import Utility

LOGGER = logging.getLogger()


class CloudWatchELB:
    """
    Encapsulates Amazon CloudWatch ELB functions.
    """

    def __init__(self, elb, cloudwatchclient, default_values):
        ciname = ""
        if "Tags" not in elb:
            LOGGER.error("elb {elb_arn} does not have Tags".format(
                elb_arn=elb["LoadBalancerArn"]))

        elb_tags = elb.get("Tags", [])
        cluster_name_result = list(
            filter(lambda tag: tag["Key"] == "eks:cluster-name", elb_tags))
        if len(cluster_name_result) > 0:
            LOGGER.info("Balancer managed by eks cluster")
            ciname = cluster_name_result[0]["Value"]

        # Kubernetes Cluster Managed
        if ciname == "":
            kube_name_result = list(
                filter(lambda tag: "kubernetes.io/cluster/" in tag["Key"], elb_tags))
            if len(kube_name_result) > 0:
                LOGGER.info("Balancer managed by eks cluster")
                ciname = Utility.get_name_from_kubetag(
                    kube_name_result[0]["Key"])
                cloudid = "arn:aws:eks:"+os.getenv("region")+":"+os.getenv(
                    "account_id")+":cluster/"+cluster_name_result[0]["Value"]

        # Basic Instance
        if ciname == "":
            ciname = elb["LoadBalancerName"]
            cloudid = elb.get("LoadBalancerArn", "")

        # Extract the metrics available for the db's type and engine
        metric_needed = {}
        for metric_name in default_values:
            all_types_allowed = "Types" not in default_values[metric_name]["MetricSpecifications"]
            if all_types_allowed or (not all_types_allowed and elb["Type"] in default_values[metric_name]["MetricSpecifications"]["Types"]):
                metric_needed[metric_name] = default_values[metric_name]

        # Richiama creazione metriche estratte
        for metric_name in metric_needed:
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchELB, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    elb, ciname, cloudwatchclient, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=elb["LoadBalancerName"],
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchELB,
                                            elb,
                                            ciname,
                                            elb["LoadBalancerArn"],
                                            alarm_values,
                                            [{
                                                "Name": "LoadBalancer",
                                                "Value": elb["LoadBalancerArn"].split(":")[-1].replace("loadbalancer/", "")
                                            }],
                                            cloudwatchclient
                                            )


class CloudWatchELBTG:
    """Encapsulates Amazon CloudWatch ELBTG functions."""

    def __init__(self, targetgroup, cloudwatchclient, default_values):
        ciname = ""
        cloudid = ""
        if "Tags" not in targetgroup:
            LOGGER.error(
                "targetgroup {targetgroup} does not have Tags".format(targetgroup=targetgroup["LoadBalancerArn"]))

        # Kubernetes Cluster Managed
        elbtg_tags = targetgroup.get("Tags", [])
        cluster_name_result = list(
            filter(lambda tag: tag["Key"] == "eks:cluster-name", elbtg_tags))
        if len(cluster_name_result) > 0:
            LOGGER.info("Targetgroup managed by eks cluster")
            ciname = cluster_name_result[0]["Value"]
            cloudid = "arn:aws:eks:"+os.getenv("region")+":"+os.getenv(
                "account_id")+":cluster/"+cluster_name_result[0]["Value"]

        # Kubernetes Cluster Managed
        if ciname == "":
            kube_name_result = list(
                filter(lambda tag: "kubernetes.io/cluster/" in tag["Key"], elbtg_tags))
            if len(kube_name_result) > 0:
                LOGGER.info("Targetgroup managed by eks cluster")
                ciname = Utility.get_name_from_kubetag(
                    kube_name_result[0]["Key"])
                cloudid = "arn:aws:eks:"+os.getenv("region")+":"+os.getenv(
                    "account_id")+":cluster/"+cluster_name_result[0]["Value"]
                    
        if ciname == "":
            ciname = targetgroup["LoadBalancerArns"][0].split("/")[-2]
            cloudid = targetgroup["LoadBalancerArns"][0]

        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        for metric_name in metric_needed:
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchELBTG, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    targetgroup, ciname, cloudwatchclient, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=targetgroup["TargetGroupName"],
                    default_values=default_values)

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchELBTG,
                                            targetgroup,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [
                                                {
                                                    "Name": "TargetGroup",
                                                    "Value": targetgroup["TargetGroupArn"].split(":")[-1]
                                                },
                                                {
                                                    "Name": "LoadBalancer",
                                                    "Value": targetgroup["LoadBalancerArns"][0].split(":")[-1].replace("loadbalancer/", "")
                                                }
                ],
                    cloudwatchclient)

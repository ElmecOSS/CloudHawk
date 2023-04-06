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

from cw_services.cw_wrapper import CloudWatchWrapper
from utility import Utility

LOGGER = logging.getLogger()


class CloudWatchEKS:
    """
    Encapsulates Amazon CloudWatch EKS functions.
    """

    @staticmethod
    def cluster_failed_node_count_core_dynamic(eks, ciname, cloudid, cloudwatchclient, default_values):
        """
        Core Override specific for ClusterFailedNodeCount metrics
        """
        # Extract metric list regarding partitions
        metric_name = "EKS_cluster_failed_node_count"
        params = {
            "Namespace": "ContainerInsights",
            "MetricName": "cluster_failed_node_count",
            "Dimensions": [
                {
                    "Name": "ClusterName",
                    "Value": eks["name"]
                }
            ],
            "RecentlyActive": "PT3H"
        }
        eks_metrics = CloudWatchWrapper.list_metrics(cloudwatchclient, params)
        # Extraction of all disks other than temporary ones
        for diskmetric in eks_metrics["Metrics"]:
            alarm_values = Utility.get_default_parameters(
                monitoring_id=metric_name,
                item_id=eks["name"],
                default_values=default_values)

            threshold = alarm_values["MetricSpecifications"]["Threshold"]
            if "DynamicThreshold" in default_values[metric_name]["MetricSpecifications"]:
                threshold = getattr(
                    CloudWatchEKS, default_values[metric_name]["MetricSpecifications"]["DynamicThreshold"])(eks, alarm_values)

            eventtype = None
            monitorcomponent = None
            impact = None
            if "CardinalisData" in alarm_values:
                eventtype = alarm_values["CardinalisData"]["EventType"]
                monitorcomponent = alarm_values["CardinalisData"]["MonitorComponent"]
                impact = alarm_values["CardinalisData"]["Impact"]
                del alarm_values["CardinalisData"]
            del alarm_values["MetricSpecifications"]
            alarm_values["Threshold"] = threshold
            alarm_values["Dimensions"] = diskmetric["Dimensions"]
            CloudWatchWrapper.create_metric_alarm(
                cloudwatchclient,
                ci=ciname,
                cloudid=cloudid,
                eventtype=eventtype,
                monitorcomponent=monitorcomponent,
                impact=impact,
                kwargs={
                    **alarm_values
                })

    def __init__(self, eks, cloudwatchclient, default_values):
        # Extract valid metrics for resource type and engine
        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            ciname = eks["name"]
            cloudid = eks["arn"]
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchEKS, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    eks, ciname, cloudid, cloudwatchclient, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    eks_identifier=eks["name"],
                    default_values=default_values)

                # Check if metric needs to be created or not
                creation = True
                if "DynamicCreation" in metric_needed[metric_name]["MetricSpecifications"]:
                    creation = getattr(CloudWatchEKS, metric_needed[metric_name]["MetricSpecifications"]["DynamicCreation"])(
                        eks, alarm_values)

                if not creation:
                    continue

                # Check wheter the metric needs dynamic threshold
                threshold = alarm_values["MetricSpecifications"]["Threshold"]
                if "DynamicThreshold" in metric_needed[metric_name]["MetricSpecifications"]:
                    threshold = getattr(
                        CloudWatchEKS, metric_needed[metric_name]["MetricSpecifications"]["DynamicThreshold"])(eks, alarm_values)

                eventtype = alarm_values["CardinalisData"]["EventType"]
                monitorcomponent = alarm_values["CardinalisData"]["MonitorComponent"]
                impact = alarm_values["CardinalisData"]["Impact"]
                del alarm_values["CardinalisData"]
                del alarm_values["MetricSpecifications"]
                alarm_values["Threshold"] = threshold

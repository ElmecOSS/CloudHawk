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
import re
import os
import boto3

from cw_services.cw_wrapper import CloudWatchWrapper
from utility import Utility

LOGGER = logging.getLogger()


class CloudWatchEC2:
    """
    Encapsulates Amazon CloudWatch EC2 functions.
    """

    @staticmethod
    def set_et_mc(monitoring_id, platform_detail, eksnode, default_values, specific_values):
        """
        This method is used to set custom EventType and MonitororComponent for EC2 monitoring
        :return: monitoring item details
        """
        # Check if cardinalis data is specified in json
        if "CardinalisData" not in specific_values[monitoring_id]:
            return specific_values[monitoring_id]

        # Event Type/Monitor Component Mapping based on O.S.
        # https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/billing-info-fields.html
        if eksnode:
            specific_values[monitoring_id]["CardinalisData"]["EventType"] = specific_values[monitoring_id]["CardinalisData"]["EventType"]["eks"]
            specific_values[monitoring_id]["CardinalisData"]["MonitorComponent"] = specific_values[
                monitoring_id]["CardinalisData"]["MonitorComponent"]["eks"]
        # elif "windows" in platform_detail.lower() or "sql server" in platform_detail.lower():
        #     specific_values[monitoring_id]["CardinalisData"]["EventType"] = specific_values[
        #         monitoring_id]["CardinalisData"]["EventType"]["windows"]
        #     specific_values[monitoring_id]["CardinalisData"]["MonitorComponent"] = specific_values[
        #         monitoring_id]["CardinalisData"]["MonitorComponent"]["windows"]
        else:
            specific_values[monitoring_id]["CardinalisData"]["EventType"] = specific_values[
                monitoring_id]["CardinalisData"]["EventType"]["ec2"]
            specific_values[monitoring_id]["CardinalisData"]["MonitorComponent"] = specific_values[
                monitoring_id]["CardinalisData"]["MonitorComponent"]["ec2"]

        return specific_values[monitoring_id]

    @staticmethod
    def disk_root_check(diskmetric):
        """
        This method is used to check if the passed disk is the root
        :return: True or False
        """
        return Utility.get_value_from_dict(diskmetric["Dimensions"], "Name", "path", "Value") == "/"

    @staticmethod
    def memusedpercent_core_dynamic(instance, ciname, cloudid, eksnode, cloudwatchclient, metric_name, default_values):
        """
        Core Override specific for Memory Usage metrics
        """
        platform_detail = instance.get("PlatformDetails", "")

        # List of metrics about partitions
        memmetrics = CloudWatchWrapper.list_metrics(cloudwatchclient, {"Namespace": "CWAgent", "MetricName": "mem_used_percent",
                                                                       "Dimensions": [
                                                                           {"Name": "InstanceId", "Value": instance["InstanceId"]}],
                                                                       "RecentlyActive": "PT3H"})["Metrics"]

        for memmetric in memmetrics:
            alarm_values = Utility.get_default_parameters(
                monitoring_id=metric_name,
                item_id=instance["InstanceId"],
                default_values=default_values,
                cb=CloudWatchEC2.set_et_mc,
                extra_params={
                    "monitoring_id": metric_name,
                    "platform_detail": instance.get("PlatformDetails", ""),
                    "eksnode": eksnode,
                    "default_values": default_values
                }
            )

            threshold = alarm_values["MetricSpecifications"]["Threshold"]
            if "DynamicThreshold" in default_values[metric_name]["MetricSpecifications"]:
                threshold = getattr(CloudWatchEC2, default_values[metric_name]["MetricSpecifications"]["DynamicThreshold"])(
                    instance, alarm_values)

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
            alarm_values["Dimensions"] = memmetric["Dimensions"]
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

    @staticmethod
    def diskusedpercent_core_dynamic(instance, ciname, cloudid, eksnode, cloudwatchclient, metric_name, default_values):
        """
        Core Override specific for Disk Usage metrics (Linux)
        """
        platform_detail = instance.get("PlatformDetails", "")

        filter_key = {
            "key": "Name",
            "excepted_key_value": "path",
            "excepted_value": "Value"
        }
        diskname_key = {
            "key": "Name",
            "excepted_key_value": "device",
            "excepted_value": "Value"
        }

        # List of metrics about partitions
        diskmetrics = CloudWatchWrapper.list_metrics(cloudwatchclient, {"Namespace": "CWAgent", "MetricName": "disk_used_percent",
                                                                        "Dimensions": [
                                                                            {"Name": "InstanceId", "Value": instance["InstanceId"]}],
                                                                        "RecentlyActive": "PT3H"})

        sanitized_dimensions = Utility.sanitize_metrics(
            cloudwatchclient, diskmetrics["Metrics"], filter_key)

        # Extract of all disks other than temporary ones
        for diskmetric in sanitized_dimensions:
            diskname = Utility.get_value_from_dict(
                diskmetric["Dimensions"], diskname_key["key"], diskname_key["excepted_key_value"], diskname_key["excepted_value"])
            # FSType filtering (only if the path is not root)
            is_wanted_type_disk = True
            if not CloudWatchEC2.disk_root_check(diskmetric):
                is_wanted_type_disk = Utility.get_value_from_dict(
                    diskmetric["Dimensions"], "Name", "fstype", "Value") not in ["tmpfs", "overlay", "nfs4", "devtmpfs", "cifs", "nfs", "squashfs", "vfat"]
            else:
                diskname = "Root"
            # PATH filtering
            there_is_no_kubelet = "kubelet" not in Utility.get_value_from_dict(
                diskmetric["Dimensions"], "Name", "path", "Value")
            if is_wanted_type_disk and there_is_no_kubelet:

                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id_components=[diskname, instance["InstanceId"]],
                    default_values=default_values,
                    cb=CloudWatchEC2.set_et_mc,
                    extra_params={
                        "monitoring_id": metric_name,
                        "platform_detail": platform_detail,
                        "eksnode": eksnode,
                        "default_values": default_values
                    }
                )

                threshold = alarm_values["MetricSpecifications"]["Threshold"]
                if "DynamicThreshold" in default_values[metric_name]["MetricSpecifications"]:
                    threshold = getattr(CloudWatchEC2, default_values[metric_name]["MetricSpecifications"]["DynamicThreshold"])(
                        instance, alarm_values)

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

    @staticmethod
    def diskfreepercent_core_dynamic(instance, ciname, cloudid, eksnode, cloudwatchclient, metric_name, default_values):
        """
        Core Override specific for Disk Free metrics (Windows)
        """
        platform_detail = instance.get("PlatformDetails", "")

        filter_key = {
            "key": "Name",
            "excepted_key_value": "instance",
            "excepted_value": "Value"
        }
        diskname_key = {
            "key": "Name",
            "excepted_key_value": "instance",
            "excepted_value": "Value"
        }

        # List of metrics about partitions
        diskmetrics = CloudWatchWrapper.list_metrics(cloudwatchclient, {"Namespace": "CWAgent", "MetricName": "disk_free_percent",
                                                                        "Dimensions": [
                                                                            {"Name": "InstanceId", "Value": instance["InstanceId"]}],
                                                                        "RecentlyActive": "PT3H"})

        sanitized_dimensions = Utility.sanitize_metrics(
            cloudwatchclient, diskmetrics["Metrics"], filter_key)

        # Extract of all disks other than temporary ones
        for diskmetric in sanitized_dimensions:
            diskname = Utility.get_value_from_dict(
                diskmetric["Dimensions"], diskname_key["key"], diskname_key["excepted_key_value"], diskname_key["excepted_value"]).replace(":", "")
            # FSType filtering (only if the path is not root)
            is_wanted_type_disk = True
            if not CloudWatchEC2.disk_root_check(diskmetric):
                is_wanted_type_disk = Utility.get_value_from_dict(
                    diskmetric["Dimensions"], "Name", "fstype", "Value") not in ["tmpfs", "overlay", "nfs4", "devtmpfs", "cifs", "nfs", "squashfs", "vfat"]
            else:
                diskname = "Root"
            # PATH filtering
            there_is_no_kubelet = "kubelet" not in Utility.get_value_from_dict(
                diskmetric["Dimensions"], "Name", "path", "Value")
            if is_wanted_type_disk and there_is_no_kubelet:

                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id_components=[diskname, instance["InstanceId"]],
                    default_values=default_values,
                    cb=CloudWatchEC2.set_et_mc,
                    extra_params={
                        "monitoring_id": metric_name,
                        "platform_detail": platform_detail,
                        "eksnode": eksnode,
                        "default_values": default_values
                    }
                )

                threshold = alarm_values["MetricSpecifications"]["Threshold"]
                if "DynamicThreshold" in default_values[metric_name]["MetricSpecifications"]:
                    threshold = getattr(CloudWatchEC2, default_values[metric_name]["MetricSpecifications"]["DynamicThreshold"])(
                        instance, alarm_values)

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

    @staticmethod
    def networksharemount_core_dynamic(instance, ciname, cloudid, eksnode, cloudwatchclient, metric_name, default_values):
        """
        Core Override specific for Network Share Mount metrics (custom)
        """
        platform_detail = instance.get("PlatformDetails", "")

        filter_key = {}
        diskname_key = {}
        if "windows" in platform_detail.lower() or "sql server" in platform_detail.lower():
            filter_key = {
                "key": "Name",
                "excepted_key_value": "instance",
                "excepted_value": "Value"
            }
            diskname_key = {
                "key": "Name",
                "excepted_key_value": "instance",
                "excepted_value": "Value"
            }
        else:
            filter_key = {
                "key": "Name",
                "excepted_key_value": "path",
                "excepted_value": "Value"
            }
            diskname_key = {
                "key": "Name",
                "excepted_key_value": "device",
                "excepted_value": "Value"
            }

        # List of metrics about partitions
        diskmetrics = CloudWatchWrapper.list_metrics(cloudwatchclient, {"Namespace": "CWAgent", "MetricName": "disk_used_percent",
                                                                        "Dimensions": [
                                                                            {"Name": "InstanceId", "Value": instance["InstanceId"]}],
                                                                        "RecentlyActive": "PT3H"})

        sanitized_dimensions = Utility.sanitize_metrics(
            cloudwatchclient, diskmetrics["Metrics"], filter_key)

        # Extract of all disks other than temporary ones
        for diskmetric in sanitized_dimensions:
            diskname = Utility.get_value_from_dict(
                diskmetric["Dimensions"], "Name", "path", "Value")
            # FSType filtering (only if the path is not root)
            is_wanted_type_disk = False
            is_wanted_type_disk = Utility.get_value_from_dict(
                diskmetric["Dimensions"], "Name", "fstype", "Value") in ["nfs4", "cifs", "nfs"]
            # PATH filtering
            there_is_no_kubelet = "kubelet" not in Utility.get_value_from_dict(
                diskmetric["Dimensions"], "Name", "path", "Value")
            if is_wanted_type_disk and there_is_no_kubelet:

                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id_components=[diskname, instance["InstanceId"]],
                    default_values=default_values,
                    cb=CloudWatchEC2.set_et_mc,
                    extra_params={
                        "monitoring_id": metric_name,
                        "platform_detail": instance.get("PlatformDetails", ""),
                        "eksnode": eksnode,
                        "default_values": default_values
                    }
                )

                threshold = alarm_values["MetricSpecifications"]["Threshold"]
                if "DynamicThreshold" in default_values[metric_name]["MetricSpecifications"]:
                    threshold = getattr(CloudWatchEC2, default_values[metric_name]["MetricSpecifications"]["DynamicThreshold"])(
                        instance, alarm_values)

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

    @staticmethod
    def cpucreditbalance_creation_dynamic(instance, alarm_values):
        """
        Creation condition for CPUCreditBalance metrics
        :return: if the metrics needs to be created or not
        """
        # Check if regex match
        return re.fullmatch(alarm_values["MetricSpecifications"]["RegexType"], instance["InstanceType"]) is not None

    def __init__(self, instance, cloudwatchclient, default_values):
        # CI Name extraction
        LOGGER.info(instance.get("PlatformDetails", ""))
        ciname = ""
        cloudid = instance.get("InstanceId", "")
        eksnode = False
        autoscaling = False

        cluster_name_result = Utility.get_name_from_kubetag(instance["Tags"])
        # Kubernetes Cluster Managed

        if cluster_name_result != "":
            LOGGER.info("Instance managed by eks cluster")
            ciname = cluster_name_result
            cloudid = "arn:aws:eks:"+os.getenv("region")+":"+os.getenv(
                "account_id")+":cluster/"+cluster_name_result
            eksnode = True

        # Autoscaling Managed
        if ciname == "":
            autoscaling_name_result = list(
                filter(lambda tag: tag["Key"] == "aws:autoscaling:groupName", instance["Tags"]))
            if len(autoscaling_name_result) > 0:
                LOGGER.info("Instance managed by autoscaling group")
                ciname = autoscaling_name_result[0]["Value"]
                autoscaling_client = boto3.client(
                    "autoscaling", region_name=os.getenv("region"))
                cloudid = autoscaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[
                                                                          autoscaling_name_result[0]["Value"]])["AutoScalingGroups"][0]["AutoScalingGroupARN"]
                autoscaling = True

        # Basic Instance
        if ciname == "":
            name_result = list(
                filter(lambda tag: tag["Key"] == "Name", instance["Tags"]))
            if len(name_result) > 0:
                ciname = name_result[0]["Value"]

        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchEC2, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    instance, ciname, cloudid, eksnode, cloudwatchclient, metric_name, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=instance["InstanceId"],
                    default_values=default_values,
                    cb=CloudWatchEC2.set_et_mc,
                    extra_params={
                        "monitoring_id": metric_name,
                        "platform_detail": instance.get("PlatformDetails", ""),
                        "eksnode": eksnode,
                        "default_values": default_values
                    }
                )

                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchEC2,
                                            instance,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [{
                                                "Name": "InstanceId",
                                                "Value": instance["InstanceId"]
                                            }],
                                            cloudwatchclient
                                            )

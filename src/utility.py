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

import copy
import json
import logging
import os
from datetime import datetime, timedelta

import boto3
from boto3.dynamodb.conditions import Key

from cw_services.cw_wrapper import CloudWatchWrapper

LOGGER = logging.getLogger()


class Utility:
    """
    Encapsulates Utility functions.
    """

    @staticmethod
    def get_value_from_dict(array, key, excepted_key_value, excepted_value):
        """
        This method is used to extract the value from a desired key inside a dictionary.
        array = [{'Name': 'path', 'Value': '/'}]
        In this case:
        - key = Name
        - excepted_key_value = Path
        - excepted_value = Value
        :return:: value of the desired key
        """
        for item in array:
            if item[key] == excepted_key_value:
                return item[excepted_value]
        return ""

    @staticmethod
    def get_name_from_kubetag(tags):
        """
        This method is used to extract the name of the EKS cluster from the resource tag.
        The key can have one of the following format (KEY:VALUE): 
        - kubernetes.io/cluster/[CLUSTERNAME]: owned
        - eks:cluster-name: [CLUSTERNAME]
        - elbv2.k8s.aws/cluster: [CLUSTERNAME]
        :return:: nome of the cluster (if present)
        """

        # Check if cluster is managed
        desired_tags_values = ["elbv2.k8s.aws/cluster", "eks:cluster-name"]
        desired_tags_key = ["kubernetes.io/cluster/"]
        for tag in tags:
            for desired_tag in desired_tags_values:
                if desired_tag in tag["Key"]:
                    return tag["Value"]
            for desired_tag in desired_tags_key:
                if desired_tag in tag["Key"]:
                    return tag["Key"].split("/")[-1]

        return ""

    @staticmethod
    def sanitize_metrics(cloudwatchclient, metrics, filter_key):
        # Single metric, no action needeed
        if len(metrics) == 1 or len(metrics) == 0:
            return metrics
        # Present multiple metrics, need to figure out which to use
        else:
            result_metric = []
            # Group by dimension based on a passed parameter
            grouped_metric = {}
            for metric in metrics:
                local_key = Utility.get_value_from_dict(
                    metric["Dimensions"], filter_key["key"], filter_key["excepted_key_value"],
                    filter_key["excepted_value"])
                if local_key not in grouped_metric:
                    grouped_metric[local_key] = []
                grouped_metric[local_key].append(metric)

            for key in grouped_metric:
                local_metrics = grouped_metric[key]

                metric_data_queries = []
                for index, metric in enumerate(local_metrics):
                    metric_data_queries.append(
                        {
                            "Id": f"m_{index}",
                            "MetricStat": {
                                "Metric": metric,
                                "Period": 60,
                                "Stat": "Average"
                            }
                        },
                    )
                # Extract datapoints of each metric
                # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch.html#CloudWatch.Client.get_metric_data
                metrics_data_results = cloudwatchclient.get_metric_data(
                    MetricDataQueries=metric_data_queries,
                    StartTime=datetime.now() - timedelta(hours=3),
                    EndTime=datetime.now(),
                    ScanBy="TimestampDescending"
                )

                tmp_metric_evaluator = {
                    "max_timestamp": datetime(2000, 1, 1),
                    "metric": None
                }
                # Extract metric whose last datapoint is most recent
                for metrics_data_result in metrics_data_results["MetricDataResults"]:
                    if len(metrics_data_result["Timestamps"]) > 0 and (tmp_metric_evaluator["metric"] is None or (
                            tmp_metric_evaluator["metric"] is not None and metrics_data_result["Timestamps"][00] >
                            tmp_metric_evaluator["max_timestamp"])):
                        tmp_metric_evaluator["metric"] = local_metrics[int(
                            metrics_data_result["Id"].split("_")[1])]
                        tmp_metric_evaluator["max_timestamp"] = metrics_data_result["Timestamps"][00]

                if tmp_metric_evaluator["metric"] is not None:
                    result_metric.append(tmp_metric_evaluator["metric"])
            return result_metric

    @staticmethod
    def search_item_with_and_without_hyphen(dynamodb_table, alarm_to_search):
        override_values = dynamodb_table.query(KeyConditionExpression=Key(
            "AlarmName").eq(f"{alarm_to_search}"))["Items"]

        if len(override_values) == 0:
            # Search only for AlarmName removing '-' at the end
            override_values_without_hyphen = dynamodb_table.query(
                KeyConditionExpression=Key("AlarmName").eq(f"{alarm_to_search[:-1]}"))["Items"]

            if len(override_values_without_hyphen) > 0:
                override_values = override_values_without_hyphen

        return override_values

    @staticmethod
    def get_default_parameters(monitoring_id, default_values, item_id=None, item_id_components=None, cb=None,
                               extra_params=None):
        """
        :param cb: callback, a reference to a function that needs to be invoked only if it is valued. The only requirement is that function return the entire monitoring detail 
        as its return is assigned to specific_value[monitoring_id]. For an example see the 'set_et_mc' in 'cw_ec2'
        :param extra_param: map with the keys identical to the parameters specified in the cb method signature
        """
        # dymanodb_table initialization with monitoring table reference
        dynamodb_table = None
        db_table_name = os.getenv("db_table_name", None)
        db_region = os.environ["region"]
        if db_table_name is not None and db_region is not None:
            dynamodbresource = boto3.resource(
                "dynamodb", region_name=db_region)
            dynamodb_table = dynamodbresource.Table(db_table_name)

        # Creating dictionary copy to avoid altering data read from default_values.
        # Altering data directly avoids compromising multiple callback for the same check (e.g. multiple disks).
        # Used 'deepcopy' to prevent the new variable from being not simply a link to the memory address but an actual copy
        # Source: https://stackoverflow.com/questions/2465921/how-to-copy-a-dictionary-and-only-edit-the-copy
        specific_values = copy.deepcopy(default_values)

        override_value = {}
        if item_id is not None:
            item_id_components = [item_id]

        if "alarm_prefix" in os.environ:
            alarm_name_prefix = os.environ["alarm_prefix"] + "-" + \
                                specific_values[monitoring_id]["MetricSpecifications"]["AlarmName"]
        else:
            alarm_name_prefix = specific_values[monitoring_id]["MetricSpecifications"]["AlarmName"]

        specific_values[monitoring_id]["AlarmName"] = alarm_name_prefix + \
                                                      "-".join(item_id_el for item_id_el in item_id_components)

        if dynamodb_table is not None:
            while len(item_id_components) > 0:
                local_id = "-".join(item_id_el for item_id_el in item_id_components)
                # Force "-" at the end of the variable
                if local_id[:-1] != "-":
                    local_id = f"{local_id}-"

                # Read from database
                # Search for AlarmName with ItemID
                override_values = Utility.search_item_with_and_without_hyphen(
                    dynamodb_table, alarm_name_prefix + local_id)

                if len(override_values) > 0:
                    override_value = override_values[0]
                    break
                item_id_components.pop()

            if len(item_id_components) == 0 and override_value == {}:
                override_values = Utility.search_item_with_and_without_hyphen(
                    dynamodb_table, alarm_name_prefix)

                if len(override_values) > 0:
                    override_value = override_values[0]

        # Check if the dynamo column is present in default_json (even in subgroups)
        for key in override_value:
            processed = False
            # Check for nested subgroups
            for nested_key in specific_values[monitoring_id]:
                # Check if the attribute contains a dictionary
                if isinstance(specific_values[monitoring_id][nested_key], dict):
                    if key in specific_values[monitoring_id][nested_key]:
                        specific_values[monitoring_id][nested_key][key] = override_value[key]
                        processed = True
            if not processed:
                # If it exists it is ovewritten otherwise it is appended
                specific_values[monitoring_id][key] = override_value[key]

        if cb is not None:
            specific_values[monitoring_id] = cb(
                **extra_params, specific_values=specific_values)

        return specific_values[monitoring_id]

    @staticmethod
    def default_core_method(metric, class_to_invoke, item, ciname, cloudid, alarm_values, dimensions, cloudwatchclient,
                            alarm_type=None):
        """
        :return: = True (alarm created) / False (alarm not created)
        """
        # Check if the metric needs to be created or not
        creation = True
        if "DynamicCreation" in metric["MetricSpecifications"]:
            creation = getattr(class_to_invoke, metric["MetricSpecifications"]["DynamicCreation"])(
                item, alarm_values)

        if not creation:
            return False

        # Check whether the metric needs dynamic thresholding
        threshold = alarm_values["MetricSpecifications"]["Threshold"]
        if "DynamicThreshold" in metric["MetricSpecifications"]:
            threshold = getattr(class_to_invoke, metric["MetricSpecifications"]["DynamicThreshold"])(
                item, alarm_values)

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
        alarm_values["Dimensions"] = dimensions
        CloudWatchWrapper.create_metric_alarm(
            cloudwatchclient,
            ci=ciname,
            cloudid=cloudid,
            eventtype=eventtype,
            monitorcomponent=monitorcomponent,
            impact=impact,
            alarm_type=alarm_type,
            kwargs={
                **alarm_values
            }
        )
        return True

    @staticmethod
    def get_full_default_values_file():
        file_name = "default_values.json"
        external_path = os.getenv('default_values_file_path')  # Final / is required
        if external_path is not None:
            s3_resource = boto3.resource('s3')
            obj = s3_resource.Object("cloudhawk-default-values-rewrite-file", f"{external_path}{file_name}")
            default_values = json.loads(obj.get()['Body'].read().decode('utf-8'))
        else:
            with open(file_name) as json_file:
                default_values = json.load(json_file)

        return default_values

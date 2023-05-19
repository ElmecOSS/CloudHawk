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

import json
import logging
import os
import decimal

LOGGER = logging.getLogger()


class CloudWatchWrapper:
    """
    Encapsulates Amazon CloudWatch functions.
    """

    # Workaround to convert DynamoDB "decimal" type
    # REF: https://github.com/boto/boto3/issues/369#issuecomment-157205696
    @staticmethod
    def replace_decimals(obj):
        if isinstance(obj, list):
            for i in range(len(obj)):
                obj[i] = CloudWatchWrapper.replace_decimals(obj[i])
            return obj
        elif isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = CloudWatchWrapper.replace_decimals(v)
            return obj
        elif isinstance(obj, decimal.Decimal):
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj)
        else:
            return obj

    @staticmethod
    def list_metrics(cloudwatchclient, kwargs):
        """
        Gets the metrics within a namespace that have the specified name.
        If the metric has no dimensions, a single metric is returned.
        Otherwise, metrics for all dimensions are returned.

        :param *Namespace: The metric namespace to filter against.
        :param *MetricName: The name of the metric to filter against.
        :param *Dimensions: The dimensions to filter against.
        :param RecentlyActive: (Optional) To filter the results to show only metrics that have had data points published in the past three hours, specify this parameter with a value of PT3H
        :return:: An iterator that yields the retrieved metrics.
        """
        try:
            metrics = cloudwatchclient.list_metrics(**kwargs)

            LOGGER.info("Got metrics for %s.%s.",
                        kwargs["Namespace"], kwargs["MetricName"])
        except:
            LOGGER.exception("Couldn't get metrics for %s.%s.", kwargs.get("Namespace", None),
                             kwargs.get("MetricName", None))
            raise
        else:
            return metrics

    @staticmethod
    def create_metric_alarm(cloudwatchclient, kwargs, ci="", cloudid="", eventtype="", monitorcomponent="", impact=3):
        """
        Creates an alarm that watches a metric.

        :param cloudwatchclient: Boto3 "cloudwatchclient" resource
        :param ci: (Default empty) Elmec Atlantis Cardinalis CI Item
        :param cloudid: (Default empty) Resource Identifier
        :param eventtype: (Default empty) Elmec Event Type
        :param monitorcomponent: (Default empty) Elmec Monitor Component
        :param impact: (default 3) Elmec Event Impact
        :param AlarmName (string): The name for the alarm. This name must be unique within the Region.
        :param AlarmDescription: The description of the alarm.
        :param Statistic (list): The metric statistics, other than percentile.
        :param ExtendedStatistics (list): The percentile statistics. Specify values between p0.0 and p100.
        :param Dimensions (list): The dimensions for the metric specified in MetricName.
        :param Period (integer): The length, in seconds, used each time the metric specified in MetricName is evaluated.
        :param Unit (string): The  of measure for the statistic.
        :param EvaluationPeriods (integer): The number of periods over which data is compared to the specified threshold
        :param DatapointsToAlarm (integer): The number of data points that must be breaching to trigger the alarm.
        :param Threshold (float): The value against which the specified statistic is compared.
        :param ComparisonOperator (string): The arithmetic operation to use when comparing the specified statistic and threshold. The specified statistic value is used as the first operand.
        :parma TreatMissingData (string): Sets how this alarm is to handle missing data points.
        :param Namespace: The namespace of the metric.
        :param MetricName: The name of the metric.
        :return:: The newly created alarm.
        """

        # Check if AlarmDescription has not been explicitly specified
        alarmdescription = ""
        alarm = None
        if "AlarmDescription" not in kwargs:
            jsonalarmdescription = {}
            if "aws_account_alias_key" in os.environ and "aws_account_alias_value" in os.environ:
                jsonalarmdescription[os.environ["aws_account_alias_key"]
                                     ] = os.environ["aws_account_alias_value"]
            elif "aws_account_alias_key" not in os.environ and "aws_account_alias_value" in os.environ:
                jsonalarmdescription["account_alias"] = os.environ["aws_account_alias_value"]
            jsonalarmdescription["ci"] = ci
            jsonalarmdescription["cloudid"] = cloudid

            if eventtype is not None and eventtype != "":
                jsonalarmdescription["eventtype"] = eventtype
            if monitorcomponent is not None and monitorcomponent != "":
                jsonalarmdescription["monitorcomponent"] = monitorcomponent
            if impact is not None:
                jsonalarmdescription["impact"] = impact
            alarmdescription = json.dumps(jsonalarmdescription)
        else:
            alarmdescription = kwargs["AlarmDescription"]
            kwargs.pop("AlarmDescription")

        # Check alarm notification

        # Not specified = default (check environment variable)
        if "AlarmActions" not in kwargs:
            kwargs["AlarmActions"] = os.environ["sns_topic_arn"].split(";")
        # If explicit empty, remove them
        elif kwargs["AlarmActions"] == "":
            kwargs.pop("AlarmActions")
        # If explicit specified, convert them to array
        else:
            kwargs["AlarmActions"] = kwargs["AlarmActions"].split(";")

        # Not specified = default (check environment variable)
        if "OKActions" not in kwargs:
            kwargs["OKActions"] = os.environ["sns_topic_arn"].split(";")
        # If explicit empty, remove them
        elif kwargs["OKActions"] == "":
            kwargs.pop("OKActions")
        # If explicit specified, convert them to array
        else:
            kwargs["OKActions"] = kwargs["OKActions"].split(";")

        try:
            CloudWatchWrapper.replace_decimals(kwargs)
            need_create = kwargs.pop("Create", True)
            if need_create:
                alarm = cloudwatchclient.put_metric_alarm(
                    AlarmDescription=alarmdescription,
                    **kwargs)

                LOGGER.info(
                    "Added/Modified alarm %s to track metric %s.%s.", kwargs["AlarmName"], kwargs["Namespace"],
                    kwargs["MetricName"])
        except:
            LOGGER.exception(
                "Couldn't add alarm %s to metric %s.%s", kwargs.get(
                    "AlarmName", None), kwargs.get("Namespace", None),
                kwargs.get("MetricName", None))
            raise
        else:
            return alarm

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

from utility import Utility

LOGGER = logging.getLogger()


class CloudWatchDynamoDB:
    """
    Encapsulates Amazon CloudWatch DynamoDB functions.
    """

    def __init__(self, dynamodb, cloudwatchclient, default_values):
        metric_needed = {}
        for metric_name in default_values:
            metric_needed[metric_name] = default_values[metric_name]

        # Call up creation of extracted metrics
        for metric_name in metric_needed:
            cloudid = dynamodb["TableInfo"]["TableId"]
            ciname = dynamodb["TableInfo"]["TableName"]

            if "DynamicCore" in metric_needed[metric_name]["MetricSpecifications"]:
                getattr(CloudWatchDynamoDB, metric_needed[metric_name]["MetricSpecifications"]["DynamicCore"])(
                    dynamodb, ciname, cloudid, default_values)
            else:
                alarm_values = Utility.get_default_parameters(
                    monitoring_id=metric_name,
                    item_id=ciname,
                    default_values=default_values)

                # At 2024/04/22 we have only two alarms to set, and they do not need Dimensions param (the empty list)
                #  as documented here https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html#AccountProvisionedReadCapacityUtilization
                Utility.default_core_method(metric_needed[metric_name],
                                            CloudWatchDynamoDB,
                                            dynamodb,
                                            ciname,
                                            cloudid,
                                            alarm_values,
                                            [
                                                {
                                                    "Name": "TableName",
                                                    "Value": ciname
                                                }
                                            ],
                                            cloudwatchclient
                                            )
